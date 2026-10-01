#!/usr/bin/env python3
"""Compile the actual patched TLS-log helper in the minimal no-TLS configuration."""

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--cc", choices=["gcc", "clang"], required=True)
    args = parser.parse_args()
    text = (args.source / "src/smtp_in.c").read_text()
    function = re.search(
        r"gstring \*\nadd_tls_info_for_log\(gstring \* g\)\n\{.*?\n\}", text, re.DOTALL
    )
    if function is None:
        raise SystemExit("TLS-log helper not found in the inspected 4.100.1 source")
    with tempfile.TemporaryDirectory(prefix="tls-log-test-", dir=args.source) as tmp:
        source = Path(tmp) / "test.c"
        binary = Path(tmp) / "test"
        source.write_text(
            "#include <stddef.h>\n"
            "#define DISABLE_TLS\n"
            "typedef struct { int marker; } gstring;\n"
            + function[0]
            + "\nint main(void) {\n"
            "  gstring value = {42};\n"
            "  return add_tls_info_for_log(&value) != &value ||\n"
            "         add_tls_info_for_log(NULL) != NULL || value.marker != 42;\n"
            "}\n"
        )
        subprocess.run(
            [
                args.cc,
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(source),
                "-o",
                str(binary),
            ],
            check=True,
        )
        subprocess.run([str(binary)], check=True, timeout=10)
    print("4.100.1 no-TLS log helper preserves NULL and an existing log buffer")


if __name__ == "__main__":
    main()
