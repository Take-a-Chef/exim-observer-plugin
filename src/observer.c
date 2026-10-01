/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "exim.h" /* Must establish platform feature macros before system headers. */

#include "compat/compat.h"
#include "event_socket.h"

static BOOL observer_enabled = FALSE;
static uschar default_events_socket[] = "/run/exim-observer/events.sock";
static uschar *observer_events_socket = default_events_socket;
static observer_event_socket events = OBSERVER_EVENT_SOCKET_INIT;

static BOOL observer_init(void *info) {
    (void)info;
    /* Config assignment follows this callback; no socket or spool access here. */
    OBSERVER_DEBUG debug_printf("Observer: module initialized (minimal, capabilities=0)\n");
    return TRUE;
}

static int observer_msg_init(void) {
    if (observer_enabled)
        observer_socket_step(&events, (const char *)observer_events_socket);
    return OK;
}

static int observer_conn_init(const uschar *helo, const uschar *address, const uschar **error) {
    (void)helo;
    (void)address;
    (void)error;
    return observer_msg_init();
}

static void observer_native_event(const uschar *event, const uschar *data) {
    (void)data;
    if (!observer_enabled)
        return;
    observer_socket_step(&events, (const char *)observer_events_socket);
    /* Diagnostic only: no message content and no protocol event claims. */
    OBSERVER_DEBUG debug_printf("Observer: native event %s\n", event);
}

static void observer_smtp_reset(void) {
    /* Close promptly on RSET/new transaction; never retain message data. */
    observer_socket_close(&events);
}

static optionlist observer_options[] = {
    {"observer_enabled", opt_bool, {&observer_enabled}},
    {"observer_events_socket", opt_stringptr, {&observer_events_socket}},
};

/* Required native loader symbol. Unused optional callbacks remain NULL. */
misc_module_info observer_module_info = {
    .name = CUS "observer",
    .dyn_magic = MISC_MODULE_MAGIC,
    .init = observer_init,
    .conn_init = observer_conn_init,
    .smtp_reset = observer_smtp_reset,
    .msg_init = observer_msg_init,
    .event = observer_native_event,
    .options = observer_options,
    .options_count = sizeof(observer_options) / sizeof(observer_options[0]),
};
