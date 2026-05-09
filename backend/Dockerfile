# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
#  Stage 1: Builder — install Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps required by some Python packages (libmagic, pymupdf, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libmagic1 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a separate prefix so we can copy cleanly
# Dùng bản CPU của PyTorch để giảm dung lượng từ 3GB+ xuống còn ~200MB
COPY backend/requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Install sentence-transformers (for local embeddings — not in base requirements)
RUN pip install --prefix=/install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu sentence-transformers==2.7.0

# ─────────────────────────────────────────────────────────────────────────────
#  Stage 2: Runtime — lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the code this service needs.
COPY backend ./backend
COPY agent ./agent
COPY pipeline ./pipeline
COPY docs ./docs
COPY detai_extracted.txt ./detai_extracted.txt

# Set PYTHONPATH so that `from app.xxx` and `from agent.xxx` and
# `from pipeline.xxx` all resolve correctly
ENV PYTHONPATH=/app/backend:/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create directories for runtime data
RUN mkdir -p /app/data/uploads /app/data/faiss_index

# Expose FastAPI port
EXPOSE 8000

# Default command: run Uvicorn (can be overridden by docker-compose for Celery)
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
