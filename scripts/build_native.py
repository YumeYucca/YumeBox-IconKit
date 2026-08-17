#!/usr/bin/env python3
"""Prepare YumeBox native inputs and build the arm64-v8a dependencies."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    args = parser.parse_args()
    target = args.target.resolve()
    ca_source = Path("/etc/ssl/certs/ca-certificates.crt")
    ca_destination = target / "core/src/foss/golang/mihomo/component/ca/ca-certificates.crt"
    ca_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ca_source, ca_destination)
    env = os.environ | {"ABI_APP_LIST": "arm64-v8a"}
    run([sys.executable, "scripts/native-build.py", "--geo"], target, env)
    run([sys.executable, "scripts/sync_kernel.py", "alpha"], target, env)
    run([sys.executable, "scripts/native-build.py", "--go", "--rust", "--compat", "--loader", "--ebpf"], target, env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
