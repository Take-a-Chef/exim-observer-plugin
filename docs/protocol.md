# Protocol dependency and unresolved integration contracts

Use the C codec, public/generated headers and canonical vectors from the exact
revision in protocol.lock.json. All multibyte values and framing are encoded by
that codec; no wire structs or locally invented constants are sent. Current plugin
traffic is HELLO followed by validation of HELLO_ACK for draft 0.1 with capabilities
zero. Frames are bounded by the protocol maximum before decoding. Unknown optional
fields follow the shared codec's compatibility rules. Unexpected ACK capabilities,
version, type or malformed payload close the connection without affecting mail.

## Contracts needed before application events and control

The current protocol implements HELLO, HELLO_ACK, ERROR, MESSAGE_ACCEPTED,
QUEUE_COUNT and QUEUE_COUNT_RESPONSE. Other requested IDs are reservations, not
message schemas. Reservations are insufficient to implement queue pagination,
message chunks, recipient lifecycle or authentication/capability semantics.

The existing event identity requires durable server_id + monotonic sequence,
including replay/restart behavior. Exim's multiple processes cannot meet that
requirement with PID/time/random/per-process counters. Blocking on a shared durable
allocator in the SMTP path would violate fail-open, no-fsync requirements.

A protocol decision must specify whether a separately identified producer-ingress
message lets the agent assign WAL sequences, or how sequence ranges are safely
allocated without blocking Exim. It also needs event/request fields, size limits,
unknown-capability behavior and canonical C fixtures for every new operation.
Neither alternative is silently implemented here. Tracking UUIDs alone do not
replace the sequence rule in the current contract.

These decisions belong in the independent protocol repository with spec, registry,
codec, vectors and compatibility tests updated together. Until then the plugin
advertises no application capabilities and implements no control listener.
