.PHONY: install test clean run

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	python -m pytest tests/ -v --cov=src --cov-report=term-missing

run:
	python -m src.main --spec configs/uart_demo.yaml

run-json:
	python -m src.main --spec configs/uart_demo.yaml --json

eval-only:
	python -m src.main --spec configs/uart_demo.yaml --eval-only

clean:
	rm -rf output/* logs/* .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	rm -rf models/saved/*.json

docker-build:
	docker build -t uvm-tb-generator .

docker-run:
	docker run --rm -v $(PWD)/output:/app/output uvm-tb-generator --spec configs/uart_demo.yaml

lint:
	python -m flake8 src/ tests/

# ============================================================================
# UVM Simulation Targets — run against generated output/
# ============================================================================
UVM_HOME   ?= $(UVM_HOME)
SIM        ?= icarus
DESIGN     ?= uart_top
OUT_DIR    := output
LOG_DIR    := $(OUT_DIR)/logs
COV_DIR    := $(OUT_DIR)/coverage
WORK_DIR   := $(OUT_DIR)/work
RTL_FILES  := $(wildcard rtl/*.v rtl/*.sv)
GEN_FILES  := $(wildcard $(OUT_DIR)/*.sv $(OUT_DIR)/*.v)
TOP        := $(DESIGN)_top

.PHONY: compile-sv run-sv smoke-sv regress-sv clean-sv

# ── Icarus (iverilog) ────────────────────────────────────────────────────────
compile-icarus:
	mkdir -p $(LOG_DIR)
	iverilog -g2012 -o $(OUT_DIR)/simv $(addprefix -I, $(UVM_HOME)/src) \
		$(GEN_FILES) $(RTL_FILES) 2>&1 | tee $(LOG_DIR)/compile.log

run-icarus:
	cd $(OUT_DIR) && ./simv 2>&1 | tee $(LOG_DIR)/sim.log

# ── VCS ──────────────────────────────────────────────────────────────────────
compile-vcs:
	mkdir -p $(LOG_DIR) $(COV_DIR)
	vlogan -full64 -sverilog +v2k -timescale=1ns/1ps -debug_all \
		-l $(LOG_DIR)/vcs_compile.log $(GEN_FILES) $(RTL_FILES)
	vcs -debug_all -l $(LOG_DIR)/vcs_elab.log $(TOP)

run-vcs:
	./simv -l $(LOG_DIR)/sim.log

# ── Questa ───────────────────────────────────────────────────────────────────
compile-questa:
	mkdir -p $(LOG_DIR) $(WORK_DIR)
	vlib $(WORK_DIR)/work
	vmap work $(WORK_DIR)/work
	vlog -64 -novopt -sv +UVM_NO_RELNOTES -work work \
		$(GEN_FILES) $(RTL_FILES) 2>&1 | tee $(LOG_DIR)/compile.log

run-questa:
	vsim -c -do "run -all; exit" -l $(LOG_DIR)/sim.log $(TOP)

# ── Common targets ──────────────────────────────────────────────────────────
compile-sv: compile-$(SIM)

run-sv: run-$(SIM)

# ── Smoke test (quick compile + run) ────────────────────────────────────────
smoke-sv: SIM=icarus
smoke-sv:
	@echo "=== UVM Smoke Test ==="
	$(MAKE) compile-icarus
	$(MAKE) run-icarus
	@echo "=== Smoke test complete ==="

# ── Regression (all generated test cases) ────────────────────────────────────
regress-sv: compile-icarus
	@echo "=== UVM Regression ==="
	$(MAKE) run-icarus
	@echo "=== Regression complete ==="

clean-sv:
	rm -rf $(OUT_DIR)/simv $(OUT_DIR)/simv.vdb $(OUT_DIR)/simv.daidir
	rm -rf $(WORK_DIR) $(COV_DIR) transcript vsim.wlf
	rm -f *.vpd *.vcd *.fsdb DVE* csrc* *.key
