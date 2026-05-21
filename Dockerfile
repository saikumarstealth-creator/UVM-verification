# Multi-stage: frontend build + Python backend

# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim AS backend-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    iverilog \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-builder /app/build /app/frontend/build

RUN pip install --no-cache-dir -e .

RUN groupadd -r uvmgen && useradd -r -g uvmgen -d /app -s /sbin/nologin uvmgen
RUN mkdir -p /app/output /app/logs /var/data && chown -R uvmgen:uvmgen /app /var/data

EXPOSE 8000

ENV UVMGEN_OUTPUT_DIR=/var/data/uvmgen_output

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"

USER uvmgen

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
