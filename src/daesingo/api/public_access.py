"""A-1 HTTP ownership port and shared-state wiring, separate from Case domain."""
import asyncio
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import re
import secrets
from time import monotonic

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from daesingo.common.db.transactions import run_api_transaction
from daesingo.common.public_runtime.policy import PublicDenied, load_policy
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.common.public_runtime import schema as public_schema
from sqlalchemy import select
from .official_samples import OfficialSamples, SampleRejected, source_duration_ms
from .upload import _storage_call
from daesingo.common.public_runtime.work import local_only

COOKIE = "__Host-daesingo_a1"
_actor: ContextVar[bytes | None] = ContextVar("public_owner", default=None)


def denied(error):
    code = "http.not_found" if error.status == 404 else "public." + error.code.lower()
    headers = {"Cache-Control": "private, no-store"}
    if error.status == 429:
        headers["Retry-After"] = "60"
    return JSONResponse({"ok": False, "error": {"code": code, "message_key": code},
                         "case_view": None}, status_code=error.status, headers=headers)


class PublicAPI:
    def __init__(self, startup, engine, cleanup):
        self.startup, self.engine, self.cleanup = startup, engine, cleanup
        self.policy = load_policy(startup.config.public.policy_file, revision=startup.revision)
        # Case Owner may replace this same-Connection ownership port; no
        # browser identifier, header override or process-local ownership map.
        self.ownership = self.store = PublicStore(self.policy, require_public=True)
        self.catalog = None
        try:
            if self.policy is not None:
                path = Path(self.policy.manifest_file)
                if path.stat().st_size > 262144:
                    raise ValueError
                with path.open("rb") as reader:
                    raw = reader.read(262145)
                self.catalog = OfficialSamples.from_manifest(raw,
                    expected_sha256=self.policy.manifest_sha256, root=Path(self.policy.samples_root),
                    max_total_bytes=self.policy.max_input_bytes)
        except Exception:
            self.catalog = None
        from .public_retention import PublicRetention
        from daesingo.common.public_runtime.temporary import public_temp_root
        self.retention = PublicRetention(engine=engine, store=self.store,
            media_root=startup.config.media_root, temp_root=public_temp_root(startup.config.media_root))

    def transaction(self, callback):
        return run_api_transaction(self.engine, callback)

    def ready(self):
        self.configured()
        if self.catalog is None:
            raise PublicDenied()

    def configured(self):
        if self.policy is None:
            raise PublicDenied()

    def owner(self):
        owner = _actor.get()
        if owner is None:
            raise PublicDenied("NOT_FOUND")
        return owner

    def require(self, conn, case_id):
        return self.ownership.require_owner(conn, case_id, self.owner())

    def before_create(self, conn):
        self.ready()
        self.store.accepting(conn)
        self.ownership.session(conn, self.owner())

    def claim(self, conn, case_id):
        self.ownership.claim_case(conn, case_id, self.owner())

    def check_sources(self, conn, case, repository, *, local=False):
        self.ready()
        self.store.local_accepting(conn) if local else self.store.accepting(conn)
        row = self.require(conn, case.case_id)
        bound = row["sources"]
        if (not bound or [s["source_asset_ref"] for s in case.sources]
                != [s["source_asset_ref"] for s in bound]):
            raise PublicDenied("INPUT")
        for item in bound:
            source = repository.get_local_source(item["source_asset_ref"])
            if (source is None or source.sha256 != item["sha256"] or source.byte_size != item["byte_size"]
                    or source_duration_ms(source) != item["duration_ms"]):
                raise PublicDenied("INPUT")
        self.store._bound_case(conn, case.case_id, local=local)

    def admit_result(self, conn, payload, result):
        if not result.appended_job_records:
            return
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).digest()
        if local_only(result.appended_job_records):
            return self.store.admit_local(conn, payload["case_id"], key, result.appended_job_records)
        self.store.admit(conn, payload["case_id"], key, initial=payload.get("kind") == "START_ANALYSIS")

    def decorate_view(self, conn, view):
        if view is None:
            return view
        row = self.require(conn, view["case_id"])
        state = row["local_work_state"]
        if state and state["case_rev"] == view["case_rev"]:
            view["notices"].append({"code": "public.local_work_not_queued", "severity": "WARN", "blocking": False,
                "message_key": "notice.public_local_" + state["reason"].lower(), "actions": []})
        return view

    def origin(self, headers):
        self.configured()
        if headers.get("origin") != self.policy.origin:
            raise PublicDenied("ORIGIN")

    def token_owner(self, request):
        token = request.cookies.get(COOKIE, "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise PublicDenied("NOT_FOUND")
        self.configured()
        return self.store.fingerprint("session:" + token)

    def issue_session(self, request):
        self.origin(request.headers)
        token = request.cookies.get(COOKIE, "")
        # Never trust arbitrary X-Forwarded-For. With the current local proxy,
        # absent verified per-client peer identity is conservatively shared.
        peer = request.client.host if request.client is not None else "unknown-peer"
        ip = self.store.fingerprint("ip:" + peer)
        if re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            owner = self.store.fingerprint("session:" + token)
            def resume(conn):
                self.store.accepting(conn)
                exists = conn.execute(select(public_schema.sessions.c.session_hash).where(
                    public_schema.sessions.c.session_hash == owner).with_for_update()).first()
                if exists is None:
                    return False
                self.store.create_session(conn, owner, ip)
                return True
            if self.transaction(resume):
                return token
        # Client-supplied unknown tokens never become server-issued identities.
        token = secrets.token_urlsafe(32)
        owner = self.store.fingerprint("session:" + token)
        self.transaction(lambda conn: self.store.create_session(conn, owner, ip))
        return token


class PublicHTTPMiddleware:
    """Authenticate every Case method/Range URL before receiving or exposing bytes."""
    def __init__(self, app, *, composition):
        self.app, self.composition = app, composition

    async def __call__(self, scope, receive, send):
        public = self.composition.public
        if public is None or scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        if root and path.startswith(root + "/"):
            path = path[len(root):]
        if not (path == "/cases" or path.startswith("/cases/") or path.startswith("/public/")):
            return await self.app(scope, receive, send)
        token = None
        guard = None
        guard_entered = [False]
        body_deadline = monotonic() + 15
        body_complete = False
        try:
            if scope["method"] == "POST" and re.fullmatch(r"/cases/[^/]+/sources", path):
                raise PublicDenied("UPLOAD_DISABLED")
            request = Request(scope)
            if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
                public.origin(request.headers)
            if path == "/cases" or path.startswith("/cases/"):
                owner = public.token_owner(request)
                if path == "/cases":
                    await _storage_call(public.transaction, lambda conn: public.ownership.session(conn, owner))
                else:
                    case_id = path.split("/")[2]
                    await _storage_call(public.transaction,
                        lambda conn: public.ownership.require_owner(conn, case_id, owner,
                            deleting=scope["method"] == "DELETE"))
                token = _actor.set(owner)
                if scope["method"] != "DELETE":
                    scanner = next(s for s in public.cleanup.scanners if s.kind == "orphan")
                    guard = scanner.in_use()
                    def enter_guard():
                        guard.__enter__()
                        guard_entered[0] = True
                    await _storage_call(enter_guard)
            async def bounded_receive():
                nonlocal body_complete
                if body_complete:
                    return await receive()
                remaining = body_deadline - monotonic()
                if remaining <= 0:
                    raise PublicDenied("INPUT")
                try:
                    message = await asyncio.wait_for(receive(), timeout=remaining)
                except TimeoutError:
                    raise PublicDenied("INPUT") from None
                if message["type"] == "http.request" and not message.get("more_body", False):
                    body_complete = True
                return message
            async def private_send(message):
                if message["type"] == "http.response.start" and (path == "/cases" or path.startswith("/cases/")):
                    headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                    message = {**message, "headers": [*headers, (b"cache-control", b"private, no-store"), (b"vary", b"Cookie")]}
                await send(message)
            task = asyncio.create_task(self.app(scope, bounded_receive, private_send))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                # Do not release a deletion lease while a shielded DB/media
                # read is still running after the browser disconnects.
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        continue
                    except BaseException:
                        break
                if not task.cancelled():
                    task.exception()
                raise
        except PublicDenied as error:
            await denied(error)(scope, receive, send)
        finally:
            if guard is not None and guard_entered[0]:
                await _storage_call(guard.__exit__, None, None, None)
            if token is not None:
                _actor.reset(token)


def public_router(composition):
    router = APIRouter()
    public = composition.public
    if public is None:
        return router

    @router.get("/public/samples")
    def samples():
        public.ready()
        return JSONResponse({"samples": public.catalog.list_samples()}, headers={"Cache-Control": "no-store"})

    @router.post("/public/session")
    def session(request: Request):
        value = public.issue_session(request)
        response = JSONResponse({"ok": True}, status_code=201, headers={"Cache-Control": "no-store"})
        response.set_cookie(COOKIE, value, httponly=True, secure=True, samesite="strict", path="/",
                            max_age=public.policy.session_ttl_sec)
        return response

    @router.post("/cases/{case_id}/official-samples")
    async def official_sample(case_id: str, request: Request):
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 4096:
                raise PublicDenied("INPUT")
            raw.extend(chunk)
        try:
            data = json.loads(raw)
            if type(data) is not dict or set(data) != {"sample_id"} or not isinstance(data["sample_id"], str):
                raise ValueError
        except (ValueError, TypeError, RecursionError):
            raise PublicDenied("INPUT") from None
        try:
            result = await _storage_call(composition.register_official_sample, case_id, data["sample_id"])
        except SampleRejected:
            raise PublicDenied("INPUT") from None
        return JSONResponse(result, status_code=201, headers={"Cache-Control": "private, no-store"})

    @router.delete("/cases/{case_id}")
    async def delete_case(case_id: str):
        await _storage_call(public.transaction, lambda conn: public.store.begin_delete(
            conn, case_id, owner=public.owner()))
        result = await _storage_call(public.retention.purge, case_id)
        return JSONResponse(result, status_code=200 if result["state"] == "DELETED" else 202,
                            headers={"Cache-Control": "private, no-store"})

    return router
