# Generic synchronous misc-module event notification

Status: implemented; runtime matrix verification in COMPATIBILITY.md.

## Decision

Append a const, void-returning event callback to misc_module_info. Dispatch before
`event_raise` tests event_action; retain the original expansion, globals, errors and
return path. Save/restore errno around listeners. Strings are borrowed only during
the call. Callbacks must not change Exim globals, recurse or delay mail processing.

The extended layout uses private magic 0x4f425331 (OBS1), not upstream MMM1. Rebuild
all misc modules with patched headers. The unchanged loader rejects an old magic
before reading the new field. This is a local ABI, not an upstream ABI assignment.

The Observer callback currently advances the nonblocking handshake and reports
native event names under Exim's load debug selector. It sends no application events.
This proves the integration point without inventing protocol payloads or sequence
numbers. No event_action configuration is needed for calls that reach event_raise.

## Limits

This patch does not remove the call-site guards identified in exim-internals.md.
TLS/DNS/SMTP defer/internal failure coverage is therefore incomplete. No reception
acceptance hook, tracking insertion, queue operation or daemon FD callback is added.
Those changes require their own semantics and integration tests.
