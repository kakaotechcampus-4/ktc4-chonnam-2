"""Bounded metadata-only physical purge planning; caller supplies quiescence.

No original paths, BLOBs or provider requests are read. A shared graph is kept;
unknown connected metadata fails closed rather than guessing ownership.
"""
from datetime import datetime, timezone
import hashlib
import json
import re

import sqlalchemy as sa

from .mysql_repository import entries, chunks, _key
from .prepared_metadata import decode_prepared_payload

MAX_ROWS = 10000
MAX_ROW_BYTES = 65536
MAX_METADATA_BYTES = 16 * 1024 * 1024
_KINDS = frozenset({"source_asset", "local_source", "media_stream", "stream_index", "gps", "time_observation",
    "frame", "frame_position", "asset_facts", "timeline", "span", "analysis_source", "incident_clip",
    "prepared_content", "remote_copy", "export_transform", "derived_asset", "derived_content", "deleted"})
_REF_KINDS = ("source_asset", "media_stream", "frame_ref", "analysis_source", "incident_clip", "derived_asset", "remote_copy")
_IDS = frozenset({"source_asset_ref", "media_stream_ref", "media_stream_refs", "frame_ref",
    "analysis_source_ref", "incident_clip_ref", "derived_asset_ref", "timeline_id", "transform_ref", "remote_copy_ref"})


class PurgeBlocked(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__("recording purge " + code.lower())


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def _nodes(value, key=None):
    result = set()
    if isinstance(value, dict):
        if value.get("kind") in _REF_KINDS and isinstance(value.get("ref"), str):
            result.add(value["ref"])
        for name, child in value.items():
            result.update(_nodes(child, name))
    elif isinstance(value, list):
        for child in value:
            result.update(_nodes(child, key))
    elif key in _IDS and isinstance(value, str):
        result.add(value)
    return result


def plan_rows(rows, case_id, stamp):
    try:
        if len(rows) > MAX_ROWS:
            raise PurgeBlocked("LIMIT")
        restored, total, wanted, foreign, owners = [], 0, set(), set(), set()
        for row in rows:
            raw = _encoded(row["payload"])
            total += len(raw)
            if len(raw) > MAX_ROW_BYTES or total > MAX_METADATA_BYTES:
                raise PurgeBlocked("LIMIT")
            payload = decode_prepared_payload(row["payload"]) if row["kind"] in ("analysis_source", "incident_clip") else row["payload"]
            if not isinstance(payload, dict):
                raise PurgeBlocked("CORRUPT")
            nodes = _nodes(payload)
            restored.append((row, payload, nodes, hashlib.sha256(raw).hexdigest()))
            if row["kind"] == "case_asset":
                ref = payload["asset_ref"]["ref"]
                if not isinstance(payload["case_id"], str) or not isinstance(ref, str):
                    raise PurgeBlocked("CORRUPT")
                owners.add(ref)
                (wanted if payload["case_id"] == case_id else foreign).add(ref)
        all_nodes = set().union(*(r[2] for r in restored)) if restored else set()
        aliases = {_key(n): n for n in all_nodes}
        for n in all_nodes:
            for kind in _REF_KINDS:
                aliases[_key([kind, n])] = n
        for row, payload, nodes, digest in restored:
            if row["entry_key"] in aliases:
                nodes.add(aliases[row["entry_key"]])
            if row["kind"] == "source_asset" and payload.get("source_asset_ref") not in owners:
                foreign.update(nodes)
        def closure(seed):
            reached, changed = set(seed), True
            while changed:
                changed = False
                for row, payload, nodes, digest in restored:
                    if row["kind"] != "case_asset" and reached & nodes and not nodes <= reached:
                        reached.update(nodes)
                        changed = True
            return reached
        mine, protected = closure(wanted), closure(foreign)
        selected, retained, shared = [], [], 0
        for row, payload, nodes, digest in restored:
            owned_link = row["kind"] == "case_asset" and payload.get("case_id") == case_id
            connected = row["kind"] != "case_asset" and bool(nodes & mine)
            if connected and row["kind"] not in _KINDS:
                raise PurgeBlocked("UNSUPPORTED")
            if owned_link or (connected and not nodes & protected):
                if row["kind"] == "remote_copy":
                    expiry = payload.get("expires_at")
                    parsed = datetime.fromisoformat(expiry) if isinstance(expiry, str) else None
                    if parsed is None or parsed.tzinfo is None or parsed.astimezone(timezone.utc) > stamp:
                        raise PurgeBlocked("PENDING_EXPIRY")
                selected.append({"ordinal": row["ordinal"], "kind": row["kind"],
                    "entry_key": row["entry_key"], "payload_sha256": digest})
            else:
                retained.append((row, payload))
                shared += int(connected)
        selected_ids = {r["ordinal"] for r in selected}
        protected_files = {p.get("locator") for r, p in retained if r["kind"] == "local_source"}
        files = []
        for row, payload, nodes, digest in restored:
            if row["ordinal"] in selected_ids and row["kind"] == "local_source":
                locator = payload["locator"]
                if not isinstance(locator, str) or re.fullmatch(r"source/[0-9a-f]{32}", locator) is None:
                    raise PurgeBlocked("UNSAFE_FILE")
                if locator not in protected_files:
                    if (not isinstance(payload.get("sha256"), str)
                            or re.fullmatch(r"[0-9a-f]{64}", payload["sha256"]) is None
                            or type(payload.get("byte_size")) is not int or payload["byte_size"] < 0):
                        raise PurgeBlocked("CORRUPT")
                    files.append({k: payload[k] for k in ("locator", "sha256", "byte_size")})
        return {"case_id": case_id, "entries": selected, "files": files, "shared_entries": shared}
    except PurgeBlocked:
        raise
    except Exception:
        raise PurgeBlocked("CORRUPT") from None


def read_metadata(conn):
    # Filter by metadata size on the server before transporting it. Never select
    # content, HASH(content), media lengths or full binary artifacts.
    if conn.execute(sa.select(entries.c.ordinal).where(
            sa.func.length(sa.cast(entries.c.payload, sa.Text)) > MAX_ROW_BYTES).limit(1)).first() is not None:
        raise PurgeBlocked("LIMIT")
    rows = [dict(r) for r in conn.execute(sa.select(entries.c.ordinal, entries.c.kind,
        entries.c.entry_key, entries.c.payload).order_by(entries.c.ordinal).limit(MAX_ROWS + 1)
        .with_for_update()).mappings()]
    if len(rows) > MAX_ROWS:
        raise PurgeBlocked("LIMIT")
    return rows


def build_plan(conn, case_id):
    return plan_rows(read_metadata(conn), case_id, datetime.now(timezone.utc))


def apply_plan(conn, plan):
    current = build_plan(conn, plan["case_id"])
    if current != plan:
        raise PurgeBlocked("CHANGED")
    rows = plan["entries"]
    for start in range(0, len(rows), 100):
        part = rows[start:start + 100]
        conn.execute(chunks.delete().where(sa.tuple_(chunks.c.kind, chunks.c.entry_key)
            .in_([(r["kind"], r["entry_key"]) for r in part])))
        conn.execute(entries.delete().where(entries.c.ordinal.in_([r["ordinal"] for r in part])))
