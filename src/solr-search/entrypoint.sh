#!/bin/sh
set -e

# When running as root (the default), fix ownership of bind-mounted
# directories that Docker may have created as root:root, then drop
# to the unprivileged "app" user before executing the CMD.
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /data/auth 2>/dev/null || true
    chown -R app:app /data/collections 2>/dev/null || true
    exec gosu app "$@"
fi

# Already running as non-root (e.g. --user flag) — just exec the command.
exec "$@"
