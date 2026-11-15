"""Small token-file client for local verification and exports."""

from __future__ import annotations

from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .api import load_token


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the station bearer token to a redirected destination.
        return None


def request(path: str, *, method: str = "GET", body: bytes | None = None,
            base_url: str = "http://127.0.0.1:8000") -> bytes:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an explicit HTTP(S) station base URL without credentials or query parameters.")
    if not path.startswith("/api/v1/") or "\r" in path or "\n" in path or "#" in path:
        raise ValueError("The request path must begin with /api/v1/ and contain no fragment or newline.")
    headers = {"Authorization": "Bearer " + load_token(), "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with build_opener(NoRedirect).open(req, timeout=30) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise ValueError(f"Station returned HTTP {exc.code}: {detail}") from exc
