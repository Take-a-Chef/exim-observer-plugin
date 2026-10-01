# Changelog

Software version and wire-protocol version are independent. All work is experimental.

## Unreleased

### Added

- Strict GCC/Clang compiler matrix, separate module diagnostic logs and an audit
  distinguishing plugin results from patched Exim core results.
- Exact-source analysis of Exim 4.99.5 and 4.100.1, with immutable source manifests.
- Native C misc module, Exim configuration aliases and fail-open Unix handshake.
- Generic native event callback with private OBS1 ABI: all misc modules must rebuild.
- Full dual-version GCC/Clang build and real two-recipient SMTP/delivery tests.
- Shared C protocol vectors, standalone sanitizers/static analysis and CI definition.

### Changed

- Limit strict warning enforcement to the plugin; preserve upstream Exim syntax
  and report its diagnostics separately.

### Deprecated

- None.

### Removed

- Broad Exim control-flow and warning-cleanup patches; retain only the two
  targeted 4.100.1 correctness fixes alongside the Observer integration hooks.

### Fixed

- Exim 4.100.1 logging helper returns its buffer when TLS is disabled; duplicate
  singleton options are rejected without rejecting repeatable options.
- Avoid duplicate parallelism flags when invoking Exim recursive make.
- Make integration depend on a successful current build for every invocation,
  including parallel `make build integration` and keep-going mode.
- Keep observer sockets above descriptor 2 when Exim closes standard streams.
- Detect peer write-half shutdown after handshake instead of retaining a stale session.
- Reject disabled C/Python test assertions to prevent false successful test results.
- Detect agent disconnection after handshake and reconnect on the next callback.
- Count transport EOF separately from malformed protocol packets; preserve errno
  during explicit socket cleanup.
- Rebuild unit tests for compiler/flag changes; order build before integration
  under parallel make; preserve build logs during patch-only checks.

### Security

- Bounded nonblocking IPC, preserved errno and fork-aware descriptor reset.
- SHA-256-pinned source archives and complete source manifests.
