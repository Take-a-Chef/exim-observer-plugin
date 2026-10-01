# Compatibility

Experimental. Tested milestone: dynamic module, native callback and handshake.
This table does not claim that the complete Observer feature set is supported.

| Exim    | GCC 16.2.1                       | Clang 23.1.2                     | Linux amd64 integration                                                                 |
| ------- | -------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------- |
| 4.99.5  | Full patched Exim + module built | Full patched Exim + module built | Module load, two-recipient SMTP acceptance/delivery, native delivery/complete callbacks |
| 4.100.1 | Full patched Exim + module built | Full patched Exim + module built | Same checks                                                                             |

Verified locally on 2026-09-30. Both integrations run with the agent absent and
with/without an administrator event_action. Existing expansion executes alongside
the module callback. Standalone handshake tests cover absent/malformed peers,
capability rejection, oversized ACKs, reconnection after full/partial peer closure,
closed-standard-stream descriptor isolation, preserved
errno and descriptor reinitialization after fork; ASan/UBSan pass.
Shared protocol canonical/malformed vectors pass. clang-tidy and cppcheck cover
the standalone socket component; the Exim-facing module has strict compiler
warnings, not a claimed complete Exim static-analysis or sanitizer audit.

## ABI and patches

Rebuild observer_miscmod.so with each version's generated headers/configuration.
The loader uses observer_module_info and checks MISC_MODULE_MAGIC. Original misc
ABI is MMM1 in both releases. The generic event extension uses private **OBS1**
(0x4f425331); rebuild **all** misc modules. It is not an upstream-assigned ABI.

Both version directories contain:

1. `0001-observer-module-options.patch`: readconf.c sorted aliases; opt_module for
   4.99.5, opt_misc_module for 4.100.1.
2. `0002-miscmod-event-hook.patch`: structs.h descriptor/magic, functions.h
   dispatcher declaration, drtables.c dispatcher, deliver.c central hook.

Only 4.100.1 additionally carries `0003-core-diagnostic-correctness.patch`, with
minimal fixes for the no-TLS return and duplicate-option mask precedence.
Style-only and warning-cleanup patches have been removed; upstream syntax is
preserved. See docs/adr/0004-compiler-diagnostics.md.

The event patch has identical added code; source context offsets differ. All
patches apply with zero fuzz to temporary copies. Original file hashes are checked
before and after each build. No static-module integration is implemented.

## Protocol and feature limits

The dependency revision is recorded in protocol.lock.json: experimental draft 0.1,
C reference codec and shared vectors. No duplicate wire constants. HELLO/ACK is the
only plugin wire exchange; application capabilities are empty. Wire stability and
plugin C API stability are distinct, both currently experimental.

Full lifecycle/queue schemas are missing from that draft. MESSAGE_ACCEPTED exists,
but its durable server-scoped sequence has no agreed nonblocking allocation
mechanism across Exim processes. A process-local counter would violate the contract.
No application event is emitted with fabricated identity. See docs/protocol.md.

Other constraints identified in the sources:

- Main daemon drops privileges; direct force delivery cannot generally replace
  Exim's normal re-exec privilege path.
- Queue listing is textual; its private scanner changed and allocates a full list.
- Central event_raise alone misses guarded defer/DNS/TLS/internal-failure calls.
- Tracking insertion must precede header commit; acceptance must follow data close.
- Cutthrough and blackhole reception need separate acceptance semantics.
- Exim 4.100.1 adds proc:deliver and changes debug/log APIs.

CI configuration is included, but no hosted CI run has been performed. The locked
protocol revision must be available in inode64/exim-observer-protocol before its
checkout step can succeed. Minimal integration builds disable TLS, DKIM, DNSSEC,
filters and optional authentication libraries; their behavior is not covered.

Compiler warnings are audited separately for the plugin and Exim core. See
[compiler audit](docs/compiler-audit.md): the plugin passes `-Werror` with both
compilers; Exim retains its upstream warnings without blanket `-Werror`.
Targeted regressions cover the no-TLS return and singleton/repeatable options.
