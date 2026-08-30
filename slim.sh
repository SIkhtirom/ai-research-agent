#!/usr/bin/env bash
#
# slim.sh - Local Docker image optimization using Docker-Slim.
#
# Purpose: build the two local application images (FastAPI backend + Next.js
# frontend), then run Docker-Slim on each to strip unnecessary dependencies,
# cache, and build leftovers WITHOUT breaking the runtime.
#
# This is development/local tooling only - it does NOT deploy anywhere.
#
# Requirements (run in a Bash shell, e.g. Linux or WSL2 with Docker Desktop):
#   - Docker          (https://docs.docker.com/engine/install/)
#   - Docker-Slim     (https://github.com/slimtoolkit/slim)  binary `docker-slim`
#                     (newer releases also install an alias binary named `dslim`)
#
# Usage:
#   chmod +x slim.sh
#   ./slim.sh                 # build + slim both images
#   ./slim.sh --backend       # only the backend
#   ./slim.sh --frontend      # only the frontend
#   ./slim.sh --build-only    # build images but skip the slim step
#
set -euo pipefail

# --------------------------------------------------------------------------- #
# Configurable knobs (override from the shell without editing the file, e.g.
#   BACKEND_TAG=my-reg/backend:dev ./slim.sh
# )
# --------------------------------------------------------------------------- #
BACKEND_IMG="${BACKEND_IMG:-ai-research-backend}"
FRONTEND_IMG="${FRONTEND_IMG:-ai-research-frontend}"

# The slim output images get a `.slim` suffix to make them easy to identify.
BACKEND_SLIM="${BACKEND_SLIM:-${BACKEND_IMG}.slim}"
FRONTEND_SLIM="${FRONTEND_SLIM:-${FRONTEND_IMG}.slim}"

# Backend runtime config is injected via env (never baked into the image).
# These are passed to the analysis container so the probes run against the real
# configuration (see slim_backend below).

# Ports the apps listen on inside their containers.
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Number of HTTP probe shots per target (higher = more code paths exercised).
HTTP_PROBE_SHOTS="${HTTP_PROBE_SHOTS:-5}"

# Docker context directories.
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backend"
FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/frontend"

# Backward-compatible mapping: keep supporting the old NEXT_PUBLIC_API_BASE_URL
# ("…/api/v1" full URL). The preferred var is NEXT_PUBLIC_API_URL (origin only).
if [ -n "${NEXT_PUBLIC_API_BASE_URL:-}" ] && [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then
  case "$NEXT_PUBLIC_API_BASE_URL" in
    */api/v1|*/api/v1/) NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_BASE_URL%/api/v1*}" ;;
    *)                   NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_BASE_URL" ;;
  esac
fi

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
log()  { printf '\033[1;34m[ slim ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ slim ]\033[0m WARN: %s\n' "$*"; }
die()  { printf '\033[1;31m[ slim ]\033[0m ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker first."
if command -v docker-slim >/dev/null 2>&1; then
  SLIM_BIN="docker-slim"
elif command -v dslim >/dev/null 2>&1; then
  SLIM_BIN="dslim"
else
  die "docker-slim (or dslim) not found. Install it: https://github.com/slimtoolkit/slim"
fi
log "Using container optimizer: ${SLIM_BIN}"

# Default behaviour: do everything.
DO_BACKEND=1
DO_FRONTEND=1
BUILD_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --backend)   DO_BACKEND=1; DO_FRONTEND=0 ;;
    --frontend)  DO_FRONTEND=1; DO_BACKEND=0 ;;
    --build-only) BUILD_ONLY=1 ;;
    -h|--help)
      echo "Usage: $0 [--backend|--frontend] [--build-only] [-h]"
      echo "  --backend    only the FastAPI backend"
      echo "  --frontend   only the Next.js frontend"
      echo "  --build-only build images but skip the Docker-Slim step"
      echo "  -h, --help   show this help"
      exit 0 ;;
    *) warn "Unknown argument ignored: $arg" ;;
  esac
done

# Optionally clean up failed/incomplete target images at the start.
docker ps -aqf "name=ai-research" | xargs -r docker rm -f >/dev/null 2>&1 || true

# --------------------------------------------------------------------------- #
# Build stage
# --------------------------------------------------------------------------- #
build_backend() {
  log "Building backend image: ${BACKEND_IMG}"
  docker build -t "${BACKEND_IMG}" "${BACKEND_DIR}"
}

build_frontend() {
  log "Building frontend image: ${FRONTEND_IMG}"
  # Only the API origin is needed; the client appends /api/v1 at runtime.
  local api="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:8000}"
  docker build \
    --build-arg "NEXT_PUBLIC_API_URL=${api}" \
    -t "${FRONTEND_IMG}" \
    "${FRONTEND_DIR}"
}

# --------------------------------------------------------------------------- #
# Docker-Slim stage
# --------------------------------------------------------------------------- #
slim_backend() {
  log "Slimming backend -> ${BACKEND_SLIM}"
  log "  * HTTP probe on port ${BACKEND_PORT}, path /health"
  log "  * Warming up the local embedding model so its cache survives the trim"

  # --http-probe-exec runs inside the container before probes and forces the
  # sentence-transformers model (all-MiniLM-L6-v2) to be downloaded/loaded. With
  # --include-new the downloaded model cache is preserved instead of being
  # stripped as "unnecessary", and with --include-cert-all the CA roots needed
  # for HTTPS calls (LLM API, model download, url scraper) are kept.
  "${SLIM_BIN}" build \
    --target "${BACKEND_IMG}" \
    --tag "${BACKEND_SLIM}" \
    --http-probe \
    --http-probe-port "${BACKEND_PORT}" \
    --http-probe-full \
    --http-probe-shots "${HTTP_PROBE_SHOTS}" \
    --http-probe-cmd "GET /health" \
    --http-probe-exec "python -c \"from app.core.embeddings import get_embedding_provider; get_embedding_provider()\"" \
    --include-new \
    --include-cert-all \
    --include-path "/app/data" \
    --include-path "/root/.cache" \
    --env "VECTOR_STORE_BACKEND=faiss" \
    --env "EMBEDDING_PROVIDER=local"
}

slim_frontend() {
  log "Slimming frontend -> ${FRONTEND_SLIM}"
  log "  * HTTP probe on port ${FRONTEND_PORT}, full path scan"

  # Next.js needs its build output (.next) and node_modules. --include-new keeps
  # chunks Next generates at boot, --include-shell lets Next spawn helper
  # processes, and --http-probe-full hits several routes to exercise the bundle.
  "${SLIM_BIN}" build \
    --target "${FRONTEND_IMG}" \
    --tag "${FRONTEND_SLIM}" \
    --http-probe \
    --http-probe-port "${FRONTEND_PORT}" \
    --http-probe-full \
    --http-probe-shots "${HTTP_PROBE_SHOTS}" \
    --http-probe-cmd "GET /" \
    --http-probe-cmd "GET /healthz" \
    --http-probe-cmd "HEAD /" \
    --include-new \
    --include-shell \
    --include-cert-all \
    --include-path "/app/.next" \
    --include-path "/app/node_modules"
}

# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
if [ "${DO_BACKEND}" -eq 1 ]; then
  build_backend
  if [ "${BUILD_ONLY}" -eq 0 ]; then slim_backend; fi
fi

if [ "${DO_FRONTEND}" -eq 1 ]; then
  build_frontend
  if [ "${BUILD_ONLY}" -eq 0 ]; then slim_frontend; fi
fi

log "Locally-optimized images:"
[ "${DO_BACKEND}" -eq 1 ] && log "  * ${BACKEND_SLIM}"
[ "${DO_FRONTEND}" -eq 1 ] && log "  * ${FRONTEND_SLIM}"
log "Done."
