"""Check a reference tree against the pinned file and symlink manifests."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def verify_sources(source, version):
    expected = json.loads((ROOT / "scripts/source-manifest.json").read_text())[version]
    actual = {
        str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(source.rglob("*"))
        if p.is_file()
    }
    expected_links = json.loads((ROOT / "scripts/source-links.json").read_text())[
        version
    ]
    actual_links = {
        str(p.relative_to(source)): str(p.readlink())
        for p in sorted(source.rglob("*"))
        if p.is_symlink()
    }
    if actual != expected or actual_links != expected_links:
        raise SystemExit(
            f"{source}: source manifest mismatch; use the exact supplied tree"
        )
