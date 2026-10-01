# Contributing

Read docs/exim-internals.md before touching Exim integration. Reference source trees
are immutable: update only patches and apply them to disposable copies. Keep
upstream context/style and split unrelated changes into separate patches/commits.
Limit core changes to necessary integration hooks and demonstrated correctness
fixes. Do not change upstream braces, macros or formatting just to remove compiler
warnings. Enforce strict warnings on plugin code and report Exim diagnostics
separately; preserve Exim's original syntax wherever no functional change is needed.

Install the tools in docs/building.md. Run `make format`, `make check`, `make
check-all` and `make test-sanitize`. Shared protocol vectors are mandatory. Never
use a host spool or system Exim for tests. C code is C11 with explicit ownership,
bounded buffers and strong warnings; no Go runtime or agent/server functionality.

Document every new internal dependency for both exact releases. A passing module
compile is insufficient: build full Exim, load the module, exercise real SMTP and
verify that agent failure cannot change mail processing. New control operations
need privilege, race/locking, malformed-input and isolated spool tests.

Protocol changes belong in the protocol repository and require specification,
registry, C codec, valid/invalid vectors and compatibility updates together. Update
protocol.lock.json only after that review; never assign private conflicting fields.
Record ABI, acceptance, security or privilege decisions in docs/adr. Do not claim
coverage or production support for untested behavior.
