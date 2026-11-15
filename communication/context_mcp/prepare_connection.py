#!/usr/bin/env python3
"""Create short-lived TLS credentials and a private Intel pairing ZIP without printing secrets."""
import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--host", required=True, help="The Mac's Wi-Fi IPv4 address")
parser.add_argument("--port", type=int, default=8765)
parser.add_argument("--rotate", action="store_true")
args = parser.parse_args()
address = ipaddress.ip_address(args.host)
if address.version != 4 or not 1 <= args.port <= 65535:
    raise SystemExit("Use an IPv4 address and a valid port.")
root = Path(__file__).resolve().parents[1]
private = root / ".junction-setup" / "context-share"
pairing = private / "intel-pairing"
private.mkdir(parents=True, exist_ok=True, mode=0o700)
pairing.mkdir(exist_ok=True, mode=0o700)
if (private / "token").exists() and not args.rotate:
    raise SystemExit("Connection already prepared. Use --rotate to deliberately replace its token and certificate, then restart the server.")
now = datetime.now(timezone.utc)
expires = now + timedelta(days=7)
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Morph local context CA")])
ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(expires).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True).sign(ca_key, hashes.SHA256()))
cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Morph context server")])).issuer_name(ca_name).public_key(server_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5)).not_valid_after(expires).add_extension(x509.SubjectAlternativeName([x509.IPAddress(address), x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]), critical=False).add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False).sign(ca_key, hashes.SHA256()))
token = secrets.token_urlsafe(48)
files = {
    private / "token": token.encode(),
    private / "server-key.pem": server_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
    private / "server-cert.pem": cert.public_bytes(serialization.Encoding.PEM),
    pairing / "morph-ca.pem": ca.public_bytes(serialization.Encoding.PEM),
    pairing / "connection.json": json.dumps({"url": f"https://{args.host}:{args.port}/mcp", "token": token, "expires_at": expires.isoformat()}, indent=2).encode(),
}
for path, data in files.items():
    path.write_bytes(data)
    path.chmod(0o600)
shutil.copyfile(root / "context_mcp" / "connect_intel.py", pairing / "connect_intel.py")
(pairing / "README.txt").write_text("PRIVATE PAIRING PACKAGE: contains a context access token. Copy only to the intended Intel computer, outside source control.\nRequires Python 3.11+ and Codex CLI. Extract the project snapshot into a sibling morph-context folder. From inside morph-context run:\n  python3 ../morph-intel-pairing/connect_intel.py --check\n  python3 ../morph-intel-pairing/connect_intel.py --project .\nRead context/INTEL_CODEX.md for required progress updates, evidence, offline retries and Notion updates.\nThe launcher supplies the token and trusted certificate only to its Codex child process. Desktop apps launched independently will not inherit them.\nUse the launcher for each session. The Mac must stay awake and the network must allow client-to-client traffic.\nTo revoke access, stop the server or rotate credentials.\n", encoding="utf-8")
archive = private / "morph-intel-pairing.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(pairing.iterdir()):
        bundle.write(path, "morph-intel-pairing/" + path.name)
archive.chmod(0o600)
print("Prepared:", f"https://{args.host}:{args.port}/mcp")
print("Private pairing ZIP:", archive)
print("Expires:", expires.isoformat())
print("Start the server with the --token-file, --tls-cert and --tls-key files in", private)
