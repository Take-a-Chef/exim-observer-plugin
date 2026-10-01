SHELL := /bin/sh
PROTOCOL_ROOT ?= ../exim-observer-protocol
EXIM_SOURCE_ROOT ?= $(PROTOCOL_ROOT)/.tools
# Reuse explicitly installed local C development tools, never install during builds.
export PATH := $(abspath $(PROTOCOL_ROOT))/.tools/venv/bin:$(abspath $(PROTOCOL_ROOT))/.tools/bin:$(PATH)
CC ?= gcc
EXIM_VERSION ?= 4.99.5
WARNINGS := -Wall -Wextra -Wpedantic -Wformat=2 -Wshadow -Wconversion -Wsign-conversion -Wundef -Wcast-qual -Wwrite-strings -Wstrict-prototypes -Wmissing-prototypes -Werror=implicit-function-declaration
.PHONY: all build exim-4.99.5 exim-4.100.1 patch-apply
all: build
build: check-protocol
	python3 scripts/build-exim.py --version $(EXIM_VERSION) --cc $(if $(filter default,$(origin CC)),gcc,$(CC)) --source-root $(EXIM_SOURCE_ROOT) --protocol-root $(PROTOCOL_ROOT)
exim-4.99.5:
	$(MAKE) build EXIM_VERSION=4.99.5
exim-4.100.1:
	$(MAKE) build EXIM_VERSION=4.100.1
patch-apply:
	python3 scripts/build-exim.py --version 4.99.5 --patch-only --source-root $(EXIM_SOURCE_ROOT)
	python3 scripts/build-exim.py --version 4.100.1 --patch-only --source-root $(EXIM_SOURCE_ROOT)
CPPFLAGS := -Isrc -I$(PROTOCOL_ROOT)/include -I$(PROTOCOL_ROOT)/c/include
CFLAGS ?= -O2 -g
override CFLAGS += -std=c11 $(WARNINGS)
PROTOCOL_C := $(PROTOCOL_ROOT)/c/src/codec.c $(PROTOCOL_ROOT)/c/src/validation.c
.PHONY: test unit FORCE integration test-vectors format fmt format-check lint check check-all test-sanitize
# This small test binary is rebuilt so compiler/flag/header changes cannot reuse it.
FORCE:
build/test-event-socket: tests/unit/test_event_socket.c src/event_socket.c src/event_socket.h $(PROTOCOL_C) FORCE
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/event_socket.c $(PROTOCOL_C) $< -o $@
unit: build/test-event-socket
	./build/test-event-socket
test: unit test-vectors test-build
test-vectors: check-protocol
	$(MAKE) -C $(PROTOCOL_ROOT) test-vectors
integration: build
	python3 tests/integration/minimal.py --version $(EXIM_VERSION) --cc $(if $(filter default,$(origin CC)),gcc,$(CC))
format fmt:
	clang-format -i src/*.c src/*.h src/compat/*.h tests/unit/*.c
format-check:
	clang-format --dry-run --Werror src/*.c src/*.h src/compat/*.h tests/unit/*.c
lint:
	clang-tidy src/event_socket.c tests/unit/test_event_socket.c -- $(CPPFLAGS) -std=c11
	cppcheck --enable=warning,style,performance,portability --error-exitcode=1 --std=c11 --suppress=missingIncludeSystem $(CPPFLAGS) src/event_socket.c tests/unit/test_event_socket.c
check: check-protocol format-check lint test patch-apply
check-all: check
	$(MAKE) test-compilers
.PHONY: test-compilers
test-compilers: check-protocol
	@set -e; for cc in gcc clang; do \
	  $(MAKE) unit CC=$$cc CFLAGS='-O2 -g -Werror'; \
	  for version in 4.99.5 4.100.1; do \
	    $(MAKE) integration CC=$$cc EXIM_VERSION=$$version; \
	  done; \
	done
test-sanitize:
	mkdir -p build
	clang $(CPPFLAGS) -std=c11 $(WARNINGS) -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer src/event_socket.c $(PROTOCOL_C) tests/unit/test_event_socket.c -o build/test-sanitize
	./build/test-sanitize

.PHONY: check-protocol fetch-sources
check-protocol:
	python3 scripts/check-protocol.py $(PROTOCOL_ROOT)
# Explicit setup; ordinary build/test/check never download sources or tools.
fetch-sources:
	python3 scripts/fetch-exim.py --source-root $(EXIM_SOURCE_ROOT) --version 4.99.5
	python3 scripts/fetch-exim.py --source-root $(EXIM_SOURCE_ROOT) --version 4.100.1

.PHONY: test-build
test-build:
	python3 -m unittest discover -s tests/build -v
