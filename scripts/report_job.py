#!/usr/bin/env python3
"""Report the current workflow run back to the Cloudflare Worker."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-url", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--callback-token", required=True)
    parser.add_argument("--status", required=True, choices=("running", "succeeded", "failed"))
    parser.add_argument("--actions-url", required=True)
    parser.add_argument("--artifact-name")
    args = parser.parse_args()
    body = {"status": args.status, "actionsUrl": args.actions_url}
    if args.artifact_name:
        body["artifactName"] = args.artifact_name
    request = urllib.request.Request(
        f"{args.worker_url.rstrip('/')}/v1/jobs/{args.job_id}/callback",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {args.callback_token}",
            "Content-Type": "application/json",
            "User-Agent": "yumebox-icon-builder",
        },
    )
    with urllib.request.urlopen(request, timeout=30):
        pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, urllib.error.URLError) as error:
        print(f"Callback error: {error}", file=sys.stderr)
        raise SystemExit(1)
