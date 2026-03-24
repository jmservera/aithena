#!/bin/sh
set -e

# Fix ownership of bind-mounted directories when container starts as root,
# then drop to the unprivileged "app" user via su-exec (Alpine gosu equivalent).
#
# The document-data volume is a host bind mount (type: none, o: bind) so the
# directory inherits host ownership (typically root:root).  The app user (1000)
# needs write access to scan and manage documents.

if [ "$(id -u)" = "0" ]; then
    # Only fix the top-level directory; avoid recursive chown on a potentially
    # large book library — subdirectory contents stay as-is (readable by all).
    chown app:app /data/documents 2>/dev/null || true
    exec su-exec app "$@"
fi

# Already running as non-root (e.g. --user flag) — just exec the command.
exec "$@"
