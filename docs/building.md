# Building and verification

Use Linux amd64 and an unprivileged account. The harness deliberately rejects
running the test build/integration as root. It never installs a setuid binary or
uses the host Exim/spool. C11 is used for the plugin; Exim itself uses GNU C11.

## Tools

Required: Python >=3.12, GNU make, patch, GCC, Clang, libc development headers,
libgdbm development files, and PCRE2 development files including pcre2-config.
Shared protocol C/Go vector tests also require Go 1.27.x; the plugin itself remains
native C. Checks additionally require clang-format **18.1.8**, clang-tidy, cppcheck, and
PyYAML for the protocol's registry/vector tooling. No C runtime dependencies are
added beyond libc and Exim's native dynamic-loader mechanism.

Locally verified compilers are recorded in COMPATIBILITY.md. CI uses Ubuntu 24.04
packages, separate GCC/Clang builds, and clang-format 18. Older compiler behavior is
not implied by local test results. Inspect tool versions with `gcc --version`,
`clang --version`, `clang-format --version`, `clang-tidy --version`,
`cppcheck --version`, and `python3 --version`.

The Makefile recognizes explicitly installed tools under the sibling protocol's
`.tools/venv/bin` and `.tools/bin`. It does not install them. For a clean Ubuntu
setup, install build-essential, clang, clang-format-18, clang-tidy, cppcheck,
libgdbm-dev, libpcre2-dev and python3-yaml; select clang-format-18 on PATH.

## Dependency and sources

Use a sibling protocol checkout at protocol.lock.json's revision. `make
check-protocol` rejects a different revision or modified tracked files. Changing
the lock requires a reviewed protocol change and vector compatibility checks.

The exact supplied references default to `../exim-observer-protocol/.tools`.
Override with `EXIM_SOURCE_ROOT=/absolute/path`. When starting without references,
`make fetch-sources EXIM_SOURCE_ROOT=.tools` explicitly downloads official archives,
checks their pinned SHA-256 and checks every extracted file against the recorded
manifest. Existing trees are verified without alteration. This is the only
network setup step; build/test/check work offline after dependencies are present.

Each build copies a pristine tree, applies version patches with --fuzz=0, writes
Local/Makefile in the copy, builds full Exim, then builds observer_miscmod.so against
its generated headers. The copy is removed even on failure. SHA-256 checks before
and after establish that references have not changed.

Artifacts and logs are under `build/<version>-<compiler>/`. Patch-only checks use
`patch.log` so they do not overwrite the full compilation log. The strict module
compiler command and diagnostics are recorded separately in `module.log`. Test configuration,
spool, delivery files and logs stay there. The test driver invokes this compiled
Exim; the plugin never launches Exim or a shell. Integration resets only those
private test spool/log/mail directories. Do not use test artifacts for production.

Unit tests require active C assertions: `-DNDEBUG` is rejected at compilation.
Integration rejects `python -O` and `PYTHONOPTIMIZE` before touching its test spool,
so disabled assertions cannot produce a false successful run.

See [compiler audit](compiler-audit.md) for measured diagnostics. The plugin has
zero enabled warnings in the tested matrix. Exim retains upstream warnings; its
syntax is preserved instead of carrying broad warning-cleanup patches. The
reference sources remain unchanged.

## Commands and scope

- `make` / `make build`: full Exim + matching module, default 4.99.5 and GCC.
- `make exim-4.99.5`, `make exim-4.100.1`: explicit releases.
- `make test`: standalone socket tests, protocol vectors and build-order
  regressions, no network. The small unit binary is always rebuilt to honor the
  selected compiler, flags and headers.
- `make integration`: build the current sources, then run SMTP and actual
  appendfile deliveries. The dependency also orders `make -j build integration`
  and prevents testing an older binary if the new build fails.
- `make check`: formatting, standalone static analysis, tests, patch verification.
- `make test-compilers`: GCC/Clang unit tests with `-Werror`, then full builds and
  integration against both Exim versions; modules use `-Werror`, Exim core does not.
  The 4.100.1 build also compiles/runs the actual no-TLS logging helper in isolation.
  Integration verifies rejection of duplicate singleton configuration options and
  acceptance of repeatable options.
- `make check-all`: check plus test-compilers.
- `make test-sanitize`: ASan/UBSan on standalone code, not on the Exim executable.
- `make format` / `make format-check`: apply/check clang-format without changing patches.

Patch context intentionally retains upstream style. All requested warning flags
are enabled for plugin code, with -Werror in the controlled module builds. Exim
core retains upstream warning settings without blanket -Werror; the plugin's
broader warning set is not imposed on upstream code.
Exim headers are system includes so their intentional casts do not weaken warnings on
plugin code. One compat header handles the old debug mask and new const-safe
is_debug call; no unused log/queue compatibility wrappers are introduced.

clang-tidy disables easily-swappable-parameters (fixed external C signatures),
unsafe-functions and the generic deprecated-buffer diagnostic (explicit byte
buffers are length-checked), and not-null-terminated-result (wire buffers are not
strings). It retains analyzer, bugprone, performance, portability and CERT numeric
conversion checks. cppcheck failures are not suppressed.
