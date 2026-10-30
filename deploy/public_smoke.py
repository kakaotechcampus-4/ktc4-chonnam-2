"""Read-only public acceptance. Never prints hostname, body or exception text."""
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import uuid


class SmokeError(Exception):
    pass


def require(ok):
    if not ok:
        raise SmokeError("public_smoke_failed")


def https_get(host, path, context):
    # No proxies, redirects, cookies, authentication or disabled TLS validation.
    connection = http.client.HTTPSConnection(host, 443, timeout=15, context=context)
    try:
        connection.request("GET", path, headers={"Cache-Control": "no-cache", "Accept": "*/*"})
        response = connection.getresponse()
        body = response.read(65537)
        require(len(body) <= 65536)
        return response.status, response.getheader("Content-Type", "").split(";", 1)[0], body
    finally:
        connection.close()


def smoke(host, revision, *, resolve=socket.getaddrinfo, get=https_get):
    try:
        require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)))
        require(isinstance(host, str) and len(host) <= 253 and "." in host)
        require(all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                    for part in host.split(".")))
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise SmokeError("hostname_required")
        require(bool(resolve(host, 443, type=socket.SOCK_STREAM)))
        context = ssl.create_default_context()
        status, _, _ = get(host, "/", context)
        require(status == 200)
        status, content_type, body = get(host, "/version.json", context)
        require(status == 200 and content_type == "application/json")
        require(json.loads(body) == {"revision": revision})
        status, content_type, _ = get(host, "/cases/" + str(uuid.uuid4()) + "/view", context)
        require(status == 404 and content_type == "application/json")
    except Exception:
        raise SmokeError("public_smoke_failed") from None


def main():
    try:
        require(len(sys.argv) == 1)
        smoke(os.environ.get("RT14_PUBLIC_HOSTNAME", ""), os.environ.get("RT14_REVISION", ""))
        print("rt14-public: verified")
        return 0
    except BaseException:
        print("rt14-public: failed_or_unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
