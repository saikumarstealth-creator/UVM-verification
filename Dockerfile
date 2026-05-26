FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN pip install --no-cache-dir -e .

RUN groupadd -r uvmgen && useradd -r -g uvmgen -d /app -s /sbin/nologin uvmgen
RUN mkdir -p /app/output /app/logs /var/data && chown -R uvmgen:uvmgen /app /var/data

EXPOSE 7860

ENV UVMGEN_OUTPUT_DIR=/var/data/uvmgen_output

USER uvmgen

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--log-level", "info"]
