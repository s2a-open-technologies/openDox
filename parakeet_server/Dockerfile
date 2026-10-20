# syntax=docker/dockerfile:1
#  openDox - Parakeet ASR server (Silero VAD + Parakeet TDT v3 ONNX)
#  Copyright (C) 2025 S2A Open Technologies gGmbH
#  SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
#  SPDX-License-Identifier: AGPL-3.0-or-later
#
#  Defaults to the NVIDIA GPU image (CUDA 13.0.2 + cuDNN) so the container
#  uses the GPU whenever the host provides one. To build a CPU-only image
#  (smaller, no CUDA base):
#    docker build --build-arg DEVICE=cpu -t opendox-parakeet:cpu .
#  The GPU build still works on CPU-only hosts — onnxruntime falls back to
#  CPUExecutionProvider automatically — but the image is larger.

# ─── Base image: CUDA+cuDNN (default) or plain Python for CPU ──────────
# Whisper (CUDA 12.4.1) and Parakeet (CUDA 13) can still share one host and GPU:
# a driver >= 580 runs both.
ARG DEVICE=gpu
FROM python:3.12-slim AS base-cpu
# Dynamically quantized int8 weights (~0.7 GB instead of ~2.5 GB): built for
# CPU inference. Not used on the GPU image, where the CUDA provider runs part of
# the int8 ops on the CPU and the copies cost more than int8 saves.
ENV PARAKEET_QUANTIZATION=int8
# Ubuntu 24.04 + CUDA 13: every onnxruntime-gpu >= 1.29 (the first with linux/aarch64
# wheels) needs Python >= 3.11 AND is linked against CUDA 13 (libcublasLt.so.13). On a
# CUDA 12 base the CUDA provider silently fails to load and onnxruntime runs on the CPU.
# The host needs an NVIDIA driver >= 580 for CUDA 13.
FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04 AS base-gpu
ENV PARAKEET_QUANTIZATION=

# Final stage selects the right base via the DEVICE arg.
FROM base-${DEVICE} AS final

ARG DEVICE=gpu
# PIP_BREAK_SYSTEM_PACKAGES: Ubuntu 24.04 marks its Python as externally managed
# (PEP 668); this container is the only consumer, so installing into it is fine.
ENV DEVICE=${DEVICE} \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

# System deps: ffmpeg for audio decoding, curl for healthcheck.
# The CUDA base is Ubuntu 24.04 (apt), the CPU base is Debian slim (apt) —
# both use the same package names.
# The `python` symlink points at the same interpreter pip3 installs for
# (`command -v python3`): on the Ubuntu/CUDA base that's /usr/bin/python3,
# on python:3.12-slim it's the image's own /usr/local/bin/python3. A hard
# /usr/bin/python3 target breaks the slim base — pip3 there is Python 3.12's
# pip, so `python` (3.11) couldn't import anything pip3 installed (this is
# what made the CPU build fail).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf "$(command -v python3)" /usr/local/bin/python

WORKDIR /app

# Model caches for the unprivileged runtime user (see USER below):
#   HF_HOME      — Parakeet ASR model via the default HuggingFace cache.
#                 Without this the cache lands in /root/.cache, which is
#                 unreadable once USER downgrades.
#   RTT_VAD_DIR  — Silero VAD flat directory. streaming.py defaults this to
#                 <repo>/models/silero-vad, a path that doesn't exist in
#                 this container, so pointing it at the build-time download
#                 also fixes a silent runtime re-download that used to hit
#                 the network on every container start.
#   HF_HUB_DISABLE_XET — hf-xet (pulled in by onnx-asr's [hub] extra) stores
#                 blobs in a nested shared pool OUTSIDE the model directory
#                 (hub/blobs/xx/...). The Parakeet ONNX model uses external
#                 data (.onnx.data), and onnxruntime validates that external
#                 data files live in the SAME directory as the model file —
#                 with xet the .onnx and .onnx.data blobs end up in different
#                 shards and every load fails with "External data path
#                 escapes model directory". Plain HTTP downloads keep the
#                 classic flat per-model blobs/ layout and load fine.
ENV HF_HOME=/app/models/hf \
    RTT_VAD_DIR=/app/models/silero-vad \
    HF_HUB_DISABLE_XET=1

# Install onnx-asr with the matching extra. [gpu] pulls onnxruntime-gpu
# (CUDA 13), [cpu] pulls plain onnxruntime. onnxruntime is imported
# directly in streaming.py for the raw Silero VAD session, so it must be
# installed explicitly regardless of the extra.
COPY parakeet_server/requirements.cpu.txt ./requirements.cpu.txt
COPY parakeet_server/requirements.gpu.txt ./requirements.gpu.txt
RUN pip3 install --no-cache-dir -r requirements.${DEVICE}.txt

# Download models at build time for faster container starts.
# Parakeet ASR (~300MB) goes to the default HF cache; Silero VAD (~2MB) goes
# into a flat directory under /app/models/silero-vad so onnxruntime accepts it
# (the HF cache stores files as symlinks into blobs/, which onnxruntime rejects
# for the raw VAD session we drive directly in streaming.py).
# providers=["CPUExecutionProvider"] here only affects this one-time download
# session — `docker build` never has GPU access (unlike `docker run --gpus`),
# so leaving the default provider list would just make onnxruntime try CUDA,
# fail with "GPU=-1 cudaSetDevice()", and silently retry on CPU anyway. The
# actual runtime provider selection is independent (main.py/streaming.py
# re-resolve providers fresh at server start).
# Only the weights matching PARAKEET_QUANTIZATION (set per base stage above)
# are baked in. Overriding it at runtime still works: onnx-asr then downloads
# the other variant from HF on the first start.
RUN python -c "import os, onnx_asr; onnx_asr.load_model('nemo-parakeet-tdt-0.6b-v3', quantization=os.environ.get('PARAKEET_QUANTIZATION') or None, providers=['CPUExecutionProvider'])" \
    && python -c "import onnx_asr; onnx_asr.load_vad('silero', path='/app/models/silero-vad', providers=['CPUExecutionProvider'])"

COPY parakeet_server/streaming.py .
COPY parakeet_server/main.py .

# Unprivileged runtime user (UID/GID 1000). Both model caches live in /app
# and are read-only at runtime (pre-downloaded at build time), uvicorn binds
# an unprivileged port, and temp files go to /tmp via tempfile — nothing
# needs root. chown -R /app so the pre-downloaded caches are readable.
# Ubuntu 24.04 images already ship a `ubuntu` user with UID 1000; drop it first
# (the slim CPU base has none, hence `|| true`).
RUN (userdel -r ubuntu 2>/dev/null || true) \
    && useradd --no-log-init -m -u 1000 appuser \
    && chown -R 1000:1000 /app

USER appuser

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5001${ROOT_PATH}/v1/models || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001", "--ws-ping-interval", "20", "--ws-ping-timeout", "60"]