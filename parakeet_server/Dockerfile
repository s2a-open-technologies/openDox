# syntax=docker/dockerfile:1
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY parakeet_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download model at build time for faster container starts (~300MB)
RUN python -c "import onnx_asr; onnx_asr.load_model('nemo-parakeet-tdt-0.6b-v3')"

COPY parakeet_server/main.py .

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/v1/models')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001"]