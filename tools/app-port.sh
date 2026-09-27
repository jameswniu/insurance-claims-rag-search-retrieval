#!/usr/bin/env bash
# The host port make up publishes the app on. APP_PORT from the shell or .env wins. Otherwise it is the port the running
# app already has, so running make up again keeps the same address, then 8000, then the next free port up to 8019.
set -u
if [ -n "${APP_PORT:-}" ]; then echo "$APP_PORT"; exit 0; fi
from_env=$(sed -n 's/^APP_PORT=//p' .env 2>/dev/null | tail -1)
if [ -n "$from_env" ]; then echo "$from_env"; exit 0; fi
current=$(docker compose port app 8000 2>/dev/null | sed -n 's/.*://p' | head -1)
if [ -n "$current" ]; then echo "$current"; exit 0; fi
for port in $(seq 8000 8019); do
  if ! (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then echo "$port"; exit 0; fi
done
echo "No free port from 8000 to 8019. Set APP_PORT to a free port and run make up again." >&2
echo 8000
