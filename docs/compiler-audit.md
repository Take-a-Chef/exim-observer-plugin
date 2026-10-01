# Compiler audit

Local Linux amd64 run on 2026-09-30, GCC 16.2.1 and Clang 23.1.2.
Command: `make test-compilers`. All four full builds and SMTP/module integrations
passed. The standalone C tests also passed with each compiler and `-Werror`.

| Exim    | Compiler | Plugin warnings | Plugin errors | Patched Exim warnings | Patched Exim errors |
| ------- | -------- | --------------- | ------------- | --------------------- | ------------------- |
| 4.99.5  | GCC      | 0               | 0             | 4                     | 0                   |
| 4.100.1 | GCC      | 0               | 0             | 3                     | 0                   |
| 4.99.5  | Clang    | 0               | 0             | 179                   | 0                   |
| 4.100.1 | Clang    | 0               | 0             | 183                   | 0                   |

Counts are compiler diagnostic lines containing `warning:` or `error:`, not the
compiler's summary lines. Results apply to these compilers and the documented
minimal build configuration; optional TLS/authentication/filter configurations
and other toolchains are not covered by this audit. Hosted CI has not been run.

## Enforcement and evidence

The native module, socket helper and linked protocol C codec compile with the
repository's full warning set and `-Werror`. Exim core uses its upstream warning
settings without blanket `-Werror`. No additional warning category is disabled.
Exim headers remain system includes for the module compilation as documented in
building.md; the core build compiles Exim itself normally.

Each `build/<version>-<compiler>/` directory contains `module.log` with the exact
module command/output and `build.log` with the full Exim build. Patch-only checks
write a separate `patch.log`. `make test-compilers` reproduces the matrix locally
without downloading tools or sources. A plugin warning fails the command; Exim
core warnings remain visible in build.log and are audited separately.

`make check test-sanitize` additionally checks formatting, clang-tidy, cppcheck,
standalone tests, shared protocol vectors, build-order regressions, patch
application, and ASan/UBSan on the standalone component. This is not a sanitizer
claim for the Exim executable.

## Corrections

The broad syntax patch 0004 has been removed in both releases, along with the
const-iteration and write-result cleanup in patch 0003. Upstream branch syntax,
macros and formatting are preserved. Remaining Exim diagnostics include ignored
write results, assignment conditions, dangling else, and a 4.99.5 const conversion.
They are not plugin warnings or compilation errors.

Only the two functional fixes in the 4.100.1 patch 0003 remain:

- `add_tls_info_for_log()` now returns its buffer even with `DISABLE_TLS`.
  Each 4.100.1 build extracts the actual patched function and compiles/runs a
  regression checking both NULL and a populated buffer with the selected compiler.
  The original function fails this test's strict compilation.
- `readconf_handle_option()` now negates the complete repeatability mask. Real
  Exim integration rejects duplicate singleton options and accepts repeatable
  conditions in both releases, plus repeatable headers in 4.100.1. The original
  4.100.1 executable incorrectly accepted the duplicate singleton test.

All changes are stored as versioned patches. Complete source manifests are checked
before and after builds; the reference trees have not been modified. See
[ADR 0004](adr/0004-compiler-diagnostics.md) for patch scope and maintenance costs.

The previous GNU make jobserver reset notices were eliminated by passing empty
MFLAGS on the Exim make invocation. Parallelism inherits MAKEFLAGS once; compiler
diagnostics are unaffected.
