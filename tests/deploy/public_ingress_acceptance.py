"""Explicit Linux loopback rehearsal. No ACME, public DNS or shared services.

Run: CADDY_BINARY=<verified local binary> python tests/deploy/public_ingress_acceptance.py
Requires a local release-marked apps/web/dist. Creates only task-owned temporary
certificates/processes, ephemeral loopback ports; cleans them in finally blocks.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from deploy import public_smoke  # noqa: E402


def main():
    paths = []
    class API(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            body = b'{"error":{"code":"synthetic"}}'
            self.send_response(503 if self.path == "/cases/error" else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    api = ThreadingHTTPServer(("127.0.0.1", 0), API)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    process = None
    with tempfile.TemporaryDirectory(prefix="rt14-ingress-") as directory:
        work = Path(directory)
        try:
            binary = os.environ["CADDY_BINARY"]
            result = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(work / "key.pem"), "-out", str(work / "cert.pem"), "-days", "1",
                "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"], capture_output=True)
            assert result.returncode == 0
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            config = (ROOT / "deploy/Caddyfile").read_text()
            config = config.replace("{\n", "{\n\tadmin off\n\tauto_https off\n", 1)
            config = config.replace("{$RT14_PUBLIC_HOSTNAME}", f"https://localhost:{port}")
            config = config.replace(f"https://localhost:{port} {{", f"https://localhost:{port} {{\n"
                f'\tbind 127.0.0.1\n\ttls "{work}/cert.pem" "{work}/key.pem"')
            config = config.replace("127.0.0.1:8000", f"127.0.0.1:{api.server_port}")
            config = config.replace("/srv/daesingo/current", str(ROOT / "apps/web/dist"))
            path = work / "Caddyfile"
            path.write_text(config)
            env = {**os.environ, "XDG_DATA_HOME": str(work / "data"), "XDG_CONFIG_HOME": str(work / "config")}
            for operation in ("adapt", "validate"):
                result = subprocess.run([binary, operation, "--config", str(path), "--adapter", "caddyfile"],
                                        env=env, capture_output=True)
                assert result.returncode == 0, "Caddy configuration rejected"
            process = subprocess.Popen([binary, "run", "--config", str(path), "--adapter", "caddyfile"],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            context = ssl.create_default_context(cafile=str(work / "cert.pem"))
            def get(host, route, tls):
                connection = http.client.HTTPSConnection("localhost", port, context=tls, timeout=3)
                try:
                    connection.request("GET", route)
                    response = connection.getresponse()
                    data = response.read()
                    assert response.getheader("Cache-Control") == "no-store"
                    return response.status, response.getheader("Content-Type", "").split(";")[0], data
                finally:
                    connection.close()
            for attempt in range(50):
                try:
                    assert get("localhost", "/", context)[0] == 200
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("loopback listener unavailable")
            revision = json.loads((ROOT / "apps/web/dist/version.json").read_text())["revision"]
            def resolve(host, port, **kwargs):
                return socket.getaddrinfo("localhost", port, **kwargs)
            with patch.object(public_smoke.ssl, "create_default_context", lambda: context):
                public_smoke.smoke("synthetic.example.invalid", revision, resolve=resolve, get=get)
                try:
                    public_smoke.smoke("synthetic.example.invalid", "0" * 40, resolve=resolve, get=get)
                except public_smoke.SmokeError:
                    pass
                else:
                    raise AssertionError("wrong revision accepted")
            try:
                get("localhost", "/", ssl.create_default_context())
            except ssl.SSLCertVerificationError:
                pass
            else:
                raise AssertionError("untrusted certificate accepted")
            assert get("localhost", "/cases/error", context)[0] == 503
            assert get("localhost", "/health/live", context)[0] == 404
            assert get("localhost", "/absent-static", context)[0] == 404
            assert "/cases/error" in paths and "/health/live" in paths
            api.shutdown()
            api.server_close()
            assert get("localhost", "/cases/down", context)[0] == 502
            print("rt14-ingress: adapt validate TLS revision routes 404 503 502 PASS (synthetic loopback only)")
        finally:
            if process:
                process.terminate()
                process.wait(timeout=10)
            api.shutdown()
            api.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print("rt14-ingress: failed", file=sys.stderr)
        raise SystemExit(1) from None
