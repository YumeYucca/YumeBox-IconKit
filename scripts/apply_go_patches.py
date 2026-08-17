#!/usr/bin/env python3
"""Apply the YumeBox Go patches to the installed Go toolchain."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-directory", required=True, type=Path)
    args = parser.parse_args()
    go_root = Path(subprocess.check_output(["go", "env", "GOROOT"], text=True).strip())
    patch_files = sorted(args.patch_directory.glob("*.patch"))
    if not patch_files:
        raise RuntimeError("No Go patches found")
    for patch_file in patch_files:
        with patch_file.open("rb") as patch:
            subprocess.run(["patch", "--verbose", "-p", "1"], cwd=go_root, stdin=patch, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
