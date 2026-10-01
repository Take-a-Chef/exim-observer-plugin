# Keep protocol evolution separate from native integration

Status: accepted for the minimal module milestone.

## Context

Protocol draft 0.1 has six implemented messages; most requested plugin operations
are reserved without schemas. Its durable server-scoped sequence cannot be
implemented by an unpersisted per-process counter across Exim forks and restarts.

## Decision

Build and link the sibling C reference codec. Advertise zero application
capabilities in the minimal handshake. Implement no private frames and no phantom
queue/body/event support. Expand the protocol only through explicit specification,
registry, vector and validation changes in that repository. Initial plugin callbacks
remain fail-open and nonblocking, regardless of observer availability.

## Consequences

Module load and SMTP reliability can be verified now. Complete event transport and
queue operations remain pending the protocol contract, not hidden behind dummy
responses. The agent's WAL remains outside the Exim process.
