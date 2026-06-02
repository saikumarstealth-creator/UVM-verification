# UVM Verification Framework — User Guide

## Overview

Automated UVM testbench generation from YAML / FuseSoC `.core` specifications. Outputs a complete, ready-to-compile UVM environment for protocol interfaces (UART, SPI, I2C, APB, AXI4-Lite, Wishbone) with AI/ML-powered coverage optimization.

## Architecture

```
Spec (.core / .yaml)
       |
       v
 Generation Engine (Jinja2 + ML)
       |
       v
 +----------------------------+
 |  Generated UVM Testbench  |
 |  +----------------------+ |
 |  | testbench.sv          | |
 |  | interface_{name}.sv   | |
 |  | sequence_item_{n}.sv  | |
 |  | driver_{name}.sv      | |
 |  | monitor_{name}.sv     | |
 |  | agent_{name}.sv       | |
 |  | env_{name}.sv         | |
 |  | scoreboard_{name}.sv  | |
 |  | coverage_collector.sv | |
 |  | protocol_checker.sv   | |
 |  | ral_model_{name}.sv   | |
 |  | base_sequence_{n}.sv  | |
 |  | test_{name}.sv        | |
 |  +----------------------+ |
 +----------------------------+
```

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional: dev/lint
```

### 2. Generate a UVM testbench

```bash
# From YAML spec
python -m src.main --spec configs/uart_demo.yaml

# From FuseSoC .core spec
python -m src.main --spec configs/uart16550-1.5.core

# With auto-training (AI coverage optimization)
python -m src.main --spec configs/uart16550-1.5.core --auto-train --max-iterations 3
```

### 3. Output

```
output/{design_name}_tb/
  testbench.sv              # Top-level module
  interface_{name}.sv       # Clocking + modport
  sequence_item_{name}.sv   # Transaction object
  driver_{name}.sv          # Bus driver
  monitor_{name}.sv         # Bus monitor
  agent_{name}.sv           # Agent (sequencer + driver + monitor)
  environment_{name}.sv     # Env (agent + scoreboard + coverage + RAL)
  scoreboard_{name}.sv      # Scoreboard (TX/RX compare, error check)
  coverage_collector_{name}.sv  # Functional coverage groups
  protocol_checker_{name}.sv    # SVA assertions
  ral_model_{name}.sv       # RAL model + adapter + predictor
  base_sequence_{name}.sv   # Sequence library
  test_{name}.sv            # Test library
  compile.f                 # Compile file list
  sim_{name}.tcl            # Simulation script
```

## Spec Format

### YAML format

```yaml
design_name: uart16550
protocol: uart

interfaces:
  - name: bus
    direction: slave
    protocol: wishbone
    signals:
      - {name: addr, direction: input, width: 3}
      - {name: data_in, direction: input, width: 8}
      - {name: data_out, direction: output, width: 8}

  - name: serial
    direction: master
    protocol: uart
    signals:
      - {name: tx, direction: output, width: 1}
      - {name: rx, direction: input, width: 1}

registers:
  - name: RBR
    address: 0x00
    access: ro
    size: 8
    description: Receiver Buffer Register
  - name: THR
    address: 0x00
    access: wo
    size: 8
  - name: IER
    address: 0x01
    access: rw
    size: 8
  - name: LCR
    address: 0x03
    access: rw
    size: 8
    reset: 0x03

clocks:
  clk: 50MHz
  reset: {name: rst_n, polarity: active_low}
```

### FuseSoC .core format

See `configs/uart16550-1.5.core` for a complete example.

## UVM VIP Integration

### Packaging as a VIP

The generated output is structured as a self-contained UVM Verification IP:

```
{design_name}_vip/
  pkg/
    {design_name}_vip_pkg.sv       # UVM package (all files)
    {design_name}_reg_pkg.sv        # RAL package
  src/
    {design_name}_if.sv             # Interface
    {design_name}_agent.sv          # Agent
    {design_name}_env.sv            # Environment
    {design_name}_driver.sv         # Driver
    {design_name}_monitor.sv        # Monitor
    {design_name}_scoreboard.sv     # Scoreboard
    {design_name}_coverage.sv       # Coverage collector
    {design_name}_checker.sv        # Protocol checker
    {design_name}_ral.sv            # RAL model
    {design_name}_sequences.sv      # Sequence library
    {design_name}_tests.sv          # Test library
  sim/
    compile.f                       # Compile list
    sim.do                          # Questa script
    sim.tcl                         # Generic TCL script
  examples/
    smoke_test.sv                   # Standalone testbench
```

### Integration into a larger SoC environment

```systemverilog
// 1. Import the VIP
import uart_vip_pkg::*;

// 2. Instantiate interface
uart_if uart_if_inst (
  .clk   (sys_clk),
  .rst_n (sys_rst_n),
  .tx    (uart_tx),
  .rx    (uart_rx)
);

// 3. Configure via config_db
initial begin
  uvm_config_db#(virtual uart_if)::set(
    null, "uvm_test_top", "vif", uart_if_inst
  );
end

// 4. Run test
initial begin
  run_test("uart_smoke_test");
end
```

### Configuration parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `protocol` | string | `"uart"` | Protocol selection |
| `model_type` | string | `"v2"` | Generation model (template / v2) |
| `rl_strategy` | string | `"ucb"` | RL exploration strategy |
| `enable_learning` | bool | true | Enable RL + coverage feedback |
| `strict_uvm` | bool | true | Generate IEEE 1800.2 compliant code |
| `max_iterations` | int | 1 | Auto-training iterations |

## AI/ML Features

### Coverage Prediction

The coverage predictor uses a 3-model ensemble (RandomForest + GradientBoosting + LinearRegression) with Ridge meta-blender to predict functional coverage gaps and suggest targeted sequences.

### Reinforcement Learning

Q-learning with:
- Double Q-learning (two independent Q-tables)
- Prioritized experience replay
- N-step returns
- Eligibility traces
- 5 exploration strategies (epsilon-greedy, softmax, UCB, Thompson, NoisyNet)

States are encoded as `{protocol}:{file_type}:{complexity}`.

### Auto-Training Loop

```
1. Generate UVM testbench
2. Run simulation (or stub)
3. Predict coverage gaps
4. Generate targeted sequences
5. Re-train RL model
6. Repeat until coverage target met
```

## Regression Management

### Running regressions

```bash
# Single test
python -m src.main --spec configs/uart16550-1.5.core \
  --test smoke

# All tests
python regression/run_regression.py \
  --spec configs/uart16550-1.5.core

# Multi-seed regression
python regression/run_regression.py \
  --spec configs/uart16550-1.5.core \
  --seeds 100 \
  --tests smoke,loopback,interrupt
```

### YAML regression spec

```yaml
regression:
  name: uart_full_regression
  spec: configs/uart16550-1.5.core
  tests:
    - uart_smoke_test
    - uart_reg_access_test
    - uart_loopback_test
    - uart_interrupt_test
    - uart_fifo_test
    - uart_random_test
  seeds: [10, 20, 30, 50, 100]
  simulator: questa
  coverage: true
  output: results/
```

## Simulator Support

| Simulator | Status | Notes |
|-----------|--------|-------|
| Questa/ModelSim | ✅ | Full support via .do / .tcl script |
| VCS | ✅ | Compatible (IEEE 1800.2 compliant) |
| Xcelium | ✅ | Compatible |
| Icarus Verilog | ✅ | Basic support (stub mode) |

## Project Structure

```
UVM-verification/
  configs/             # Spec files (.yaml, .core)
  docs/                # Documentation
  frontend/            # React UI
  protocols/           # Protocol definitions (UART, SPI, I2C, etc.)
  regression/          # Regression scripts
  src/                 # Core engine
    features/          # Spec feature extraction
    generation/        # Template engine
      templates/       # Jinja2 UVM templates
    models/            # ML models (RL, coverage predictor, etc.)
    evaluation/        # Quality scoring, SV checking
    pipeline.py        # Auto-training pipeline
  vip/                 # Packaged VIP files
  output/              # Generated testbenches
```

## Testing

```bash
# Run unit tests
python -m pytest tests/

# Test coverage prediction
python -m pytest tests/test_coverage_predictor.py -v

# Test RL learner
python -m pytest tests/test_rl_learner.py -v

# Test pipeline end-to-end
python test_pipeline.py
```

## Docker

```bash
docker-compose up --build
# Frontend: http://localhost:7860
# API:      http://localhost:8000/docs
```

## License

MIT License — see LICENSE file.
