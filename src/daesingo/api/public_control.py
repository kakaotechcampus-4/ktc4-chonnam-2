"""Local operator-only gate; no HTTP opening endpoint or embedded approval values."""
import argparse
import json
import os
from pathlib import Path
import re

from sqlalchemy import select

from daesingo.common.bootstrap import bootstrap_service
from daesingo.common.db import create_api_engine
from daesingo.common.db.transactions import run_api_transaction
from daesingo.common.public_runtime import schema
from daesingo.common.public_runtime.policy import PublicDenied, load_policy
from daesingo.common.public_runtime.repository import PublicStore


def control(engine, policy, action, *, verify_catalog=None):
    if action == "open":
        if policy is None or verify_catalog is None:
            raise PublicDenied()
        verify_catalog()  # Bounded source hash/probe verification, never in DB callback.
    store = PublicStore(policy, require_public=True)
    def operation(conn):
        store.locked(conn)
        if action != "status":
            if action == "pause-analysis":
                store.pause_analysis(conn)
            else:
                store.set_open(conn, action == "open")
        state = conn.execute(select(schema.control).where(schema.control.c.id == 1)).mappings().one()
        return {"accepting": bool(state["accepting"]), "jobs_stopped": bool(state["jobs_stopped"]), "policy_available": policy is not None,
                "policy_matches": policy is not None and state["policy_hash"] == policy.fingerprint()}
    return run_api_transaction(engine, operation)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "stop", "pause-analysis", "open"))
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        # Same image identity supplied by the verified deployment controller to
        # API/Worker bootstrap; no CLI --revision override or browser switch.
        revision = os.environ.get("DAESINGO_REVISION", "")
        if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise PublicDenied()
        startup = bootstrap_service("api", env_file=args.env_file, revision=revision)
        if startup.config.public.mode != "a1":
            raise PublicDenied()
        policy = load_policy(startup.config.public.policy_file, revision=revision)
        def verify_catalog():
            from daesingo.api.official_samples import OfficialSamples
            if policy is None:
                raise PublicDenied()
            manifest = Path(policy.manifest_file)
            if manifest.stat().st_size > 262144:
                raise PublicDenied()
            with manifest.open("rb") as reader:
                raw = reader.read(262145)
            catalog = OfficialSamples.from_manifest(raw,
                expected_sha256=policy.manifest_sha256, root=Path(policy.samples_root),
                max_total_bytes=policy.max_input_bytes)
            for item in catalog.list_samples():
                catalog.verify(item["sample_id"])
        engine = create_api_engine(startup.config.db)
        print(json.dumps(control(engine, policy, args.action, verify_catalog=verify_catalog)))
        return 0
    except Exception:
        print(json.dumps({"status": "REFUSED", "code": "PUBLIC_CONTROL_UNAVAILABLE"}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
