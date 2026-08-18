#!/usr/bin/env python3
"""Build and stage exactly the builtin and external IconKit APKs."""

from __future__ import annotations

import argparse
import glob
import shutil
import subprocess
import sys
from pathlib import Path


def exactly_one(pattern: str) -> Path:
    files = [Path(path) for path in glob.glob(pattern)]
    if len(files) != 1:
        raise RuntimeError(f"Expected one APK matching {pattern}, found {len(files)}")
    return files[0]


def clean_apks(directory: Path) -> None:
    for apk in directory.glob("*.apk"):
        apk.unlink()


def build(target: Path, geo_bundle: bool, arguments: list[str]) -> Path:
    outputs = target / "app/build/outputs/apk/release"
    clean_apks(outputs)
    subprocess.run(
        ["./gradlew", "--no-daemon", *arguments, f"-Pgeo.bundle={'true' if geo_bundle else 'false'}", ":app:assembleRelease"],
        cwd=target,
        check=True,
    )
    return exactly_one(str(outputs / ("*-builtin-*.apk" if geo_bundle else "*-external-*.apk")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--build-number", required=True)
    parser.add_argument("--build-hash", required=True)
    parser.add_argument("--build-branch", required=True)
    parser.add_argument("--variant", choices=("builtin", "external"))
    args = parser.parse_args()
    target = args.target.resolve()
    (target / "gradlew").chmod((target / "gradlew").stat().st_mode | 0o111)
    stage = target / "apk-stage"
    stage.mkdir(exist_ok=True)
    clean_apks(stage)
    common = [
        "-Pupdate.channel=pre",
        "-Pupdate.tag=IconKit",
        "-Pupdate.metaAssetName=YumeBox-IconKit-meta.json",
        f"-Pbuild.number={args.build_number}",
        f"-Pbuild.hash={args.build_hash}",
        f"-Pbuild.branch={args.build_branch}",
        "-Papk.output.tail=iconkit",
    ]
    variants = (args.variant,) if args.variant else ("builtin", "external")
    for variant in variants:
        geo_bundle = variant == "builtin"
        shutil.copyfile(
            build(target, geo_bundle, common),
            stage / f"YumeBox-IconKit-{variant}.apk",
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"APK build error: {error}", file=sys.stderr)
        raise SystemExit(1)
