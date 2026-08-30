from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import chat, export, ingestion, sessions
from .core.config import settings


# --------------------------------------------------------------------------- #
# CORS - accept requests from the app, local dev, and remote tunnel origins.  #
# --------------------------------------------------------------------------- #
def _parse_origins(raw: str) -> list[str]:
    """Turn a comma-separated origin list into a trimmed list."""
    return [o.strip() for o in raw.split(",") if o.strip()]


ALLOWED_ORIGINS = _parse_origins(settings.cors_allow_origins)

# Dynamic allow for tunnel hosts used by expose.sh (NGrok / localTunnel), so the
# backend never blocks a tester just because their URL came from a tunnel tool.
TUNNEL_ORIGIN_REGEX = r"https?://(.+\.)?(ngrok\.io|ngrok-free\.app|loca\.lt)$"

# Wildcard mode: reflect any origin (no credentials, so this is not a security
# concern here). Handy for `EXPOSE_BACKEND=1 ./expose.sh`.
if settings.cors_allow_any_origin:
    allowed_origins = ["*"]
    allowed_origin_regex = None
else:
    allowed_origins = ALLOWED_ORIGINS
    allowed_origin_regex = TUNNEL_ORIGIN_REGEX

app = FastAPI(
    title="AI Research & Knowledge Synthesis Agent",
    description="Backend API for collecting, extracting, and synthesizing research information from multiple sources.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Attach common security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a generic message for unhandled errors so internals never leak."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan internal. Silakan coba lagi."},
    )


app.include_router(ingestion.router)
app.include_router(chat.router)
app.include_router(export.router)
app.include_router(sessions.router)


@app.get("/")
def read_root() -> dict:
    return {"message": "AI Research & Knowledge Synthesis Agent API is running"}


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
