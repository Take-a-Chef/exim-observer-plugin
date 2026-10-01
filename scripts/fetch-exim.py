#!/usr/bin/env python3
"""Explicit network setup only: fetch pinned archives and verify the full source tree."""

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from sources import verify_sources

ARCHIVES = {
    "4.99.5": "c2d2f80adc7c71d424fd82a46655eaa2d7d9b4ca2e77883eba9076947b7ee627",
    "4.100.1": "e9fb41f6724a5b136d64c9d19dbc5f26494af879a3e7e3190f91639eaa79fa0d",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--version", choices=ARCHIVES, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = "exim-" + args.version
    destination = root / name
    if destination.exists():
        verify_sources(destination, args.version)
        print(destination, "already verified; unchanged")
        return
    with tempfile.TemporaryDirectory(prefix="fetch-exim-", dir=root) as tmp:
        archive = Path(tmp) / "source.tar.xz"
        for directory in ("", "old/"):
            url = "https://ftp.exim.org/pub/exim/exim4/" + directory + name + ".tar.xz"
            try:
                with (
                    urllib.request.urlopen(url, timeout=30) as response,
                    archive.open("wb") as out,
                ):
                    total = 0
                    while chunk := response.read(65536):
                        total += len(chunk)
                        if total > 32 * 1024 * 1024:
                            raise SystemExit("archive exceeds 32 MiB setup limit")
                        out.write(chunk)
                break
            except urllib.error.HTTPError as error:
                if error.code != 404 or directory:
                    raise
        if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVES[args.version]:
            raise SystemExit("archive checksum mismatch")
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            if any(not (m.isfile() or m.isdir() or m.issym()) for m in members):
                raise SystemExit("unexpected archive member type")
            if sum(m.size for m in members) > 64 * 1024 * 1024:
                raise SystemExit("extracted archive exceeds 64 MiB setup limit")
            tar.extractall(tmp, filter="data")
        extracted = Path(tmp) / name
        verify_sources(extracted, args.version)
        shutil.move(extracted, destination)
    print(destination, "archive checksum and complete file manifest verified")


if __name__ == "__main__":
    main()
