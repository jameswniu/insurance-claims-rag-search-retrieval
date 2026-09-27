#!/bin/sh
# The database healthcheck. Ready means Postgres answers over TCP, so the check stays red while the entrypoint's
# socket-only init server is up, and the superuser's password matches var/secrets.env. The data volume keeps the
# password it was created with while every clone of the repo mints its own, so a second clone's init would fail to
# sign in. The container's own Unix socket is trusted, so the password is set again over it, once per container.
set -eu
pg_isready -q -U postgres -h 127.0.0.1
marker=/tmp/postgres-password.sha256
want=$(printf '%s' "$POSTGRES_PASSWORD" | sha256sum | cut -d' ' -f1)
if [ -f "$marker" ] && [ "$(cat "$marker")" = "$want" ]; then
  exit 0
fi
psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres <<'SQL'
\getenv pw POSTGRES_PASSWORD
ALTER ROLE postgres PASSWORD :'pw';
SQL
printf '%s' "$want" > "$marker"
