from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.apply_icon_bundle import DENSITIES, apply
from scripts.extract_issue_bundle import extract


class ApplyIconBundleTest(unittest.TestCase):
    def test_applies_all_density_resources_without_duplicate_res_directory(self) -> None:
        archive_bytes = io.BytesIO()
        expected = {}
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            for density in DENSITIES:
                source_dir = f"res/mipmap-{density}"
                for name in (
                    "ic_launcher",
                    "ic_launcher_adaptive_back",
                    "ic_launcher_adaptive_fore",
                ):
                    member = f"{source_dir}/{name}.png"
                    expected[member] = member.encode()
                    archive.writestr(member, expected[member])
            archive.writestr(
                "res/mipmap-anydpi-v26/ic_launcher.xml",
                "<adaptive-icon>ic_launcher_adaptive_back ic_launcher_adaptive_fore</adaptive-icon>",
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "yumebox"
            resources = target / "app" / "res"
            for density in DENSITIES:
                (resources / f"mipmap-{density}").mkdir(parents=True)
            (resources / "mipmap-anydpi").mkdir()

            with zipfile.ZipFile(io.BytesIO(archive_bytes.getvalue())) as archive:
                apply(archive, target)

            for density in DENSITIES:
                source_dir = f"res/mipmap-{density}"
                destination_dir = resources / f"mipmap-{density}"
                self.assertEqual(
                    (destination_dir / "ic_launcher.png").read_bytes(),
                    expected[f"{source_dir}/ic_launcher.png"],
                )
                self.assertEqual(
                    (destination_dir / "ic_launcher_background.png").read_bytes(),
                    expected[f"{source_dir}/ic_launcher_adaptive_back.png"],
                )
                self.assertEqual(
                    (destination_dir / "ic_launcher_foreground.png").read_bytes(),
                    expected[f"{source_dir}/ic_launcher_adaptive_fore.png"],
                )

            icon_xml = (resources / "mipmap-anydpi" / "ic_launcher.xml").read_text()
            self.assertIn("ic_launcher_background", icon_xml)
            self.assertIn("ic_launcher_foreground", icon_xml)
            self.assertFalse((resources / "res").exists())


class ExtractIssueBundleTest(unittest.TestCase):
    def test_extracts_one_worker_bundle_url(self) -> None:
        worker_url = "https://yumebox-iconkit.yumeyuka.moe"
        job_id = "31e7be51-426e-4b9f-9b05-679753650973"
        token = "a" * 64
        body = f"{worker_url}/v1/jobs/{job_id}/bundle?token={token}"

        self.assertEqual(extract(body, worker_url), (job_id, token))

    def test_rejects_multiple_or_foreign_bundle_urls(self) -> None:
        worker_url = "https://yumebox-iconkit.yumeyuka.moe"
        job_id = "31e7be51-426e-4b9f-9b05-679753650973"
        token = "a" * 64
        body = (
            f"https://other.example/v1/jobs/{job_id}/bundle?token={token}\n"
            f"{worker_url}/v1/jobs/{job_id}/bundle?token={token}\n"
            f"{worker_url}/v1/jobs/{job_id}/bundle?token={token}"
        )

        with self.assertRaises(ValueError):
            extract(body, worker_url)
