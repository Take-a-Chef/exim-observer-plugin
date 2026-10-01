/* SPDX-License-Identifier: GPL-2.0-or-later */
// NOLINTNEXTLINE(bugprone-reserved-identifier): glibc feature-test macro.
#define _GNU_SOURCE
#ifdef NDEBUG
#error "Unit tests require assertions; remove -DNDEBUG"
#endif
#include "event_socket.h"
#include "exim_observer_protocol.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>

static void hello(int peer) {
    uint8_t wire[256];
    ssize_t n = recv(peer, wire, sizeof(wire), MSG_DONTWAIT);
    assert(n > 0);
    exob_frame frame;
    assert(exob_decode(wire, (size_t)n, &frame) == EXOB_ERROR_OK);
    assert(frame.type == EXOB_MSG_HELLO && frame.field_count == 3);
    for (size_t i = 0; i < 8; ++i)
        assert(frame.fields[2].value[i] == 0);
}

static void ack(int peer, bool invalid) {
    const uint8_t version[] = {EXOB_MAJOR, EXOB_MINOR};
    uint8_t caps[8] = {0};
    if (invalid)
        caps[7] = 1;
    exob_frame frame = {
        .version = {EXOB_MAJOR, EXOB_MINOR},
        .type = EXOB_MSG_HELLO_ACK,
        .field_count = 2,
        .fields = {{EXOB_FIELD_SELECTED_VERSION, 2, version}, {EXOB_FIELD_CAPABILITIES, 8, caps}}};
    uint8_t wire[64];
    size_t n = 0;
    assert(exob_encode(&frame, wire, sizeof(wire), &n) == EXOB_ERROR_OK);
    assert(send(peer, wire, n, MSG_NOSIGNAL) == (ssize_t)n);
}

static void test_closed_stdio(int listener, const char *path) {
    pid_t child = fork();
    assert(child >= 0);
    if (child == 0) {
        for (int fd = STDIN_FILENO; fd <= STDERR_FILENO; ++fd)
            (void)close(fd);
        observer_event_socket state = OBSERVER_EVENT_SOCKET_INIT;
        observer_socket_step(&state, path);
        bool valid = state.fd > STDERR_FILENO;
        for (int fd = STDIN_FILENO; fd <= STDERR_FILENO; ++fd)
            if (fcntl(fd, F_GETFD) != -1 || errno != EBADF)
                valid = false;
        if (state.fd >= 0) {
            int flags = fcntl(state.fd, F_GETFD);
            if (flags < 0 || ((unsigned)flags & (unsigned)FD_CLOEXEC) == 0)
                valid = false;
            flags = fcntl(state.fd, F_GETFL);
            if (flags < 0 || ((unsigned)flags & (unsigned)O_NONBLOCK) == 0)
                valid = false;
        }
        observer_socket_close(&state);
        _exit(valid ? 0 : 1);
    }
    int status = 0;
    assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    int peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    assert(close(peer) == 0);
}

int main(void) {
    /* A broken nonblocking path must fail the test instead of hanging CI. */
    (void)alarm(15);
    observer_event_socket state = OBSERVER_EVENT_SOCKET_INIT;
    assert(!observer_socket_path_valid(NULL));
    assert(!observer_socket_path_valid("relative.sock"));
    assert(!observer_socket_path_valid("/tmp/a\nb"));
    char long_path[256];
    memset(long_path, 'a', sizeof(long_path));
    long_path[0] = '/';
    long_path[sizeof(long_path) - 1] = 0;
    assert(!observer_socket_path_valid(long_path));
    char directory[] = "/tmp/exob-unit-XXXXXX";
    assert(mkdtemp(directory) != NULL);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    int n = snprintf(address.sun_path, sizeof(address.sun_path), "%s/events.sock", directory);
    assert(n > 0 && (size_t)n < sizeof(address.sun_path));
    for (int i = 0; i < 100; ++i) {
        errno = EDOM;
        observer_socket_step(&state, address.sun_path);
        assert(state.fd == -1 && errno == EDOM);
    }
    assert(state.unavailable == 100);
    int listener = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    assert(listener >= 0);
    assert(bind(listener, (const struct sockaddr *)&address, sizeof(address)) == 0);
    assert(listen(listener, 4) == 0);
    test_closed_stdio(listener, address.sun_path);
    observer_socket_step(&state, address.sun_path);
    assert(state.fd >= 0 && !state.ready);
    int flags = fcntl(state.fd, F_GETFL);
    assert(flags >= 0 && ((unsigned)flags & (unsigned)O_NONBLOCK) != 0);
    flags = fcntl(state.fd, F_GETFD);
    assert(flags >= 0 && ((unsigned)flags & (unsigned)FD_CLOEXEC) != 0);
    int peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    /* An idle peer is not an error and must not trigger a second HELLO. */
    errno = EDOM;
    observer_socket_step(&state, address.sun_path);
    assert(errno == EDOM && state.fd >= 0 && !state.ready);
    uint8_t extra = 0;
    assert(recv(peer, &extra, 1, MSG_DONTWAIT) == -1);
    assert(errno == EAGAIN || errno == EWOULDBLOCK);
    ack(peer, false);
    observer_socket_step(&state, address.sun_path);
    assert(state.ready);
    pid_t parent = state.owner;
    pid_t child = fork();
    assert(child >= 0);
    if (child == 0) {
        observer_socket_step(&state, address.sun_path);
        _exit(state.owner == getpid() && !state.ready && state.fd >= 0 ? 0 : 1);
    }
    int status = 0;
    assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    assert(state.owner == parent && state.ready);
    int child_peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(child_peer >= 0);
    hello(child_peer);
    assert(close(child_peer) == 0);
    /* A completed handshake must not hide agent exit forever. */
    assert(close(peer) == 0);
    errno = EDOM;
    observer_socket_step(&state, address.sun_path);
    assert(errno == EDOM && state.fd == -1 && !state.ready);
    assert(state.unavailable == 101 && state.protocol_errors == 0);
    observer_socket_step(&state, address.sun_path);
    peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    ack(peer, false);
    observer_socket_step(&state, address.sun_path);
    assert(state.ready);
    errno = EDOM;
    observer_socket_close(&state);
    observer_socket_close(&state);
    assert(errno == EDOM && state.fd == -1 && !state.ready);
    assert(close(peer) == 0);
    observer_socket_step(&state, address.sun_path);
    peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    ack(peer, true);
    observer_socket_step(&state, address.sun_path);
    assert(state.fd == -1 && !state.ready && state.protocol_errors == 1);
    assert(close(peer) == 0);
    observer_socket_step(&state, address.sun_path);
    peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    assert(send(peer, "bad", 3, MSG_NOSIGNAL) == 3);
    observer_socket_step(&state, address.sun_path);
    assert(state.fd == -1 && state.protocol_errors == 2);
    assert(close(peer) == 0);
    /* EOF before ACK is transport unavailability, not a malformed frame. */
    observer_socket_step(&state, address.sun_path);
    peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    assert(close(peer) == 0);
    observer_socket_step(&state, address.sun_path);
    assert(state.fd == -1 && state.unavailable == 102 && state.protocol_errors == 2);
    /* MSG_TRUNC reports the original packet size; never decode a truncated prefix. */
    observer_socket_step(&state, address.sun_path);
    peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    uint8_t oversized[EXOB_HEADER_SIZE + EXOB_MAX_PAYLOAD + 1] = {0};
    assert(send(peer, oversized, sizeof(oversized), MSG_DONTWAIT | MSG_NOSIGNAL) ==
           (ssize_t)sizeof(oversized));
    observer_socket_step(&state, address.sun_path);
    assert(state.fd == -1 && state.protocol_errors == 3);
    assert(close(peer) == 0);
    /* Closing only the peer's write direction must invalidate the session too. */
    observer_socket_step(&state, address.sun_path);
    peer = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    assert(peer >= 0);
    hello(peer);
    ack(peer, false);
    observer_socket_step(&state, address.sun_path);
    assert(state.ready);
    assert(shutdown(peer, SHUT_WR) == 0);
    observer_socket_step(&state, address.sun_path);
    assert(state.fd == -1 && !state.ready && state.unavailable == 103);
    assert(state.protocol_errors == 3);
    assert(close(peer) == 0);
    assert(close(listener) == 0);
    assert(unlink(address.sun_path) == 0);
    assert(rmdir(directory) == 0);
    (void)alarm(0);
    puts("handshake, reconnect, half-close, stdio isolation, oversized packets and fork tests "
         "passed");
    return 0;
}
