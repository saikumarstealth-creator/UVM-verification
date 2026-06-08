---
title: UVM Verification Framework
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: src/api/server.py
pinned: false
---

# UVM Verification Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)
![UVM IEEE 1800.2](https://img.shields.io/badge/UVM-1800.2-802A99)

Automated UVM testbench generation from YAML / FuseSoC `.core` specifications — with protocol libraries, schema validation, coverage-driven auto-training, and CI/CD integration.

**Supports:** UART (16550), SPI, I2C, APB, AXI4-Lite, Wishbone

---

## Quick Start

```bash
pip install -r requirements.txt

# Generate a UVM testbench
python -m src.main --spec configs/uart16550-1.5.core

# With AI auto-training
python -m src.main --spec configs/uart16550-1.5.core --auto-train --max-iterations 3

# Run regression
python regression/run_regression.py --spec configs/uart16550-1.5.core
```

## Features

### UVM Generation
- Complete UVM environment: agent, driver, monitor, scoreboard, coverage, RAL
- IEEE 1800.2-2020 compliant SystemVerilog
- Spec-driven register map with DLAB-aware addressing (UART 16550)
- Functional coverage groups with cross coverage
- SVA protocol assertions
- RAL model with adapter and predictor

### AI/ML Coverage Optimization
- **Reinforcement Learning**: Double Q-learning with prioritized replay, n-step returns, eligibility traces
- **Coverage Prediction**: 3-model ensemble (RF + GBR + LR) with confidence calibration
- **Auto-Training**: Generate → simulate → analyze → improve loop
- **Exploration Strategies**: epsilon-greedy, softmax, UCB, Thompson, NoisyNet

### CI/CD
- Docker container with FastAPI + React frontend
- Hugging Face Space deployment ready
- REST API for generation and evaluation
- ZIP export of generated testbenches

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | Full walkthrough: install, spec format, integration, regression |
| [API Docs](https://localhost:8000/docs) | FastAPI Swagger UI (when running) |

## Project Structure

```
├── configs/           # YAML / .core specification files
├── docs/              # Documentation
├── frontend/          # React UI (Vite + TypeScript)
├── protocols/         # Protocol definitions
├── regression/        # Regression scripts
├── src/
│   ├── features/      # Spec feature extraction
│   ├── generation/    # Jinja2 templates + engine
│   ├── models/        # RL, coverage prediction, spec adaptation
│   ├── evaluation/    # SV syntax check, quality scoring
│   ├── pipeline.py    # Auto-training pipeline
│   └── main.py        # CLI entry point
├── vip/               # Packaged VIP files
└── output/            # Generated testbenches
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
# Frontend: http://localhost:7860
# API:      http://localhost:8000/docs
```

## Regression

```bash
# Quick smoke test
python regression/smoke.py

# Full regression
python regression/run_regression.py \
  --regression regression/uart_full.yaml

# Custom test + seeds
python regression/run_regression.py \
  --spec configs/uart16550-1.5.core \
  --tests smoke,loopback,interrupt \
  --seeds 5
```

## Tests

```bash
pytest tests/ -v
```

## <big><big>Developer: Sai Kumar Taraka</big></big>

## License

MIT
