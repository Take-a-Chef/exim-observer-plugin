/* SPDX-License-Identifier: GPL-2.0-or-later */
// NOLINTNEXTLINE(bugprone-reserved-identifier): glibc feature-test macro.
#define _GNU_SOURCE
#include "event_socket.h"
#include "exim_observer_protocol.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stddef.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

bool observer_socket_path_valid(const char *path) {
    if (path == NULL || path[0] != '/')
        return false;
    const size_t limit = sizeof(((struct sockaddr_un *)0)->sun_path);
    const size_t n = strnlen(path, limit);
    if (n == 0 || n >= limit)
        return false;
    for (size_t i = 0; i < n; ++i)
        if ((unsigned char)path[i] < 32 || (unsigned char)path[i] == 127)
            return false;
    return true;
}

void observer_socket_close(observer_event_socket *state) {
    const int saved_errno = errno;
    if (state->fd >= 0)
        (void)close(state->fd);
    state->fd = -1;
    state->ready = false;
    errno = saved_errno;
}

static bool send_hello(int fd) {
    const uint8_t version[] = {EXOB_MAJOR, EXOB_MINOR};
    const uint8_t capabilities[8] = {0};
    exob_frame frame = {.version = {EXOB_MAJOR, EXOB_MINOR},
                        .type = EXOB_MSG_HELLO,
                        .field_count = 3,
                        .fields = {{EXOB_FIELD_MIN_VERSION, 2, version},
                                   {EXOB_FIELD_MAX_VERSION, 2, version},
                                   {EXOB_FIELD_CAPABILITIES, 8, capabilities}}};
    uint8_t wire[64];
    size_t length = 0;
    if (exob_encode(&frame, wire, sizeof(wire), &length) != EXOB_ERROR_OK)
        return false;
    const ssize_t sent = send(fd, wire, length, MSG_DONTWAIT | MSG_NOSIGNAL);
    return sent >= 0 && (size_t)sent == length;
}

/* Validation borrows the packet only for this call; no socket state is changed. */
static bool valid_ack(const uint8_t *wire, size_t length) {
    exob_frame frame;
    if (exob_decode(wire, length, &frame) != EXOB_ERROR_OK || frame.type != EXOB_MSG_HELLO_ACK ||
        frame.version.major != EXOB_MAJOR || frame.version.minor != EXOB_MINOR)
        return false;
    /* The codec guarantees required fields and their lengths. */
    for (size_t i = 0; i < frame.field_count; ++i) {
        const exob_field *field = &frame.fields[i];
        if (field->id == EXOB_FIELD_SELECTED_VERSION &&
            (field->value[0] != EXOB_MAJOR || field->value[1] != EXOB_MINOR))
            return false;
        if (field->id == EXOB_FIELD_CAPABILITIES)
            for (size_t j = 0; j < field->length; ++j)
                if (field->value[j] != 0)
                    return false;
    }
    return true;
}

static bool connect_peer(observer_event_socket *state, const char *path) {
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    const size_t length = strlen(path);
    memcpy(address.sun_path, path, length + 1);
    state->fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (state->fd < 0)
        return false;
    /* Exim closes and redirects standard streams during delivery. Keep owned
     * sockets outside that range, even when socket() returns a vacant stdio FD. */
    if (state->fd <= STDERR_FILENO) {
        const int original = state->fd;
        state->fd = fcntl(original, F_DUPFD_CLOEXEC, STDERR_FILENO + 1);
        (void)close(original);
        if (state->fd < 0)
            return false;
    }
    return connect(state->fd, (const struct sockaddr *)&address,
                   (socklen_t)(offsetof(struct sockaddr_un, sun_path) + length + 1)) == 0 &&
           send_hello(state->fd);
}

static void unavailable(observer_event_socket *state) {
    ++state->unavailable;
    observer_socket_close(state);
}

static void receive_ack(observer_event_socket *state) {
    uint8_t wire[EXOB_HEADER_SIZE + EXOB_MAX_PAYLOAD];
    const ssize_t length = recv(state->fd, wire, sizeof(wire), MSG_DONTWAIT | MSG_TRUNC);
    if (length < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
        return;
    if (length <= 0) {
        unavailable(state);
        return;
    }
    if ((size_t)length > sizeof(wire) || !valid_ack(wire, (size_t)length)) {
        ++state->protocol_errors;
        observer_socket_close(state);
        return;
    }
    state->ready = true;
}

static void handshake_step(observer_event_socket *state, const char *path) {
    const pid_t pid = getpid();
    if (state->owner != pid) {
        observer_socket_close(state);
        state->owner = pid;
        state->unavailable = 0;
        state->protocol_errors = 0;
    }
    if (state->ready) {
        /* Observe disconnects without consuming future application packets.
         * Reconnect on the next callback, keeping work bounded per invocation. */
        struct pollfd peer = {.fd = state->fd, .events = POLLRDHUP};
        const int result = poll(&peer, 1, 0);
        if ((result < 0 && errno != EINTR) ||
            (result > 0 &&
             ((unsigned)peer.revents & (unsigned)(POLLHUP | POLLRDHUP | POLLERR | POLLNVAL)) != 0))
            unavailable(state);
        return;
    }
    if (!observer_socket_path_valid(path)) {
        unavailable(state);
        return;
    }
    if (state->fd < 0 && !connect_peer(state, path)) {
        unavailable(state);
        return;
    }
    receive_ack(state);
}

void observer_socket_step(observer_event_socket *state, const char *path) {
    const int saved_errno = errno;
    handshake_step(state, path);
    errno = saved_errno;
}
