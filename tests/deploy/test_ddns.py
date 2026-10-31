"""Synthetic DDNS requests only; never use a real account token."""
import importlib
import io
from pathlib import Path

import pytest


@pytest.mark.parametrize("result", [b"OK\n", b"KO\n", b"PRIVATE-CANARY", None])
def test_ddns_only_accepts_exact_ok_and_keeps_token_private(result, capsys):
    assert Path("deploy/ddns.py").exists(), "protected DDNS updater missing"
    m = importlib.import_module("deploy.ddns")
    def open_request(request, timeout):
        assert request.full_url.startswith("https://www.duckdns.org/update?")
        assert "token=synthetic-token" in request.full_url
        if result is None:
            raise OSError("PRIVATE-CANARY")
        return io.BytesIO(result)
    if result == b"OK\n":
        m.update("synthetic", "synthetic-token", open_request=open_request)
    else:
        with pytest.raises(m.DDNSError) as error:
            m.update("synthetic", "synthetic-token", open_request=open_request)
        assert "PRIVATE-CANARY" not in str(error.value)
    assert "synthetic-token" not in str(capsys.readouterr())
