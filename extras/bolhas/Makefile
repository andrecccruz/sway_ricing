CFLAGS ?= -O2 -Wall -Wextra
PKGS = wayland-client wayland-egl egl glesv2
PROTO = wlr-layer-shell-unstable-v1

bolhas: main.c $(PROTO)-protocol.c $(PROTO)-client-protocol.h
	$(CC) $(CFLAGS) -o $@ main.c $(PROTO)-protocol.c \
		$$(pkg-config --cflags --libs $(PKGS)) -lm

$(PROTO)-client-protocol.h: $(PROTO).xml
	wayland-scanner client-header $< $@

$(PROTO)-protocol.c: $(PROTO).xml
	wayland-scanner private-code $< $@

install: bolhas
	install -Dm755 bolhas $(HOME)/.local/bin/bolhas

clean:
	rm -f bolhas $(PROTO)-protocol.c $(PROTO)-client-protocol.h

.PHONY: install clean
