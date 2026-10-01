# Exim internals: inspected 4.99.5 and 4.100.1

Status: source analysis, before plugin implementation. References below are relative
to the immutable `exim-<version>/` reference trees. `scripts/source-manifest.json`
records SHA-256 for all 444 files in 4.99.5 and 458 in 4.100.1. This analysis is
about those exact trees, not upstream master. Build and runtime evidence belongs
in COMPATIBILITY.md; API inspection alone does not establish support.

## Misc modules, loading and ABI

| Subject              | Exim 4.99.5 file / symbol / behavior                                                                                                                                              | Exim 4.100.1 file / symbol / behavior                                                           | Compatibility                                                                                                   |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Module descriptor    | src/structs.h:1034, misc_module_info: next, name, dyn_magic, init, lib_vers_report, conn_init, smtp_reset, msg_init, authres, and options/functions/variables pointer-count pairs | src/structs.h:1029, misc_module_info: identical fields and ordering                             | Identical descriptor; not a guarantee of binary compatibility                                                   |
| Magic                | src/structs.h:1054, MISC_MODULE_MAGIC = 0x4d4d4d31 (MMM1)                                                                                                                         | src/structs.h:1050, same magic                                                                  | Identical; adding callbacks requires changing magic and rebuilding every misc module                            |
| Open library         | src/drtables.c:347, mod_open builds LOOKUP_MODULE_DIR/<name>_miscmod.so and uses dlopen(RTLD_NOW)                                                                                 | src/drtables.c:128, same naming and eager symbol resolution                                     | Compatible                                                                                                      |
| Find module          | src/drtables.c:460/506/517, misc_mod_load/findonly/find, looks up <name>_module_info, checks magic before adding to list                                                          | src/drtables.c:326/372/383, same dynamic behavior; missing static module checks errstr for NULL | Compatible for dynamic use; do not depend on the old NULL-error-pointer bug                                     |
| Initialize           | src/drtables.c:434, misc_mod_add links descriptor then calls init; init failure is only debugged, not removed from list                                                           | src/drtables.c:300, same lifecycle                                                              | Compatible; init runs before the triggering option is assigned, so it cannot validate final config              |
| Dispatch             | src/drtables.c:533/546/556, misc_mod_conn_init/smtp_reset/msg_init visit the loaded list; FAIL in conn_init/msg_init affects mail processing                                      | src/drtables.c:401/414/424, same semantics                                                      | Compatible; Observer callbacks must always return OK                                                            |
| Module config        | src/readconf.c:2514, opt_module loads module, then searches its sorted option table; options require sorted aliases in optionlist_config                                          | src/readconf.c:2518, opt_misc_module; separate opt_lookup_module added                          | Changed; version-specific alias patches, common module option table                                             |
| Static/dynamic build | src/miscmods/README, scripts/Configure-Makefile and scripts/Makelinks, SUPPORT_<name>=yes or 2; static registration in drtables.c                                                 | same files, same public module convention; driver availability tables refactored                | Compatible convention; initial plugin is an external dynamic module, no static registration patch               |
| Debug/log API        | src/macros.h DEBUG(D_any); src/local_scan.h:205 log_write(unsigned selector, int flags, format, ...)                                                                              | src/macros.h DEBUG(any); src/local_scan.h:215 log_write(int flags, format, ...)                 | Incompatible source syntax/signature; isolate debug selection in one compat header; avoid an unused log wrapper |

The required loader filename is **observer_miscmod.so**, with exported descriptor
**observer_module_info**. An exim-observer.so artifact can be an alias, but Exim
will not load that name merely because it exists. Modules must be built against
the headers/configuration of their target Exim. No universal .so is promised.

## Native events and call-site guards

| Subject          | Exim 4.99.5 file / symbol / behavior                                                                                                                                                                                                                   | Exim 4.100.1 file / symbol / behavior                                                    | Compatibility                                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Central dispatch | src/deliver.c:860, event_raise(action,event,data,errnop): does nothing without action; otherwise temporarily sets event_name/data, expands action, logs expansion failures, clears globals, returns nonempty expansion and optionally sets ERRNO_EVENT | src/deliver.c:844, same contract, new debug/log APIs                                     | Compatible behavior; add void misc dispatch before the action guard, preserve errno and native return behavior           |
| Message context  | src/deliver.c:898, msg_event_raise: temporarily sets routing/recipient/host expansion globals; uses transport event_action; converts no-transport delivery failure to internal failure                                                                 | src/deliver.c:882, same behavior                                                         | Compatible; consume pointers synchronously and copy bounded data only                                                    |
| Delivery start   | src/deliver.c:6730, deliver_message: no proc:deliver event                                                                                                                                                                                             | src/deliver.c:6797, event_raise(event_action,"proc:deliver",id,NULL) before CONTINUED_ID | Changed; 4.99 needs a small matching hook; neither call means successful delivery or even acquisition of a spool lock    |
| Defer helper     | src/transports/smtp.c:708, deferred_event_raise returns immediately if transport event_action is NULL                                                                                                                                                  | same helper in src/transports/smtp.c, same early return                                  | Compatible but central hook alone misses these events; guard must also account for module listeners                      |
| Internal failure | src/deliver.c:7469 and src/queue.c:1458 guard failure emission on event_action                                                                                                                                                                         | corresponding deliver.c/queue.c paths have the same guards                               | Compatible; listener-aware guards needed                                                                                 |
| DNS and TLS      | src/dns.c not_good block only calls dns:fail if action set; src/tls-openssl.c verify_event requires action; tls-gnu.c installs verification callbacks conditionally                                                                                    | same guards in corresponding files                                                       | Compatible limitation; audit callback registration as well as event_raise calls before claiming independent TLS coverage |

Both trees contain these named events: auth:fail, dane:fail, dns:fail,
msg:complete, msg:defer, msg:delivery, msg:fail:delivery, msg:fail:internal,
msg:host:defer, msg:rcpt:defer, msg:rcpt:host:defer, smtp:connect, smtp:ehlo,
smtp:fail:protocol, smtp:fail:syntax, tcp:close, tcp:connect, tls:cert,
and tls:fail:connect. 4.100.1 additionally contains proc:deliver.

smtp:connect and smtp:ehlo in transports/smtp.c are **outbound** transport events,
not incoming SMTP reception. msg:delivery is raised per successful address;
msg:complete is message-level and follows spool deletion. Transport host/recipient
deferrals are different scopes and must not collapse all recipients into one state.
The central msg:defer call is in the SMTP transport; it is not a universal local
transport/router deferral event. No received/accepted/rejected/recipient-added or
freeze/thaw lifecycle event is present under those names.

## Reception, IDs, headers and acceptance

| Subject             | Exim 4.99.5 file / symbol / behavior                                                                                                             | Exim 4.100.1 file / symbol / behavior                       | Compatibility                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Receive entry       | src/receive.c:1706 receive_msg; clears message_id; misc_mod_msg_init at 1833 occurs before reading all headers                                   | src/receive.c:1919 receive_msg; msg_init at 2029            | Changed input internals; same lifecycle constraint: msg_init cannot implement tracking-header lookup              |
| ID creation         | src/receive.c:2785 onward fills message_id from time/PID/subtime before opening the -D spool                                                     | src/receive.c:2982 onward, same encoding                    | Compatible                                                                                                        |
| ID grammar          | src/local_scan.h:114–123: current 6-11-4 base62 components (23 bytes), old 6-6-2 (16 bytes); src/exim.c:2236 regex_ismsgid; macros.h mac_ismsgid | same constants; src/exim.c:2110 same anchored regex         | Identical on Linux; accept both historical and current forms, reject path/control characters before internal APIs |
| Recipients          | src/receive.c:517 receive_add_recipient adds recipient_item entries with address, parent and DSN data; DATA ACL/local_scan may remove recipients | src/receive.c:675, same role                                | Compatible; do not assume RCPT-time list equals final accepted list                                               |
| Header manipulation | src/header.c:33 header_testname, :258 header_add, :284 header_remove; removed headers are marked '*'                                             | same symbols/locations                                      | Compatible; add tracking after final ACL/local_scan changes and before spool_write_header                         |
| Header commit       | src/receive.c:4027 spool_write_header(...,SW_RECEIVING,...); skip for host_checking or blackhole                                                 | src/receive.c:4208 same decision                            | Compatible; too early for final MESSAGE_ACCEPTED                                                                  |
| Data durability     | receive.c after header write calls fflush and fdatasync; failure rejects SMTP or exits local submission                                          | same path after header write                                | Compatible; Observer adds no fsync                                                                                |
| Final close         | src/receive.c:4436 TIDYUP, fclose at 4442 can rescind logged acceptance, remove spool files and clear message_id                                 | src/receive.c:4619 TIDYUP, fclose at 4625 has same behavior | Compatible; accepted hook must be after successful close and before header reset                                  |
| Header lifetime     | receive.c tail sets header_list/header_last to NULL before returning                                                                             | same tail                                                   | Compatible; all event metadata must be copied/encoded before this point                                           |

The safe initial acceptance hook is after TIDYUP closes a normal spool, gated on
nonempty message_id, no host_checking, no blackhole, and cutthrough_done == NOT_TRIED.
It observes responsibility for a successfully spooled message, even with an ACL
fake rejection; do not equate wire SMTP response codes with spool acceptance.
Cutthrough and accepted-and-discarded messages need separate, explicitly documented
semantics before claiming complete reception coverage. A failed close must never
emit accepted. Tracking must be inserted before header commit, not in accepted
notification; otherwise it would not be persisted for delivery processes.

Already-available globals include sender_address, sender_host_address/port,
sender_helo_name, authenticated_id/sender, message_size, message_id, recipients_list,
received_time, header_list and tls_in when TLS is compiled. RFC Message-ID and
Content-Type can be located in header_list without body parsing. Native event
context includes deliver_localpart/domain, router_name, transport_name,
deliver_host/address/port and diagnostics; never treat a NULL or stale global as
proof of structured metadata. msg_event_raise does not populate every host field.

## Queue and delivery APIs

| Subject          | Exim 4.99.5 file / symbol / behavior                                                                                                                                                                   | Exim 4.100.1 file / symbol / behavior                                                                | Compatibility                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Count            | src/queue.c:937 unsigned queue_count(void), scans via queue_get_spool_list count-only mode                                                                                                             | src/queue.c:966, same public API                                                                     | Compatible; O(queue size), use a bounded worker context, not the daemon's poll loop                                                   |
| List             | src/queue.c:1014 queue_list(int,const uschar **,int) prints human output and reads headers                                                                                                             | src/queue.c:1043 same public signature/output purpose                                                | Compatible but unsuitable as a structured paginated protocol API                                                                      |
| Internal scanner | src/queue.c:128 static queue_get_spool_list(...,BOOL randomize,unsigned *pcount), allocates linked list when not counting                                                                              | src/queue.c:131 static queue_get_spool_list(...,s_order_t order,unsigned *pcount), adds newest-first | Changed and non-exported; simply exporting it would still allocate an unbounded queue list; design a bounded scanner/cursor API later |
| Mutation         | src/queue.c:1192 BOOL queue_action(id,action,argv,argc,recipients_arg): sets global message_id, opens/locks data, reads headers, checks permissions, prints outcomes, mutates via Exim spool functions | src/queue.c:1221 same contract                                                                       | Compatible; invoke in an isolated child, not a stateful daemon; BOOL/stdout do not provide a typed reason for every failure           |
| Freeze/thaw      | queue_action MSG_FREEZE/MSG_THAW update f.deliver_freeze/manual_thaw and spool_write_header(SW_MODIFYING); already-in-state returns FALSE                                                              | same cases                                                                                           | Compatible; idempotent protocol semantics must be defined rather than inferred                                                        |
| Remove           | queue_action MSG_REMOVE closes out data/header/journal/log files, handles broken spool cases and ownership, raises failure/complete under guards                                                       | same behavior                                                                                        | Compatible; do not duplicate unlink logic in the plugin                                                                               |
| Delivery         | src/deliver.c:6730 int deliver_message(id,forced,give_up), owns an entire process and may chain messages                                                                                               | src/deliver.c:6786 same public contract plus proc:deliver                                            | Compatible call; false/false respects normal retries; true/false bypasses retry timing but still uses native eligibility/lock checks  |
| Fork helper      | src/functions.h:1408 exim_fork sets daemon_listen false and process_purpose in child; does not close arbitrary module FDs or establish worker credentials                                              | src/functions.h:1424 same behavior, different debug macros                                           | Compatible; needs explicit FD, signal and child-reaping integration                                                                   |

Do not pre-lock a message and then call queue_action/deliver_message: they acquire
their own data-file locks. queue_action permits freeze/thaw only for f.admin_user;
non-admin removal is restricted to real_uid == originator_uid. Do not set admin
flags merely because a control client connected. MSG_SHOW_* paths stream raw spool
files to stdout and should not serve as a structured header/body API.

## Spool reading and locking

| Subject        | Exim 4.99.5 file / symbol / behavior                                                                                                                            | Exim 4.100.1 file / symbol / behavior             | Compatibility                                                                                                             |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Data file/lock | src/spool_in.c:39 spool_open_datafile(id), tries split/unsplit paths, O_RDWR/O_APPEND plus CLOEXEC/NOFOLLOW, nonblocking fcntl F_SETLK over the initial ID line | same symbol and behavior                          | Compatible; -1 with errno==0 means lock conflict, ENOENT missing; owns deliver_datafile only if caller assigns it         |
| Header parser  | src/spool_in.c:377 spool_read_header(fname,read_headers,subdir_set), parses metadata/recipients and optionally header_line list into global state               | src/spool_in.c:370 same signature/global behavior | Compatible; use isolated worker/store context; parse failure is not necessarily absence                                   |
| Header rewrite | src/spool_out.c spool_write_header writes temporary file, syncs, closes, renames, syncs directory                                                               | same entry point and durable replacement pattern  | Compatible; never hand-edit -H                                                                                            |
| Body offset    | functions.h spool_data_start_offset(id) distinguishes old/current IDs; body data is -D content after Exim's leading ID line                                     | same helpers                                      | Compatible; bounded pread after offset validation, no arbitrary peer allocation                                           |
| Paths/logs     | functions.h spool_fname/set_subdir_str; queue_action MSG_SHOW_LOG locates msglog file; message_logs may disable creation                                        | same helpers and MSG_SHOW_LOG branch              | Compatible; no separate public bounded log-reader API; future justified NOFOLLOW bounded reads must use Exim path helpers |

The stable mutation lock is on -D because -H is atomically replaced. Closing a
second descriptor for the same inode can affect process-associated fcntl locks;
avoid extra opens/closes in a process holding a delivery lock. Inspection needs
its own worker to avoid corrupting delivery globals or locks. Header-only
inspection can race removal; report a stable protocol error, not a crash.

## Daemon, listener ownership, forks and privileges

| Subject            | Exim 4.99.5 file / symbol / behavior                                                                                                            | Exim 4.100.1 file / symbol / behavior             | Compatibility                                                                                                                                                          |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Main loop          | src/daemon.c:1697 daemon_go, poll(fd_polls,poll_fd_count,-1) inside daemon_listen branch; queue-only mode polls zero descriptors with a timeout | src/daemon.c:1723, same layout                    | Compatible; queue-only mode must be explicitly included or documented unsupported for control                                                                          |
| Poll storage       | daemon_go allocates 3 entries initially, then listen_socket_count+2 for SMTP plus TLS watch and notifier                                        | same fixed spare capacity                         | Compatible; cannot append arbitrary module FDs without resizing safely                                                                                                 |
| Ancillary dispatch | daemon.c around 2562–2714 installs/handles tls_watch_fd and daemon_notifier_fd separately from SMTP accept descriptors                          | corresponding daemon.c block around 2622 onward   | Compatible model for a module poll range; never send module descriptors through accept's SMTP path                                                                     |
| FD cleanup         | src/daemon.c:151 close_daemon_sockets, called in SMTP child, queue-runner paths and SIGHUP restart                                              | src/daemon.c:152, same responsibility             | Compatible; add module close callback with parent/child distinction; a child must not unlink parent's socket                                                           |
| Privileges         | daemon.c:2375 exim_setugid drops to exim_uid/exim_gid before main loop; SMTP children inherit these credentials                                 | daemon.c:2405 same                                | Compatible; control socket should be owned by the long-running daemon after drop, in an administrator-provisioned directory                                            |
| Delivery privilege | daemon.c around 700 forks delivery child; if not root and !deliver_drop_privilege it re-execs Exim to regain required privilege                 | corresponding handle_smtp_call path               | Compatible constraint: direct delivery from an Exim-user control worker is safe only with deliver_drop_privilege or an independently reviewed privileged-worker design |
| Child cleanup      | src/daemon.c:880 handle_ending_processes reaps children and updates SMTP/queue-runner counts; daemon_die handles shutdown                       | src/daemon.c:883 and :1113, analogous bookkeeping | Compatible but additional worker PID accounting is necessary                                                                                                           |

A prospective generic module extension should expose a bounded poll registration,
readiness dispatch, and cleanup/fork notification, initialized only by daemon_go.
Do not create the listener in module init or each SMTP child. Listener and accepted
peers must be nonblocking, CLOEXEC and credential-checked with SO_PEERCRED. Bound
client count, work per poll iteration and outstanding workers. Expensive queue
scans/delivery must never run synchronously in this loop. No pthread is needed.

The prohibition on invoking the Exim executable rules out copying the daemon's
normal privilege-regaining re-exec path into Observer. Advertise delivery-control
capabilities only when the current configuration/context can safely execute them;
do not circumvent the native privilege model.

## Patch plan and minimum compatibility layer

1. `src/readconf.c`: sorted Observer option aliases following existing misc-module
   conventions. Only the alias type differs: opt_module vs opt_misc_module.
   No second configuration parser is needed. This is the sole patch needed to
   load/configure an externally built minimal module.
2. For event dispatch: `src/structs.h` (append void callback, new local ABI magic),
   `src/functions.h` (dispatch/listener declarations), `src/drtables.c` (dispatch
   loaded callbacks), `src/deliver.c` (call before native action guard). Preserve
   errno around observers. Existing action return/errnop behavior stays intact.
3. To remove gated event blind spots: `src/transports/smtp.c`, `src/dns.c`,
   `src/queue.c`, `src/deliver.c`, and TLS backend registration/verify guards in
   `src/tls-openssl.c` / `src/tls-gnu.c`. Apply only scoped listener-aware changes,
   never an unrelated formatting pass. TLS remains unclaimed until tested.
4. Later lifecycle hooks: `src/receive.c` needs a pre-spool header callback and a
   separately gated post-close acceptance notification. Recipient/rejection and
   local-defer coverage require distinct audited hooks. Freeze/thaw notification
   belongs after successful queue_action writes. Backport proc:deliver to 4.99
   only if needed; do not duplicate 4.100's event.
5. Later daemon integration: `src/daemon.c`, `src/structs.h`, `src/functions.h`,
   `src/drtables.c`, with explicit poll capacity and lifecycle accounting.
6. Later bounded queue iteration: `src/queue.c` / `src/functions.h`; current
   static scanner cannot satisfy bounded pagination unchanged.

Only the initial debug macro adaptation is needed in src/compat/compat.h. The
module descriptor is common; options differ in patches, not scattered #ifs.
Do not add queue/message wrappers until a protocol schema and worker model exist.

## Protocol boundary discovered during analysis

The sibling protocol draft 0.1 defines HELLO, HELLO_ACK, ERROR, MESSAGE_ACCEPTED,
QUEUE_COUNT and its response. Other event/command IDs are reserved, without payload
schemas, response semantics, pagination or chunking. It also requires a durable
server-scoped event sequence; a PID-local counter is not conformant. The plugin
must not silently replace that identity with a process-local sequence.

Initial module loading, configuration, fail-open IPC and native callback tests can
be proven without inventing wire fields. Full event forwarding/control require
reviewed changes to the protocol project, including replay identity/transport
negotiation appropriate to many short-lived Exim processes. No feature is supported
merely because its numeric ID is reserved. Minimal handshake advertises zero
application capabilities until those implementations are ready.

## Implemented milestone follow-up

The initial source analysis above records pristine upstream behavior. The current
integration patches implement readconf option aliases and the central generic event
callback. They append the callback and change MMM1 to private OBS1, retaining
the loader's compatibility check. The dispatcher preserves errno and runs before
native event_action expansion. Guarded call sites remain explicitly incomplete.
The sole source wrapper handles debug selection: D_load in 4.99.5, and the const-safe
ANY_DEBUG/is_debug("load") equivalent in 4.100.1. Full compiler and runtime evidence
is recorded in COMPATIBILITY.md. No queue, spool mutation or daemon hook is added.

### Standard descriptors during delivery

Exim 4.99.5: src/exim.c:716, close_unwanted(), called before delivery at line 6323.
Exim 4.100.1: src/exim.c:724, close_unwanted(), called at line 6277. Both close
SMTP descriptors or standard input/output, and sometimes standard error depending
on debug and synchronous-delivery state. Behavior is compatible; debug syntax
changed. Therefore a later socket() may return 0, 1 or 2. The plugin relocates any
such descriptor above STDERR_FILENO before connecting, preserving NONBLOCK and
CLOEXEC. A forked unit test closes all three standard descriptors and verifies they
remain closed while the observer completes its initial nonblocking send.

### Compiler-diagnostic corrections

Exim 4.100.1: `src/smtp_in.c`, `add_tls_info_for_log()`, places its return inside
`#ifndef DISABLE_TLS`; callers still use its result in the minimal build. The patch
returns the incoming buffer unchanged when TLS is disabled. Exim 4.99.5 does not
have this helper. Compatibility: version-specific correctness patch.

Exim 4.100.1: `src/readconf.c`, `readconf_handle_option()`, tests repeated options with
`!ol->type & (opt_rep_con | opt_rep_str)`, negating before masking. The patch tests
`!(ol->type & (opt_rep_con | opt_rep_str))`. Integration verifies singleton rejection
and repeated condition/header acceptance. Exim 4.99.5 uses its older condition-only
repetition test and passes the corresponding integration cases unchanged.

The earlier warning-cleanup patches for const iteration, best-effort writes and
control-flow syntax have been withdrawn. Exim's existing braces, macros and
assignment conditions are preserved. Only the two functional 4.100.1 fixes above
remain in patch 0003; Exim 4.99.5 needs only the Observer integration patches.
Upstream diagnostics are recorded separately from strict plugin results.
