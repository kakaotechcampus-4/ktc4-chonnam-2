"""Host-only DuckDNS update; token stays in protected file and process memory."""
import os
from pathlib import Path
import re
import stat
import sys
import urllib.parse
import urllib.request


class DDNSError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DDNSError("ddns_failed")


def update(domain, token, *, open_request=None):
    try:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", domain):
            raise DDNSError("ddns_failed")
        if not re.fullmatch(r"[A-Za-z0-9-]+", token):
            raise DDNSError("ddns_failed")
        # HTTPS only, no proxy credentials, redirect or shell command. DuckDNS
        # detects IPv4 from the request; IPv6 is not guessed or configured here.
        opener = open_request or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()).open
        query = urllib.parse.urlencode({"domains": domain, "token": token, "ip": ""})
        request = urllib.request.Request("https://www.duckdns.org/update?" + query)
        with opener(request, timeout=20) as response:
            if response.read(16).strip() != b"OK":
                raise DDNSError("ddns_failed")
    except Exception:
        raise DDNSError("ddns_failed") from None


def main():
    try:
        if len(sys.argv) != 1 or os.name != "posix" or os.geteuid() != 0:
            raise DDNSError("ddns_failed")
        path = Path("/etc/daesingo-ddns/token")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o400:
            raise DDNSError("ddns_failed")
        update(os.environ.get("RT14_DDNS_SUBDOMAIN", ""), path.read_text().strip())
        print("rt14-ddns: updated")
        return 0
    except BaseException:
        print("rt14-ddns: failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
