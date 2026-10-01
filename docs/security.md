# Security boundaries

Treat SMTP headers, Exim metadata and local socket bytes as untrusted. The module
uses the shared bounded protocol decoder, does not expose pointers or Exim layouts,
and does not allocate according to peer lengths. The handshake receive buffer is
bounded by the shared maximum. There are no control commands or message reads.

Nonblocking event failure must leave SMTP acceptance and delivery unchanged. Native
callbacks return OK or void; counters replace repeated normal logging. Debug event
names are native constants; message content is not logged by Observer.

The agent owns events.sock. Production runtime directories must have controlled
ownership and permissions. The minimal event client does not yet authenticate the
server's credentials and sends only a zero-capability HELLO. Peer verification is
required before adding sensitive application event payloads. A future control
listener must enforce SO_PEERCRED and an explicit UID/GID policy before requests.

Do not install these test binaries setuid or run integration against a real spool.
Test configurations deliberately accept all recipients in their private stdio SMTP
session. The minimal build disables TLS and optional modules; it is not an MTA
installation recipe. Reference sources and protocol revision are checksum/revision
checked. All modules must be rebuilt for the private OBS1 ABI; magic checks are
not bypassed.
