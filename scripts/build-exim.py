#!/usr/bin/env python3
"""Copy verified Exim references, patch/build full Exim and its matching module."""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sources import verify_sources

ROOT = Path(__file__).resolve().parent.parent


def run(argv, cwd, log):
    env = os.environ.copy()
    for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL"):
        env.pop(name, None)
    log.write("+ " + shlex.join(argv) + "\n")
    log.flush()
    result = subprocess.run(
        argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=False
    )
    log.flush()
    if result.returncode:
        raise SystemExit(
            f"command failed ({result.returncode}): {argv}; see {log.name}"
        )


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["4.99.5", "4.100.1"], required=True)
    ap.add_argument("--cc", choices=["gcc", "clang"], default="gcc")
    ap.add_argument(
        "--source-root",
        type=Path,
        default=ROOT.parent / "exim-observer-protocol/.tools",
    )
    ap.add_argument(
        "--protocol-root", type=Path, default=ROOT.parent / "exim-observer-protocol"
    )
    ap.add_argument("--patch-only", action="store_true")
    return ap.parse_args()


def apply_patches(work, version, log):
    for patch in sorted((ROOT / "patches" / ("exim-" + version)).glob("*.patch")):
        run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], work, log)


def run_core_regressions(work, cc, log):
    run(
        [
            sys.executable,
            str(ROOT / "tests/build/core_regressions.py"),
            str(work),
            "--cc",
            cc,
        ],
        work,
        log,
    )


def write_local_makefile(work, output, cc):
    uid = os.getuid() or 65534
    gid = os.getgid() if os.getuid() else 65534
    (work / "Local").mkdir(exist_ok=True)
    (
        work / "Local/Makefile"
    ).write_text(f"""# Minimal unprivileged integration build; not a production configuration.
BIN_DIRECTORY={output}/bin
CONFIGURE_FILE={output}/exim.conf
CONFIGURE_OWNER={os.getuid()}
CONFIGURE_GROUP={os.getgid()}
EXIM_USER={uid}
EXIM_GROUP={gid}
SPOOL_DIRECTORY={output}/spool
LOG_FILE_PATH={output}/log/%slog
PID_FILE_PATH={output}/exim.pid
LOOKUP_MODULE_DIR={output}/modules
CC={cc}
CFLAGS=-O2 -g -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -std=gnu11
USE_GDBM=yes
DBMLIB=-lgdbm
PCRE2_CONFIG=yes
DISABLE_TLS=yes
DISABLE_DKIM=yes
DISABLE_DNSSEC=yes
DISABLE_EXIM_FILTER=yes
DISABLE_SIEVE_FILTER=yes
ROUTER_ACCEPT=yes
ROUTER_MANUALROUTE=yes
ROUTER_REDIRECT=yes
TRANSPORT_APPENDFILE=yes
TRANSPORT_SMTP=yes
LOOKUP_LSEARCH=yes
EXTRALIBS=-ldl
EXTRALIBS_EXIM=-rdynamic
EXIM_MONITOR=
""")


def compile_exim(work, log):
    # Exim forwards MFLAGS explicitly; -j in both argv and inherited
    # MAKEFLAGS resets GNU make's jobserver. Inherit it only once.
    run(["make", "-j4", "MFLAGS=", "build=Linux-observer"], work, log)
    candidates = [p for p in work.glob("build-*/exim") if p.is_file()]
    if len(candidates) != 1:
        raise SystemExit(f"expected one Exim executable, got {candidates}")
    return candidates[0]


def compile_module(work, output, cc, version, protocol, binary):
    version_number = "49905" if version == "4.99.5" else "410001"
    # Exim headers contain their own intentional casts/extensions. System-header
    # treatment confines plugin warnings to our code rather than suppressing them.
    flags = [
        "-std=c11",
        "-O2",
        "-g",
        "-fPIC",
        "-shared",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Wformat=2",
        "-Wshadow",
        "-Wconversion",
        "-Wsign-conversion",
        "-Wundef",
        "-Wcast-qual",
        "-Wwrite-strings",
        "-Wstrict-prototypes",
        "-Wmissing-prototypes",
        "-Werror=implicit-function-declaration",
        "-Werror",
        "-D_FILE_OFFSET_BITS=64",
        "-DDYNLOOKUP",
        "-DOBSERVER_EXIM_VERSION=" + version_number,
    ]
    with (output / "module.log").open("w") as module_log:
        run(
            [
                cc,
                *flags,
                "-isystem",
                str(binary.parent),
                "-I" + str(ROOT / "src"),
                "-I" + str(protocol / "include"),
                "-I" + str(protocol / "c/include"),
                str(ROOT / "src/observer.c"),
                str(ROOT / "src/event_socket.c"),
                str(protocol / "c/src/codec.c"),
                str(protocol / "c/src/validation.c"),
                "-o",
                str(output / "modules/observer_miscmod.so"),
            ],
            work,
            module_log,
        )


def install_artifacts(binary, output):
    shutil.copy2(binary, output / "exim")
    alias = output / "exim-observer.so"
    alias.unlink(missing_ok=True)
    alias.symlink_to("modules/observer_miscmod.so")


def main():
    a = parse_args()
    if os.getuid() == 0 and not a.patch_only:
        raise SystemExit("Run the private Exim build as an unprivileged user")
    source = (a.source_root / ("exim-" + a.version)).resolve()
    protocol = a.protocol_root.resolve()
    verify_sources(source, a.version)
    output = ROOT / "build" / (a.version + "-" + a.cc)
    output.mkdir(parents=True, exist_ok=True)
    (output / "modules").mkdir(exist_ok=True)
    log_name = "patch.log" if a.patch_only else "build.log"
    with (output / log_name).open("w") as log:
        try:
            with tempfile.TemporaryDirectory(
                prefix="exim-build-", dir=ROOT / "build"
            ) as tmp:
                work = Path(tmp) / "exim"
                shutil.copytree(source, work, symlinks=True)
                apply_patches(work, a.version, log)
                if a.patch_only:
                    print(a.version, "patches apply without fuzz")
                    return
                if a.version == "4.100.1":
                    run_core_regressions(work, a.cc, log)
                write_local_makefile(work, output, a.cc)
                binary = compile_exim(work, log)
                compile_module(work, output, a.cc, a.version, protocol, binary)
                install_artifacts(binary, output)
        finally:
            verify_sources(source, a.version)
    print(
        a.version, a.cc, "full Exim and observer_miscmod.so built; references unchanged"
    )


if __name__ == "__main__":
    main()
