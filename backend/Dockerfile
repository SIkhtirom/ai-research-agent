# Local development image for the FastAPI backend.
# Config is injected at RUN time via environment variables (never baked in), so
# .env and data/ are deliberately excluded (see .dockerignore).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VECTOR_STORE_BACKEND=${VECTOR_STORE_BACKEND:-faiss} \
    EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-local}

# Minimal runtime tooling. tesseract-ocr is the optional OCR fallback used by
# pytesseract for scanned/image PDFs; drop it if you disabled OCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache

COPY app ./app
RUN mkdir -p /app/data

EXPOSE 8000

# PaaS providers (Back4app, Render, Railway, ...) sometimes inject a PORT env
# var that their ingress expects. Default to 8000 so local / Docker-Slim runs
# are unchanged. The 0.0.0.0 bind is required inside any container.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
