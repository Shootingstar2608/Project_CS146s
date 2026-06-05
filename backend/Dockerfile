# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
#  Stage 1: Builder — install Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install Python dependencies into a separate prefix so we can copy cleanly.
COPY backend/requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
#  Stage 2: Runtime — lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the code this service needs.
COPY backend ./backend
COPY agent ./agent
COPY pipeline ./pipeline
COPY docs ./docs

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
     "--log-level", "info"]
