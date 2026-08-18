#!/usr/bin/env python3
"""Extract the one permitted IconKit bundle URL from an issue body."""

from __future__ import annotations

import argparse
import re


def extract(issue_body: str, worker_url: str) -> tuple[str, str]:
    base_url = worker_url.rstrip("/")
    pattern = re.compile(
        rf"{re.escape(base_url)}/v1/jobs/"
        r"(?P<job_id>[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})"
        r"/bundle\?token=(?P<token>[0-9a-f]{64})",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(issue_body))
    if len(matches) != 1:
        raise ValueError("Issue must contain exactly one valid IconKit bundle URL")
    return matches[0]["job_id"], matches[0]["token"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-url", required=True)
    parser.add_argument("--issue-body", required=True)
    args = parser.parse_args()
    job_id, token = extract(args.issue_body, args.worker_url)
    print(f"ICON_JOB_ID={job_id}")
    print(f"ICON_DOWNLOAD_TOKEN={token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
