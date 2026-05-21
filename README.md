# UVM-verification

Automated UVM testbench generation from YAML / `.core` specifications — with **protocol libraries**, **schema validation**, **coverage-driven auto-training**, and **CI/CD integration**.

## Quick Start

```bash
pip install -r requirements.txt

python -m src.main --spec configs/uart_demo.yaml
python -m src.main --spec configs/uart16550-1.5.core
python -m src.main --spec configs/uart16550-1.5.core --auto-train --max-iterations 3
```

## API Server

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

## Frontend

```bash
cd frontend && npm install && npm run build
```

## Docker

```bash
docker-compose up --build
```
