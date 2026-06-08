# syntax=docker/dockerfile:1
#  openDox - Medical transcription platform
#  Copyright (C) 2025  crizz <christopher.abanilla@gmx.de>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ═══════════════════════════════════════════════════════════════════════════════
#  Stage 1: Build the React frontend
#  ═══════════════════════════════════════════════════════════════════════════════
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

ARG VITE_ROOT_PATH=""
ENV VITE_ROOT_PATH=${VITE_ROOT_PATH}

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2: Python backend
# ═══════════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim-bookworm

# Install system deps (ffmpeg for audio processing, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# Copy backend code
COPY backend/ ./backend/
COPY main.py ./
COPY config.py ./
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Copy built frontend static files
COPY --from=frontend-builder /app/frontend/dist ./static/

# Create runtime directories
RUN mkdir -p logs chunks models_cache certs

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000${ROOT_PATH:-}/api/endpoint || exit 1

EXPOSE 5000

# Entrypoint: run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 5000"]
