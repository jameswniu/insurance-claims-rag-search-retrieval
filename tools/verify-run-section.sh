#!/usr/bin/env bash
# The edge cases around make up that the run section in README.md does not reach, run for real: the port make up picks
# when every port from 8000 to 8019 is held and when only the first free one is, a second make up, make down then make
# up, a second clone with passwords of its own on the same database, and make live-check with no key.
# It starts and stops the claims-qa stack. It begins where the run section's make reset leaves off, with no stack and no
# database volume, refuses to start from anything else, and removes the volume it made when it ends.
set -euo pipefail
cd "$(dirname "$0")/.."
# Compose settings from the shell could point make at another project or file than the one checked below.
unset APP_PORT COMPOSE_PROJECT_NAME COMPOSE_FILE COMPOSE_PROFILES COMPOSE_PATH_SEPARATOR COMPOSE_ENV_FILES

VOLUME=claims-qa_pgdata
CLAIMS=6951
SCANS=60
tmp=$(mktemp -d "${TMPDIR:-/tmp}/verify-run-section.XXXXXX")
second="$tmp/second"
held=()
started=0
check=setup

# Stops the script with a message, and with the last 20 lines of a log when one is named.
fail() {
  echo "FAIL $check: $1" >&2
  if [ -n "${2:-}" ]; then tail -n 20 "$2" >&2; fi
  exit 1
}

pass() {
  echo "PASS $check: $1"
}

# Runs a command with its output kept in a log named by the first argument, and stops the script if it fails.
run() {
  local log="$tmp/$1.log"
  shift
  if ! "$@" >"$log" 2>&1; then fail "$* failed. Its last 20 lines:" "$log"; fi
}

# True when something accepts connections on the port, the same test tools/app-port.sh makes.
busy() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

# Holds a port with a small listener of this script's own, and records its pid.
hold() {
  local ready="$tmp/hold-$1" tries=0
  python3 -c 'import signal, socket, sys
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", int(sys.argv[1])))
s.listen(64)
print("listening", flush=True)
while True:
    s.accept()[0].close()' "$1" >"$ready" 2>&1 &
  held+=("$!")
  while ! grep -q listening "$ready"; do
    tries=$((tries + 1))
    if [ "$tries" -gt 50 ] || grep -q Error "$ready"; then fail "could not hold port $1" "$ready"; fi
    sleep 0.2
  done
}

# Stops the listeners this script started, each by the pid it recorded, and only while that pid is still its child.
release() {
  local pid
  for pid in ${held[@]+"${held[@]}"}; do
    if [ "$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')" = "$$" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  held=()
}

# On any exit: the listeners, then the stack and the volume it made if this script started them, then the temp dir.
finish() {
  local status=$?
  set +e
  release
  if [ "$started" = 1 ]; then
    if [ -n "${second:-}" ] && [ -d "$second" ]; then (cd "$second" && docker compose down >/dev/null 2>&1); fi
    docker compose down >/dev/null 2>&1
    docker volume rm "$VOLUME" >/dev/null 2>&1
  fi
  rm -rf "$tmp"
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Asks the database as the superuser over the container's own trusted socket, so no password is involved.
sql() {
  docker compose exec -T db psql -U postgres -d claims -tAc "$1"
}

# Stops the script unless the query's one value is the one expected. The first argument names the value.
expect() {
  local got
  got=$(sql "$2" 2>"$tmp/sql.err") || true
  if [ "$got" != "$3" ]; then fail "$1 is '$got', not $3" "$tmp/sql.err"; fi
}

# The port in the running at line of a make up log, or a stop when there is no such line.
printed_port() {
  local port
  port=$(sed -n 's|.*is running at http://localhost:\([0-9][0-9]*\).*|\1|p' "$tmp/$1.log" | tail -n 1)
  if [ -z "$port" ]; then fail "make up printed no running at line" "$tmp/$1.log"; fi
  echo "$port"
}

# Stops the script unless the app is published on the port make up printed and answers /healthz there.
answers() {
  local published body
  published=$(docker compose port app 8000 2>/dev/null | sed 's/.*://') || true
  if [ "$published" != "$1" ]; then fail "make up printed port $1, but the app is published on '$published'"; fi
  body=$(curl -fsS --max-time 10 "http://localhost:$1/healthz" 2>&1) || true
  case "$body" in
    *'"ok":true'*) ;;
    *) fail "/healthz on port $1 answered '$body'" ;;
  esac
}

# Each bootstrap step with the time it last ran, one to a line, and the line for one step.
steps() {
  sql "SELECT step || ' ' || done_at FROM app.bootstrap_state ORDER BY step"
}
row() {
  printf '%s\n' "$2" | grep "^$1 " || true
}

# The claim count and a hash over every claim row, which changes if any claim does.
claims_hash() {
  sql "SELECT count(*) || ' ' || md5(string_agg(c::text, ',' ORDER BY c.claim_id)) FROM core.claims c"
}

# Runs a command in the second clone, in a subshell, so this script's own directory never changes.
in_second() {
  (cd "$second" && "$@")
}

# The run section ends with make down and make reset, so this starts from nothing. It refuses anything else rather than
# touch a stack or a database it did not start, or run where a .env would choose the port.
if [ -e .env ]; then fail ".env is here and would choose the port. Run this from a fresh clone."; fi
if ! docker info >/dev/null 2>&1; then fail "Docker is not running."; fi
if [ -n "$(docker ps -q --filter label=com.docker.compose.project=claims-qa)" ]; then
  fail "a claims-qa stack is running. Stop it with make down first."
fi
if docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  fail "the $VOLUME volume exists. Run make reset first, so the first make up seeds from nothing."
fi

check=1
# 1. With every free port from 8000 to 8019 held, tools/app-port.sh has none to choose, so it prints 8000 and says why
# on stderr.
count=0
for port in $(seq 8000 8019); do
  if ! busy "$port"; then
    hold "$port"
    count=$((count + 1))
  fi
done
if ! bash tools/app-port.sh >"$tmp/port.out" 2>"$tmp/port.err"; then fail "tools/app-port.sh failed" "$tmp/port.err"; fi
release
if [ "$(cat "$tmp/port.out")" != 8000 ]; then fail "tools/app-port.sh printed '$(cat "$tmp/port.out")', not 8000"; fi
if ! grep -q "No free port from 8000 to 8019" "$tmp/port.err"; then
  fail "tools/app-port.sh did not say that no port is free" "$tmp/port.err"
fi
pass "with every port from 8000 to 8019 taken, $count of them here, app-port.sh printed 8000 and said none is free"

check=2
# 2. With the first free port held by this script, make up must pick another port in range, print it and answer
# /healthz on it, and seed every claim and scan from nothing.
first=""
for port in $(seq 8000 8019); do
  if ! busy "$port"; then
    first=$port
    break
  fi
done
if [ -z "$first" ]; then fail "no port from 8000 to 8019 is free to hold"; fi
hold "$first"
started=1
run up2 make up
port=$(printed_port up2)
if [ "$port" = "$first" ] || [ "$port" -lt 8000 ] || [ "$port" -gt 8019 ]; then
  fail "with $first held, make up printed port $port, not another port from 8000 to 8019" "$tmp/up2.log"
fi
answers "$port"
docker compose logs --no-color init >"$tmp/init2.log" 2>&1 || true
if ! grep -Eq "bootstrap seed +[0-9]+ ms" "$tmp/init2.log"; then fail "init did not log a seed run" "$tmp/init2.log"; fi
expect "the claim count" "SELECT count(*) FROM core.claims" "$CLAIMS"
expect "the scan count" "SELECT count(*) FROM rag.documents WHERE kind = 'scan'" "$SCANS"
release
pass "with $first held, make up chose $port, printed it, answered /healthz, and seeded $CLAIMS claims and $SCANS scans"

check=3
# 3. A second make up finds the app running and keeps its port, though the port held in check 2 is free again. Init
# runs again and redoes the steps it runs every time, but the seed row keeps the time it was first written.
if busy "$first"; then fail "port $first is taken again, so keeping $port would prove nothing"; fi
before=$(steps) || fail "could not read app.bootstrap_state"
run up3 make up
again=$(printed_port up3)
if [ "$again" != "$port" ]; then fail "the second make up printed port $again, not $port" "$tmp/up3.log"; fi
answers "$again"
after=$(steps) || fail "could not read app.bootstrap_state"
if [ -z "$(row seed "$before")" ] || [ "$(row seed "$before")" != "$(row seed "$after")" ]; then
  fail "the seed row went from '$(row seed "$before")' to '$(row seed "$after")'"
fi
if [ "$(row passwords "$before")" = "$(row passwords "$after")" ]; then
  fail "init did not run again, so an unchanged seed row proves nothing"
fi
expect "the claim count" "SELECT count(*) FROM core.claims" "$CLAIMS"
pass "a second make up kept port $port, ran init again without seeding, and still holds $CLAIMS claims"

check=4
# 4. make down then make up keeps the data. The claims are the same rows, and the new init container logs the seed and
# the other one-time steps as skipped, each with its row unchanged.
before=$(steps) || fail "could not read app.bootstrap_state"
hash=$(claims_hash) || fail "could not read core.claims"
run down4 make down
run up4 make up
port=$(printed_port up4)
answers "$port"
if [ "$(claims_hash)" != "$hash" ]; then fail "the claims changed across make down and make up"; fi
after=$(steps) || fail "could not read app.bootstrap_state"
docker compose logs --no-color init >"$tmp/init4.log" 2>&1 || true
skipped=$(sed -n 's/.* bootstrap \([a-z_]*\) *skipped, already done.*/\1/p' "$tmp/init4.log")
if ! printf '%s\n' "$skipped" | grep -qx seed; then fail "init did not log the seed as skipped" "$tmp/init4.log"; fi
for step in $skipped; do
  if [ "$(row "$step" "$before")" != "$(row "$step" "$after")" ]; then
    fail "init logged $step as skipped, yet its row changed"
  fi
done
skipped=$(echo $skipped | sed 's/ /, /g; s/\(.*\), /\1 and /')
pass "make down then make up kept all $CLAIMS claims as they were, skipped $skipped, and answered on $port"

check=5
# 5. A second clone of the same commit mints passwords of its own, and its make up must still start on the existing
# volume, since the database healthcheck sets the superuser's password again from that clone. Its commands run in
# subshells, so this script never leaves its own directory.
run clone5 git clone -q --no-checkout "$PWD" "$second"
run checkout5 git -C "$second" checkout -q "$(git rev-parse HEAD)"
run up5 in_second make up
if [ ! -s var/secrets.env ] || [ ! -s "$second/var/secrets.env" ]; then fail "a var/secrets.env is missing"; fi
if cmp -s var/secrets.env "$second/var/secrets.env"; then
  fail "the second clone's var/secrets.env matches this one's, so this check would prove nothing"
fi
port=$(printed_port up5)
in_second answers "$port"
in_second docker compose logs --no-color init >"$tmp/init5.log" 2>&1 || true
if ! grep -Eq "bootstrap seed +skipped, already done" "$tmp/init5.log"; then
  fail "the second clone's init did not find the seed already done" "$tmp/init5.log"
fi
in_second expect "the claim count" "SELECT count(*) FROM core.claims" "$CLAIMS"
run down5 in_second make down
pass "a second clone with its own passwords started on the same volume, answered on $port, held $CLAIMS claims, stopped"

check=6
# 6. make live-check with no key calls no model. With LLM_BACKEND=anthropic it must fail and name ANTHROPIC_API_KEY
# before it makes a client. With LLM_BACKEND unset as well, live mode is off, the default, and it must say so. The API
# address points at a closed local port both times, so even a wrong turn could not reach a model.
if env -u ANTHROPIC_API_KEY -u LLM_CHECK_BACKEND LLM_BACKEND=anthropic ANTHROPIC_BASE_URL=http://127.0.0.1:9 \
  make live-check >"$tmp/live.log" 2>&1; then
  fail "make live-check passed with LLM_BACKEND=anthropic and no key" "$tmp/live.log"
fi
if ! grep -q "LLM_BACKEND=anthropic needs ANTHROPIC_API_KEY" "$tmp/live.log"; then
  fail "make live-check did not name ANTHROPIC_API_KEY" "$tmp/live.log"
fi
if ! env -u ANTHROPIC_API_KEY -u LLM_BACKEND -u LLM_CHECK_BACKEND ANTHROPIC_BASE_URL=http://127.0.0.1:9 \
  make live-check >"$tmp/off.log" 2>&1; then
  fail "make live-check failed with live mode off" "$tmp/off.log"
fi
if ! grep -q "LLM_BACKEND is off, so there is nothing to check." "$tmp/off.log"; then
  fail "make live-check did not say that live mode is off" "$tmp/off.log"
fi
if grep -Eq "answered as|^(backend|checker) " "$tmp/live.log" "$tmp/off.log"; then
  fail "make live-check called a model"
fi
pass "with no key, live-check failed naming ANTHROPIC_API_KEY, said off with no backend set, and called no model"

echo "All six checks passed."
