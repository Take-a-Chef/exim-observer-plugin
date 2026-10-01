# Native events

The generic patch calls misc_mod_event before event_raise's action guard. The
callback is synchronous, cannot return a mail-processing decision and preserves
errno. Exim's original event_action expansion and return value remain unchanged.
Callbacks must not retain strings, change global mail state or recurse.

Real two-recipient appendfile delivery tests verify two msg:delivery callbacks and
one msg:complete callback, with and without event_action, for both releases and
both compilers. Debug output contains event names only, under `-d+load`. These are
native callback observations, not encoded Observer events.

| Native event                          | Intended future Observer mapping     | Current wire support |
| ------------------------------------- | ------------------------------------ | -------------------- |
| msg:delivery                          | DELIVERY_SUCCESS, per recipient      | Not implemented      |
| msg:defer / msg:rcpt:defer            | DELIVERY_DEFER, preserve scope       | Not implemented      |
| msg:host:defer / msg:rcpt:host:defer  | Host attempt diagnostics             | Contract pending     |
| msg:fail:delivery / msg:fail:internal | DELIVERY_FAIL, distinguish origin    | Not implemented      |
| msg:complete                          | MESSAGE_COMPLETE                     | Not implemented      |
| proc:deliver (4.100.1 only)           | Process start, not proof of delivery | Contract pending     |
| auth/dns/tcp/smtp/tls events          | Preserve native category and scope   | Contract pending     |

`event_raise` does not cover calls suppressed by upstream action guards. SMTP defer
helpers, DNS, internal failures and TLS callback registration need additional
listener-aware changes. See exact locations in exim-internals.md. No claim of
complete native event coverage is made.

MESSAGE_ACCEPTED requires a separate reception hook after the successful final
spool data close, before header-list reset; header commit alone can still be
followed by rejection. Tracking insertion must occur before spool header commit.
Blackhole, cutthrough and fake SMTP rejection need explicit distinct semantics.
No extra reception patch has been added at this milestone.
