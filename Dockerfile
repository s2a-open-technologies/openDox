#  openDox - Medical transcription platform
#  Copyright (C) 2025  S2A Open Technologies gGmbH
#  SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
#  SPDX-License-Identifier: AGPL-3.0-or-later
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
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Copy built frontend static files
COPY --from=frontend-builder /app/backend/static ./backend/static/

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Create runtime directory for transient PCM recording chunks (ephemeral,
# self-cleaning at startup — see run.py). Everything durable now lives in
# Postgres or S3-compatible object storage, not on local disk.
RUN mkdir -p chunks

# Unprivileged runtime user (UID/GID 1000) — nothing in this container needs
# root: uvicorn binds an unprivileged port, Alembic migrations run as this
# user, and every runtime write stays inside /app (recording chunks, the
# ROOT_PATH injection into backend/static/index.html) or /tmp. chown -R /app
# so those writes succeed; a fresh app-chunks volume inherits this ownership
# via Docker's volume copy-up. Volumes created by older root-based images
# need a one-time chown — see docs/SECURITY.md "Docker Security".
RUN useradd --no-log-init -m -u 1000 appuser \
    && chown -R 1000:1000 /app

USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000${ROOT_PATH:-}/api/endpoint || exit 1

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
