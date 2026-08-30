# Local Docker Image Optimization (Docker-Slim)

`./slim.sh` builds the two local application images and then trims them with
**Docker-Slim** to reduce size (strips unused dependencies, caches, and build
leftovers) — **without** deploying anywhere. It is development/local tooling.

> This project had **no Dockerfiles before**. This change adds minimal local
> images for the backend (`backend/Dockerfile`) and frontend
> (`frontend/Dockerfile`) so the slim script has something to build. The
> Dockerfiles are optimized for a local single-host setup, not for cloud deploy.

---

## 1. What the script does

1. **Build** the backend image `ai-research-backend` and the frontend image
   `ai-research-frontend` from their `Dockerfile`s.
2. **Slim** each image with `docker-slim build`, producing clearly-labeled
   output images suffixed `.slim`:
   - `ai-research-backend.slim`  (FastAPI, probes `/health` on port `8000`)
   - `ai-research-frontend.slim` (Next.js, probes `/` on port `3000`)
3. During analysis it applies safety/“do-not-delete” options so essential
   runtime files survive the trim:
   - **Backend:** warms up the local embedding model
     (`all-MiniLM-L6-v2`, `sentence-transformers`) via
     `--http-probe-exec` and keeps its cache (`/root/.cache`) and the runtime
     data dir (`/app/data`) with `--include-new` + `--include-path`. It also
     keeps CA root certs (`--include-cert-all`) so HTTPS calls to the LLM API,
     model downloads, and the URL scraper keep working.
   - **Frontend:** keeps the Next.js build output and runtime files
     (`/app/.next`, `/app/node_modules`, `--include-new`, `--include-shell`),
     and runs a full HTTP probe so generated chunks are exercised/kept.

HTTPS/`--include-cert-all` and the embedding warm-up are the "HTTP probe /
sensor" options called out for apps needing a short warm-up during analysis —
they ensure the optimizer does not strip files that are only touched on first
use.

---

## 2. Requirements

- **Docker** — https://docs.docker.com/engine/install/
- **Docker-Slim** — https://github.com/slimtoolkit/slim
  (installs a `docker-slim` binary; newer releases also install an alias `dslim`.
  The script auto-detects either.)
- Bash 4+ on **Linux** or **WSL2** (with Docker Desktop using Linux containers).

---

## 3. Give execute permission

```bash
chmod +x slim.sh
```

On WSL, `chmod +x` works normally since the file lives on the Windows filesystem
under `/mnt/...`.

---

## 4. Run it locally

```bash
./slim.sh                 # build + slim BOTH images
./slim.sh --backend       # only the FastAPI backend
./slim.sh --frontend      # only the Next.js frontend
./slim.sh --build-only    # build the images, skip the slim step
```

Optional overrides (set before running):

```bash
BACKEND_IMG=my-backend:dev ./slim.sh
FRONTEND_IMG=my-frontend:dev ./slim.sh
# API origin is compiled into the frontend image (client.ts appends /api/v1).
export NEXT_PUBLIC_API_URL=http://localhost:8000; ./slim.sh --frontend
# Legacy name still works: NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

First run of the backend slim step downloads the embedding model
(all-MiniLM-L6-v2), so it takes a little longer on a cold machine.

---

## 5. Verify

```bash
docker images                   # both original and `.slim` images listed
docker run --rm -p 8000:8000 ai-research-backend.slim   # curl /health -> ok
docker run --rm -p 3000:3000 ai-research-frontend.slim  # open http://localhost:3000
```

Check the size reduction with `docker images` (original vs `.slim`).

---

## 6. Notes & PRD alignment

- **Secrets are never baked in.** `backend/.env` (which currently holds a live
  API key) and `frontend/.env*` are ignored via `.dockerignore`; the runtime
  backend config is supplied through environment variables at run time.
  > Action recommended: rotate/rename the key in `backend/.env` since it is a
  > real credential.
- Error handling is friendly: the script uses `set -euo pipefail`, clear
  colored progress messages, and dies with a helpful message if `docker` or
  `docker-slim` is missing.
- If a slimmed image still misses a runtime file on first real request, re-run
  with reference to the probe/warm-up flags above (add the touched path via
  `--include-path` / `--include-new`); the optimizer only keeps what it
  observes during the probe.
