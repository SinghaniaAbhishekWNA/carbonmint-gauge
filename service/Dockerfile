# CarbonMint gauge reader v1 as a folder-watching service. Build from the repo root:
#   docker build -f service/Dockerfile -t carbonmint-gauge .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    IN_DIR=/data/in OUT_DIR=/data/out POLL_SECONDS=10 CM_PER_STRIPE=1.0 WORKERS=1 MAX_IMAGES=5000 \
    MODEL_PATH=/app/models/v2_confidence.json COLOUR_DIR=/app/colour HEARTBEAT=/tmp/heartbeat

WORKDIR /app
COPY service/requirements.txt /app/service/requirements.txt
RUN pip install --no-cache-dir -r /app/service/requirements.txt

# the reader, the trained confidence model, the colour-method locator, and the service itself
COPY gauge/ /app/gauge/
COPY models/v2_confidence.json /app/models/v2_confidence.json
COPY methods/teammate/pipeline/isolate.py methods/teammate/pipeline/locate.py methods/teammate/pipeline/rings.py /app/colour/
COPY service/gaugesvc/ /app/service/gaugesvc/

# the commit the image was built from; every report carries it
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT

RUN useradd --create-home --uid 10001 gauge && mkdir -p /data/in /data/out && chown -R gauge /data
USER gauge
WORKDIR /app/service
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 CMD ["python", "-m", "gaugesvc", "health"]
CMD ["python", "-m", "gaugesvc", "watch"]
