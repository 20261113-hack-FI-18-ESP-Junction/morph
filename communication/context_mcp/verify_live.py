#!/usr/bin/env python3
"""Verify the prepared TLS endpoint and save a credential-free local evidence report."""
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request

from connect_intel import check_connection, NoRedirect
from store import now

root = Path(__file__).resolve().parents[1]
folder = root / ".junction-setup/context-share/intel-pairing"
connection = json.loads((folder / "connection.json").read_text())
result = check_connection(connection, folder)
tls = ssl.create_default_context(cafile=str(folder / "morph-ca.pem"))
opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=tls))
unauthorized = []
for authorization in (None, "Bearer invalid-test-token"):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if authorization:
        headers["Authorization"] = authorization
    request = urllib.request.Request(connection["url"], data=b"{}", headers=headers)
    try:
        opener.open(request, timeout=10)
        raise SystemExit("FAIL: unauthenticated request was accepted")
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        unauthorized.append(error.code)
report = {"checked_at": now(), "status": "passed", "type": "Mac client to actual Mac Wi-Fi HTTPS endpoint; not an Intel-side test", "url": connection["url"], "tls_certificate_verified": True, "authenticated_mcp": result, "missing_and_wrong_token_http_codes": unauthorized, "intel_connection_verified": False, "physical_hardware_tested": False}
path = root / "context_mcp/live-check.json"
path.write_text(json.dumps(report, indent=2) + "\n")
print("Evidence saved:", path)
