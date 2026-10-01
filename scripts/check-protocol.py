#!/usr/bin/env python3
"""Reject unreviewed protocol changes; updates require an explicit lock change."""

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
args = parser.parse_args()
lock = json.loads((ROOT / "protocol.lock.json").read_text())
revision = subprocess.check_output(
    ["git", "-C", str(args.path), "rev-parse", "HEAD"], text=True
).strip()
changes = subprocess.check_output(
    ["git", "-C", str(args.path), "status", "--porcelain", "--untracked-files=no"],
    text=True,
)
if revision != lock["revision"] or changes:
    raise SystemExit(
        "protocol dependency differs from reviewed revision; update lock and vectors together"
    )
print("protocol dependency:", revision)
