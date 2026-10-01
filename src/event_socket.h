/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef OBSERVER_EVENT_SOCKET_H
#define OBSERVER_EVENT_SOCKET_H
#include <stdbool.h>
#include <stdint.h>
#include <sys/types.h>

/* Per-process state. Never shares a connected socket with a forked child. */
typedef struct {
    int fd;
    pid_t owner;
    bool ready;
    uint64_t unavailable;
    uint64_t protocol_errors;
} observer_event_socket;
#define OBSERVER_EVENT_SOCKET_INIT {.fd = -1}

bool observer_socket_path_valid(const char *path);
/* One bounded, nonblocking handshake/liveness step; preserves errno.
 * Path is immutable for a session; close explicitly before changing it. */
void observer_socket_step(observer_event_socket *state, const char *path);
/* Idempotent local close; preserves errno and retains diagnostic counters. */
void observer_socket_close(observer_event_socket *state);
#endif
