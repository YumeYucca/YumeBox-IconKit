#!/usr/bin/env python3
"""Download, validate, and apply an Android Asset Studio launcher icon bundle."""

from __future__ import annotations

import argparse
import io
import json
import shutil
import struct
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DENSITIES = {
    "mdpi": (48, 108),
    "hdpi": (72, 162),
    "xhdpi": (96, 216),
    "xxhdpi": (144, 324),
    "xxxhdpi": (192, 432),
}
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 24 * 1024 * 1024


def png_dimensions(data: bytes, name: str) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        raise ValueError(f"{name} is not a PNG")
    return struct.unpack(">II", data[16:24])


def required_members() -> dict[str, int]:
    members = {
        "manifest.json": 0,
        "res/mipmap-anydpi-v26/ic_launcher.xml": 0,
    }
    for density in DENSITIES:
        for name in ("ic_launcher", "ic_launcher_adaptive_back", "ic_launcher_adaptive_fore"):
            members[f"res/mipmap-{density}/{name}.png"] = 0
    return members


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "yumebox-icon-builder"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("Icon bundle exceeds 8 MB")
    return payload


def validate_archive(payload: bytes) -> zipfile.ZipFile:
    archive = zipfile.ZipFile(io.BytesIO(payload))
    infos = archive.infolist()
    if any(info.is_dir() or Path(info.filename).is_absolute() or ".." in Path(info.filename).parts for info in infos):
        raise ValueError("Icon bundle has unsafe paths")
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("Icon bundle expands beyond 24 MB")
    missing = set(required_members()) - set(archive.namelist())
    if missing:
        raise ValueError(f"Icon bundle is missing {sorted(missing)[0]}")
    try:
        manifest = json.loads(archive.read("manifest.json"))
    except (json.JSONDecodeError, KeyError) as error:
        raise ValueError("Invalid icon bundle manifest") from error
    if manifest.get("format") != "android-asset-studio-launcher-icon-v1":
        raise ValueError("Unsupported icon bundle format")
    icon_xml = archive.read("res/mipmap-anydpi-v26/ic_launcher.xml").decode("utf-8")
    if "<adaptive-icon" not in icon_xml or "<monochrome" in icon_xml:
        raise ValueError("Invalid adaptive icon XML")
    for density, (legacy_size, adaptive_size) in DENSITIES.items():
        for name, expected_size in (
            ("ic_launcher", legacy_size),
            ("ic_launcher_adaptive_back", adaptive_size),
            ("ic_launcher_adaptive_fore", adaptive_size),
        ):
            path = f"res/mipmap-{density}/{name}.png"
            if png_dimensions(archive.read(path), path) != (expected_size, expected_size):
                raise ValueError(f"{path} has incorrect dimensions")
    return archive


def apply(archive: zipfile.ZipFile, target: Path) -> None:
    resources = target / "app" / "res"
    if not resources.is_dir():
        raise ValueError(f"YumeBox resources not found in {target}")
    for density in DENSITIES:
        source_dir = f"res/mipmap-{density}"
        destination_dir = resources / source_dir
        shutil.copyfile(archive.open(f"{source_dir}/ic_launcher.png"), destination_dir / "ic_launcher.png")
        shutil.copyfile(
            archive.open(f"{source_dir}/ic_launcher_adaptive_back.png"),
            destination_dir / "ic_launcher_background.png",
        )
        shutil.copyfile(
            archive.open(f"{source_dir}/ic_launcher_adaptive_fore.png"),
            destination_dir / "ic_launcher_foreground.png",
        )
    icon_xml = archive.read("res/mipmap-anydpi-v26/ic_launcher.xml").decode("utf-8")
    icon_xml = icon_xml.replace("ic_launcher_adaptive_back", "ic_launcher_background")
    icon_xml = icon_xml.replace("ic_launcher_adaptive_fore", "ic_launcher_foreground")
    (resources / "mipmap-anydpi" / "ic_launcher.xml").write_text(icon_xml, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-url", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--download-token", required=True)
    parser.add_argument("--target", required=True, type=Path)
    args = parser.parse_args()
    bundle_url = f"{args.worker_url.rstrip('/')}/v1/jobs/{args.job_id}/bundle?token={args.download_token}"
    archive = validate_archive(download(bundle_url))
    apply(archive, args.target.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f"Icon bundle error: {error}", file=sys.stderr)
        raise SystemExit(1)
