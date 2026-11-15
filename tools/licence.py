"""Vendor tool for office-install licences (P13.5). Keep the private key OFFLINE.

  python tools/licence.py keygen --out vendor-licence.key
      Writes the private key (keep it secret) and prints the public key: put that line into
      backend/apps/tenancy/licence_public_key.txt before building a release.
  python tools/licence.py sign --key vendor-licence.key --agency "Regional Office" \\
      --expires 2027-12-31 --seats 50 --out licence.json
  python tools/licence.py show licence.json
"""

import argparse
import base64
import datetime
import json
import sys
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical(payload: dict) -> bytes:  # must match apps.tenancy.licence.canonical
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def keygen(args) -> None:
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    out = Path(args.out)
    out.write_text(base64.b64encode(raw).decode() + "\n")
    out.chmod(0o600)
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print(f"private key written to {out} (keep it offline)")
    print(f"public key: {base64.b64encode(pub).decode()}")


def sign_payload(private_b64: str, payload: dict) -> dict:
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_b64.strip()))
    return {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}


def sign(args) -> None:
    datetime.date.fromisoformat(args.expires)  # validate
    payload = {
        "licence_id": str(uuid.uuid4()),
        "agency": args.agency,
        "expires": args.expires,
        "seats": int(args.seats),
        "issued": datetime.date.today().isoformat(),
    }
    doc = sign_payload(Path(args.key).read_text(), payload)
    Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"licence written to {args.out}: {payload}")


def show(args) -> None:
    print(json.dumps(json.loads(Path(args.file).read_text())["payload"], indent=2))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--out", required=True)
    s = sub.add_parser("sign")
    s.add_argument("--key", required=True)
    s.add_argument("--agency", required=True)
    s.add_argument("--expires", required=True, help="YYYY-MM-DD")
    s.add_argument("--seats", required=True, type=int)
    s.add_argument("--out", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("file")
    args = p.parse_args(argv)
    {"keygen": keygen, "sign": sign, "show": show}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
