#!/usr/bin/env python3
"""Validate untrusted workflow_dispatch inputs before they reach build tooling."""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse


def require(name: str, pattern: str) -> str:
    value = os.environ.get(name, "")
    if not re.fullmatch(pattern, value):
        raise ValueError(f"Invalid {name}")
    return value


def main() -> int:
    require("ICON_JOB_ID", r"[a-f0-9-]{36}")
    require("ICON_DOWNLOAD_TOKEN", r"[a-f0-9]{64}")
    require("ICON_CALLBACK_TOKEN", r"[a-f0-9]{64}")
    worker_url = os.environ.get("ICON_WORKER_URL", "")
    parsed = urlparse(worker_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("ICON_WORKER_URL must be an HTTPS origin")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
