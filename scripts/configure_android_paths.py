#!/usr/bin/env python3
"""Write the Android SDK and NDK locations expected by the YumeBox build."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--ndk-version", required=True)
    args = parser.parse_args()
    sdk_root = os.environ.get("ANDROID_SDK_ROOT", "")
    if not sdk_root:
        raise ValueError("Missing ANDROID_SDK_ROOT")
    (args.target.resolve() / "local.properties").write_text(
        f"sdk.dir={sdk_root}\nndk.dir={sdk_root}/ndk/{args.ndk_version}\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
