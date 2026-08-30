#!/usr/bin/env bash
#
# expose.sh - Run the app locally and share it with a remote tester using a
# local tunnel (ngrok or localtunnel). No cloud deploy involved.
#
# What it does:
#   * starts the FastAPI backend  (uvicorn, port 8000)  in the background
#   * starts the Next.js frontend (next dev, port 3000) in the background
#   * opens a tunnel to the FRONTEND so you can copy a public URL to a friend
#   * on Ctrl+C / exit, kills backend + frontend + tunnel cleanly (no strays)
#
# Remote testers also need the API. The frontend's API origin is compiled in at
# start time via NEXT_PUBLIC_API_URL, and this script injects the backend tunnel
# URL so the app talks to YOUR backend (not the tester's localhost). Usage:
#
#   EXPOSE_BACKEND=1 ./expose.sh
#   EXPOSE_BACKEND=1 BACKEND_PUBLIC_URL=https://your-ngrok.ngrok.io ./expose.sh
#
# Prerequisites (see EXPOSE.md):
#   - Bash on Linux or WSL2
#   - Backend deps installed (python + `pip install -r backend/requirements.txt`)
#   - Frontend deps installed (`cd frontend && npm install`)
#   - A tunnel tool: `ngrok` (https://ngrok.com/download) or `lt` (localtunnel,
#     `npm install -g localtunnel`). The script auto-detects, preferring ngrok.

set -euo pipefail

# --------------------------------------------------------------------------- #
# Config                                                                            #
# --------------------------------------------------------------------------- #
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"     # local bind (safe default)
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"

# Set to 1 to also tunnel the backend and point the frontend at it.
EXPOSE_BACKEND="${EXPOSE_BACKEND:-0}"
# Optional: manually provide the backend's public base (e.g. an existing tunnel).
# Used as-is; the script skips creating a backend tunnel when this is set.
BACKEND_PUBLIC_URL="${BACKEND_PUBLIC_URL:-}"

# Tunnel tool: auto | ngrok | lt
TUNNEL_TOOL="${TUNNEL_TOOL:-auto}"

# Where logs / pidfiles live (kept in the OS temp dir so the repo stays clean).
STATE_DIR="${TMPDIR:-/tmp}/ai-research-expose"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${BACKEND_DIR:-$ROOT_DIR/backend}"
FRONTEND_DIR="${FRONTEND_DIR:-$ROOT_DIR/frontend}"

PIDS=()   # tracked background process ids

# --------------------------------------------------------------------------- #
# Helpers                                                                            #
# --------------------------------------------------------------------------- #
log()  { printf '\033[1;36m[ expose ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ expose ]\033[0m WARN: %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[ expose ]\033[0m ERROR: %s\n' "$*" >&2; exit 1; }

mkdir -p "$STATE_DIR"

command -v curl >/dev/null 2>&1 || die "curl is required. Install curl first."

# Recursively kill a process and all of its children (handles npm->next chains).
kill_tree() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  local children
  children=$(pgrep -P "$pid" 2>/dev/null || true)
  for child in $children; do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  log "Stopping all processes..."
  for pid in "${PIDS[@]:-}"; do
    kill_tree "$pid"
  done
  pkill -f "ngrok http" 2>/dev/null || true
  pkill -f "localtunnel" 2>/dev/null || true
  wait 2>/dev/null || true
  log "Done - nothing left running."
}
trap cleanup EXIT INT TERM

# Resolve which tunnel tool to use.
resolve_tunnel_tool() {
  if [ "$TUNNEL_TOOL" = "ngrok" ] || { [ "$TUNNEL_TOOL" = "auto" ] && command -v ngrok >/dev/null 2>&1; }; then
    command -v ngrok >/dev/null 2>&1 || die "TUNNEL_TOOL=ngrok but ngrok is not installed."
    echo ngrok
  elif [ "$TUNNEL_TOOL" = "lt" ] || { [ "$TUNNEL_TOOL" = "auto" ] && command -v lt >/dev/null 2>&1; }; then
    command -v lt >/dev/null 2>&1 || die "TUNNEL_TOOL=lt but localtunnel is not installed (npm i -g localtunnel)."
    echo lt
  else
    die "No tunnel tool found (ngrok or localtunnel). Install one: see EXPOSE.md"
  fi
}

# Wait until a local HTTP endpoint answers, with a timeout. Warn (don't fail)
# so a sluggish frontend build on first run doesn't abort everything.
wait_for_http() {
  local host="$1" port="$2" name="$3" timeout="${4:-45}"
  local i=0
  while [ "$i" -lt "$timeout" ]; do
    if curl -fsS --max-time 2 "http://${host}:${port}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  warn "${name} did not answer on :${port} within ${timeout}s - continuing anyway."
  return 1
}

# --------------------------------------------------------------------------- #
# Application startup                                                                 #
# --------------------------------------------------------------------------- #
start_backend() {
  log "Starting backend: uvicorn app.main:app on ${BACKEND_HOST}:${BACKEND_PORT}"
  # Tunnels make the "browser origin" unpredictable (NGrok/localTunnel URLs), so
  # open CORS on the API. Safe: the app sets allow_credentials=False, meaning
  # browsers never send cookies/tokens with these requests.
  (cd "$BACKEND_DIR" \
    && export CORS_ALLOW_ANY_ORIGIN=1 \
    && exec uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT") &
  PIDS+=("$!")
}

start_frontend() {
  local backend_url="${BACKEND_PUBLIC_URL:-}"
  log "Starting frontend: next dev on ${FRONTEND_HOST}:${FRONTEND_PORT}"
  if [ "$EXPOSE_BACKEND" -eq 1 ] && [ -n "$backend_url" ]; then
    log "  * backend API for the app -> ${backend_url}/api/v1"
    (cd "$FRONTEND_DIR" \
      && export NEXT_PUBLIC_API_URL="$backend_url" \
      && exec npx next dev -H "$FRONTEND_HOST" -p "$FRONTEND_PORT") &
  else
    (cd "$FRONTEND_DIR" \
      && exec npx next dev -H "$FRONTEND_HOST" -p "$FRONTEND_PORT") &
  fi
  PIDS+=("$!")
}

# --------------------------------------------------------------------------- #
# Tunnels                                                                              #
# --------------------------------------------------------------------------- #
# Extract the public_url of the ngrok tunnel whose local addr ends in ":port".
# Uses jq when available, falls back to python3, then a plain grep last resort.
tunnel_url_for_port() {
  local json_file="$1" port="$2" admin_api="$3"
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg port ":$port" \
      '[.tunnels[] | select((.config.addr // "") | endswith($port))][0].public_url // empty' \
      "$json_file" 2>/dev/null || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));
print("".join(t["public_url"] for t in d.get("tunnels",[]) if str(t.get("config",{}).get("addr","")).endswith(":"+sys.argv[2])))' \
        "$json_file" "$port" 2>/dev/null || true
  else
    curl -fsS --max-time 3 "$admin_api" 2>/dev/null \
      | grep -o '"public_url":"[^"]*"' \
      | grep ":${port}\"" \
      | head -1 \
      | sed 's/.*"public_url":"\([^"]*\)".*/\1/' 2>/dev/null || true
  fi
}

# ngrok tunnel(s). When two ports are requested a single ngrok process opens
# both tunnels; URLs are read back from ngrok's local admin API.
ngrok_start() {
  local ports=("$@")
  local logfile="$STATE_DIR/ngrok.log"
  : > "$logfile"

  local cmd
  if [ "${#ports[@]}" -eq 1 ]; then
    cmd="ngrok http ${ports[0]} --log=stdout"
  else
    cmd="ngrok http ${ports[0]} http ${ports[1]} --log=stdout"
  fi
  log "Starting tunnel: ${cmd}"
  # shellcheck disable=SC2086
  eval "$cmd" >"$logfile" 2>&1 &
  PIDS+=("$!")

  # ngrok exposes one admin API listing both tunnels; wait for public URLs.
  local admin_api="http://127.0.0.1:4040/api/tunnels"
  local attempts=0
  while [ "$attempts" -lt 30 ]; do
    if curl -fsS --max-time 3 "$admin_api" >"$STATE_DIR/ngrok-api.json" 2>/dev/null; then
      break
    fi
    sleep 1
    attempts=$((attempts + 1))
  done

  local port urls=() url
  for port in "${ports[@]}"; do
    url=$(tunnel_url_for_port "$STATE_DIR/ngrok-api.json" "$port" "$admin_api")
    urls+=("$url")
  done

  # Publish resolved URLs back to caller via globals set by caller.
  NGROK_FRONTEND_URL="${urls[0]:-}"
  NGROK_BACKEND_URL="${urls[1]:-}"
}

# localtunnel (<name>.loca.lt). One process per port; URL is printed to stdout,
# so we parse it from the log file.
lt_start() {
  local port="$1"
  local logfile="$STATE_DIR/lt-$port.log"
  : > "$logfile"
  log "Starting tunnel: lt --port ${port}"
  lt --port "$port" >"$logfile" 2>&1 &
  PIDS+=("$!")

  local url=""
  local attempts=0
  while [ "$attempts" -lt 30 ]; do
    url=$(grep -o "https://[a-z0-9.-]*loca\.lt" "$logfile" 2>/dev/null | head -1 || true)
    [ -n "$url" ] && break
    sleep 1
    attempts=$((attempts + 1))
  done
  if [ "$port" = "$FRONTEND_PORT" ]; then
    LT_FRONTEND_URL="$url"
  else
    LT_BACKEND_URL="$url"
  fi
}

# --------------------------------------------------------------------------- #
# Main                                                                                    #
# --------------------------------------------------------------------------- #
TOOL="$(resolve_tunnel_tool)"
log "Tunnel tool: $TOOL"

[ -d "$BACKEND_DIR" ] || die "backend dir not found: $BACKEND_DIR"
[ -d "$FRONTEND_DIR" ] || die "frontend dir not found: $FRONTEND_DIR"
[ -f "$BACKEND_DIR/requirements.txt" ] || warn "backend/requirements.txt missing - check deps."

start_backend
wait_for_http "$BACKEND_HOST" "$BACKEND_PORT" "backend" || true

# ---------- tunnels (backend first when it must feed the frontend's API) ----
FRONTEND_URL=""
BACKEND_TUNNEL_URL="${BACKEND_PUBLIC_URL:-}"

if [ "$EXPOSE_BACKEND" -eq 1 ] && [ -z "$BACKEND_TUNNEL_URL" ]; then
  if [ "$TOOL" = "ngrok" ]; then
    NGROK_FRONTEND_URL=""; NGROK_BACKEND_URL=""
    # One ngrok process opens both tunnels; URLs resolved from the admin API.
    ngrok_start "$FRONTEND_PORT" "$BACKEND_PORT"
    FRONTEND_URL="$NGROK_FRONTEND_URL"
    BACKEND_TUNNEL_URL="$NGROK_BACKEND_URL"
  else
    LT_FRONTEND_URL=""; LT_BACKEND_URL=""
    lt_start "$BACKEND_PORT"
    lt_start "$FRONTEND_PORT"
    BACKEND_TUNNEL_URL="$LT_BACKEND_URL"
    FRONTEND_URL="$LT_FRONTEND_URL"
  fi
  if [ -z "$BACKEND_TUNNEL_URL" ]; then
    warn "Backend tunnel did not resolve - frontend will keep its default API URL."
  fi
else
  # Tunnel only the frontend.
  if [ "$TOOL" = "ngrok" ]; then
    NGROK_FRONTEND_URL=""; NGROK_BACKEND_URL=""
    ngrok_start "$FRONTEND_PORT"
    FRONTEND_URL="$NGROK_FRONTEND_URL"
  else
    LT_FRONTEND_URL=""; LT_BACKEND_URL=""
    lt_start "$FRONTEND_PORT"
    FRONTEND_URL="$LT_FRONTEND_URL"
  fi
fi

# Start the frontend now that the backend public URL (if any) is known. npx/next
# compile NEXT_PUBLIC_* at startup, so this env must be set before it boots.
if [ "$EXPOSE_BACKEND" -eq 1 ] && [ -n "$BACKEND_TUNNEL_URL" ]; then
  BACKEND_PUBLIC_URL="$BACKEND_TUNNEL_URL"
  log "  * backend API for the app -> ${BACKEND_PUBLIC_URL}/api/v1"
fi
start_frontend
wait_for_http "$FRONTEND_HOST" "$FRONTEND_PORT" "frontend" || true

# --------------------------------------------------------------------------- #
# Output                                                                          #
# --------------------------------------------------------------------------- #
printf '\n'
log "================== SHARE THESE URLS =================="
if [ -n "$FRONTEND_URL" ]; then
  log "  Frontend (send to a friend):  $FRONTEND_URL"
else
  warn "Frontend tunnel did not produce a public URL - check $STATE_DIR/*.log"
fi
if [ "$EXPOSE_BACKEND" -eq 1 ] && [ -n "$BACKEND_PUBLIC_URL" ]; then
  log "  Backend API (for the app)  :  ${BACKEND_PUBLIC_URL}/api/v1"
fi
log "======================================================"
printf '\n'
log "Press Ctrl+C to stop everything (backend + frontend + tunnel)."

# Keep the script in the foreground so Ctrl+C reaches it. `wait` blocks until
# the background jobs exit; the EXIT/INT/TERM trap then cleans them all up.
wait