# Exim Observer Plugin

Experimental native C integration for Exim Observer. The first milestone provides
source analysis, a loadable misc module, a generic native event hook, a fail-open
Unix socket handshake, and a dual-version build/integration harness.

The inspected targets are **Exim 4.99.5 and 4.100.1**. This is not yet a production
observer: tracking headers, application event serialization, the control listener,
queue operations and message inspection are not implemented. The module advertises
**zero application capabilities**. See [compatibility](COMPATIBILITY.md).

Exim → native C plugin → Exim Observer Protocol → separate observer agent.
No Go runtime, HTTP service, database, WAL, or central processing runs inside Exim.
The protocol codec is a reviewed external C dependency, not a private wire format.

## Development

Place this checkout beside `exim-observer-protocol` at the revision recorded in
`protocol.lock.json`. Install the tools listed in [building](docs/building.md).
The provided read-only references are expected under the protocol checkout's
`.tools`; set `EXIM_SOURCE_ROOT` to change their location.

```sh
make test                 # local unit tests and shared protocol vectors
make check                # formatting, analysis, tests and patch application
make build integration EXIM_VERSION=4.99.5 CC=gcc
make build integration EXIM_VERSION=4.100.1 CC=clang
make check-all            # full checks, both releases and both compilers
make test-compilers       # unit/module warnings as errors and SMTP integration
make test-sanitize        # standalone ASan + UBSan
```

Ordinary builds and tests do not download anything. For a new developer/CI source
cache, explicitly run `make fetch-sources EXIM_SOURCE_ROOT=.tools`. Archives and
complete extracted manifests are verified before use. Supplied references are
never modified; patches apply to disposable copies.

The native loader requires `observer_miscmod.so`, exporting
`observer_module_info`. `build/<version>-<compiler>/exim-observer.so` is an alias.
Each binary is specific to the patched Exim build and its generated headers.

## Current behavior

`observer_enabled` defaults to false. Configuring it loads the module through Exim's
native module option mechanism. `observer_events_socket` defaults to
`/run/exim-observer/events.sock`. When enabled, callbacks attempt a nonblocking
SOCK_SEQPACKET HELLO/HELLO_ACK handshake using protocol draft 0.1. Failure never
changes an SMTP result. There is no listener in this milestone: the agent owns the
event socket, and no control socket is created yet.

Native `event_raise` calls notify the module even without event_action. With
`-d+load`, the module logs native event names only. Existing event_action expansion
continues unchanged. Some upstream call sites have additional guards, documented
in [events](docs/events.md); this is not complete lifecycle coverage.

## References

- [Exact source analysis and required patch sites](docs/exim-internals.md)
- [Architecture](docs/architecture.md), [protocol boundary](docs/protocol.md),
  [security](docs/security.md), [contribution process](CONTRIBUTING.md)
- [Exim Observer Protocol](https://github.com/Take-a-Chef/exim-observer-protocol)
- [Exim Observer](https://github.com/inode64/exim-observer)

Python is used only for build/test tooling. Runtime plugin and codec code are C.
