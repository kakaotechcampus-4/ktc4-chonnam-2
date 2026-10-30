"""No real DNS, user data or provider calls."""
import importlib
import json
from pathlib import Path
import ssl

import pytest

REV = "b" * 40


def module():
    assert Path("deploy/public_smoke.py").exists(), "external smoke missing"
    return importlib.import_module("deploy.public_smoke")


@pytest.mark.parametrize("failure", [None, "dns", "tls", "root", "revision", "api", "redirect", "html404"])
def test_smoke_exact_public_contract(failure):
    m = module()
    paths = []
    def resolve(host, port, **kwargs):
        assert host == "synthetic.example.invalid" and port == 443
        if failure == "dns":
            raise OSError("PRIVATE-CANARY")
        return [(2, 1, 6, "", ("192.0.2.1", 443))]
    def get(host, path, context):
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        paths.append(path)
        if failure == "tls":
            raise ssl.SSLError("PRIVATE-CANARY")
        if path == "/":
            return (302 if failure == "redirect" else 500 if failure == "root" else 200, "text/html", b"ok")
        if path == "/version.json":
            return 200, "application/json", json.dumps({"revision": "c" * 40 if failure == "revision" else REV}).encode()
        assert path.startswith("/cases/") and path.endswith("/view")
        return (200 if failure == "api" else 404, "text/html" if failure == "html404" else "application/json", b'{}')
    if failure:
        with pytest.raises(m.SmokeError) as error:
            m.smoke("synthetic.example.invalid", REV, resolve=resolve, get=get)
        assert "PRIVATE-CANARY" not in str(error.value)
    else:
        m.smoke("synthetic.example.invalid", REV, resolve=resolve, get=get)
        assert len(paths) == 3


@pytest.mark.parametrize("host", ["https://example.invalid", "user@example.invalid", "example.invalid/path", "localhost", "127.0.0.1", "example.invalid:443", "example.invalid\n"])
def test_smoke_rejects_non_hostname_without_network(host):
    m = module()
    with pytest.raises(m.SmokeError):
        m.smoke(host, REV, resolve=lambda *a, **k: pytest.fail("invalid host reached DNS"))
