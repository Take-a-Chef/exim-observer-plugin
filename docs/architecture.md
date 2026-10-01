# Architecture at the initial milestone

Exim's dynamic misc-module loader owns the module descriptor and native options.
A generic void callback observes event_raise synchronously. Borrowed Exim pointers
are never retained or serialized as native structures. The event socket helper is
independent of Exim headers and tested against the real protocol C codec.

The helper uses SOCK_SEQPACKET with NONBLOCK/CLOEXEC and MSG_NOSIGNAL. Socket
descriptors are relocated above 2 with F_DUPFD_CLOEXEC when standard streams are
closed, so Exim stdio redirection cannot overwrite an observer socket. A callback
performs at most one connect, one HELLO send and one ACK receive; it never waits or
loops for a peer. Failures close the connection and update process-local counters.
errno is preserved. PID changes close inherited descriptors and reset connection
state. SMTP reset closes the connection. No thread, filesystem sync, DNS, HTTP,
SQL or remote network activity is introduced by the observer event path.

The first milestone negotiates no application capabilities. A successful handshake
is not evidence that any event reached the agent. No observer durability or replay
is claimed. After handshake, each callback checks connection liveness with a
zero-timeout poll without consuming application data. POLLRDHUP detects peer
write-half shutdown as well as full closure. Peer closure clears the
session; the next callback attempts a fresh handshake. Disconnects increment the
unavailable counter, while malformed ACKs increment protocol_errors. Both stepping
and explicitly closing the socket preserve errno. Application-send backpressure
and drop behavior still require dedicated implementation and tests.

The source layout intentionally contains only implemented components: observer.c,
event_socket.c and compat/compat.h. Empty queue/message/control modules would hide
their missing contracts, so they are not created. Protocol implementation remains
in its own C repository. Python scripts are developer tooling, not embedded code.

The future control path must have one daemon-owned listener, peer credentials and
bounded worker execution; it must not share long operations with the event path.
The daemon's privilege drop and fork cleanup are documented in exim-internals.md.
