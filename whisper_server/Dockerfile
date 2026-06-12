# syntax=docker/dockerfile:1
#  openDox - Standalone Whisper transcription server
#  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
#
#  CUDA + cuDNN runtime base — required by CTranslate2 (faster-whisper) for GPU.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Python + ffmpeg (faster-whisper decodes audio via ffmpeg/av)
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

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
