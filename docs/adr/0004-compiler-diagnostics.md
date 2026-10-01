# Keep Exim patches minimal and preserve upstream syntax

Status: revised after review; supersedes the initial blanket warning-cleanup policy.

## Context

The plugin must remain small and easy to maintain across Exim releases. The
previous attempt to remove every upstream compiler warning introduced broad
control-flow edits unrelated to Observer. Even behavior-preserving syntax changes
increase review and rebase costs and do not belong in the integration patch set.

## Decision

Remove patch 0004 in both versions. Restore upstream braces, assignment conditions,
empty bodies and EARLY_DEBUG macros. Remove the const-iteration and best-effort
write changes from patch 0003 as well.

Keep the two small functional fixes in Exim 4.100.1: return the logging buffer with
TLS disabled, and negate the complete repeatability mask when checking duplicate
options. These retain upstream formatting and have targeted regression tests.
Exim 4.99.5 now carries only the Observer configuration and event-hook patches.

Require strict warnings and -Werror for the plugin and its codec. Build full Exim
with upstream warning settings without blanket -Werror. Keep its diagnostics
visible in build.log and report them separately from module.log. Do not add warning
suppression or reformat upstream code merely to claim zero warnings.

## Validation

Run `make test-compilers` to build both complete releases and their modules with
GCC and Clang and exercise real SMTP acceptance/delivery and native callbacks.
The no-TLS regression and singleton/repeatable option tests remain required.
Use `make check` for formatting, standalone static analysis, shared vectors and
zero-fuzz patch application. Compiler counts are recorded in ../compiler-audit.md.
Reference trees remain read-only and are checked against full source manifests.
