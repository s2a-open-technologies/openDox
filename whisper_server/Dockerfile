# syntax=docker/dockerfile:1
#  openDox - Standalone Whisper transcription server
#  Copyright (C) 2026 Christopher Abanilla <christopher.abanilla@gmx.de>
#
#  Defaults to the NVIDIA GPU image (CUDA 12.4.1 + cuDNN) — required by
#  CTranslate2/faster-whisper for GPU inference. To build a CPU-only image
#  (smaller, no CUDA base):
#    docker build --build-arg DEVICE=cpu -f whisper_server/Dockerfile -t opendox-whisper:cpu .
#  faster-whisper/CTranslate2 ship a single wheel that supports both CPU and
#  GPU, so only the base image changes between DEVICE=cpu/gpu — remember to
#  also set WHISPER_DEVICE=cpu at runtime when using the CPU image, the CUDA
#  runtime is not present in that base.

# ─── Base image: CUDA+cuDNN (default) or plain Python for CPU ──────────
# The GPU base matches parakeet_server/Dockerfile (CUDA 12.4.1 + cuDNN) so
# both containers can share the same host driver.
ARG DEVICE=gpu
FROM python:3.12-slim AS base-cpu
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS base-gpu

# Final stage selects the right base via the DEVICE arg.
FROM base-${DEVICE} AS final

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Python + ffmpeg (faster-whisper decodes audio via ffmpeg/av).
# The CUDA base is Ubuntu 22.04 (apt), the CPU base is Debian slim (apt) —
# both use the same package names.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY whisper_server/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY whisper_server/app.py ./app.py

# Persist downloaded models across restarts (mount a volume here)
ENV HF_HOME=/var/lib/whisper \
    WHISPER_MODEL=large-v3-turbo \
    WHISPER_DEVICE=cuda \
    WHISPER_COMPUTE_TYPE=float16

EXPOSE 9000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002"]
