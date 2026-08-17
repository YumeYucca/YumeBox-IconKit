#!/usr/bin/env python3
"""Restore the release signing files from GitHub Actions secret environment variables."""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path


def require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"Missing {name}")
    return value


def main() -> int:
    target = Path(os.environ["YUMEBOX_DIR"])
    keystore = base64.b64decode(require("SIGNING_KEYSTORE_BASE64"), validate=True)
    if not keystore:
        raise ValueError("SIGNING_KEYSTORE_BASE64 is empty")
    (target / "release.keystore").write_bytes(keystore)
    properties = {
        "keystore.password": require("SIGNING_STORE_PASSWORD"),
        "key.alias": require("SIGNING_KEY_ALIAS"),
        "key.password": require("SIGNING_KEY_PASSWORD"),
        "keystore.path": "release.keystore",
    }
    (target / "signing.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, ValueError, base64.binascii.Error) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
