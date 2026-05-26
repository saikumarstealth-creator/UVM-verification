"""
FastAPI backend for UVM TB Generator.
Serves both the REST API and the React frontend from a single process
for free-tier deployment (Render, Fly.io, PythonAnywhere).
"""

from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from src.config import ConfigLoader
from src.exceptions import UVMGenError
from src.pipeline import TBPipeline

logger = logging.getLogger("uvmgen")
logger.setLevel(logging.INFO)

# ── Find frontend build directory ─────────────────────────────────
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"

# ── Request / Response models ─────────────────────────────────────

class PipelineRequest(BaseModel):
    spec_yaml: str = Field(..., description="YAML or .core specification content")
    design_name: str = Field(default="unnamed")
    auto_train: bool = Field(default=False)
    max_iterations: int = Field(default=5, ge=1, le=50)
    coverage_target: float = Field(default=90.0, ge=0, le=100)
    num_seeds: int = Field(default=3, ge=1, le=20)
    overwrite: bool = Field(default=False)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.3.0"
    api_version: str = "v1"
    simulators: List[str] = ["stub", "icarus"]


class VersionInfo(BaseModel):
    version: str
    coverage: float
    files: int
    iteration: int


class PipelineResponse(BaseModel):
    design_name: str
    status: str
    versions: List[VersionInfo]
    coverage_trend: list
    coverage_gaps: list
    artifacts: list
    total_files: int
    iterations: int
    simulator: str


# ── Pipeline singleton ─────────────────────────────────────────────

pipeline_instance: Optional[TBPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline_instance
    logger.info("UVM TB Generator starting...")
    pipeline_instance = TBPipeline()
    yield
    logger.info("UVM TB Generator shutting down...")


app = FastAPI(title="UVM TB Generator", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception handlers ─────────────────────────────────────────────

@app.exception_handler(UVMGenError)
async def uvmgen_error_handler(request, exc: UVMGenError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def generic_error_handler(request, exc: Exception):
    logger.error("Unhandled: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": str(exc)},
    )


# ── API Routes ─────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.get("/api/versions")
async def list_versions():
    if not pipeline_instance:
        raise HTTPException(503, "Pipeline not initialized")
    trend = pipeline_instance.registry.coverage_trend()
    return {"versions": trend}


@app.post("/api/run-pipeline", response_model=PipelineResponse)
async def run_pipeline(req: PipelineRequest):
    global pipeline_instance
    if not pipeline_instance:
        pipeline_instance = TBPipeline()

    try:
        import tempfile, os as _os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(req.spec_yaml)
            spec_path = f.name

        pipeline_instance.cfg.auto_train.enabled = req.auto_train
        pipeline_instance.cfg.auto_train.max_iterations = req.max_iterations
        pipeline_instance.cfg.auto_train.coverage_target = req.coverage_target
        pipeline_instance.cfg.auto_train.num_seeds = req.num_seeds
        pipeline_instance.cfg.generation.overwrite = req.overwrite

        result = pipeline_instance.run(spec_path)

        try:
            _os.unlink(spec_path)
        except OSError:
            pass

        analysis = result.get("coverage_analysis") or {}
        gaps = [{"bin": g["bin"], "addr": g.get("addr"), "dir": g.get("dir")}
                for g in (analysis.get("gaps") or [])]

        versions = []
        for t in (result.get("coverage_trend") or []):
            if isinstance(t, dict):
                versions.append(VersionInfo(
                    version=t.get("version", "v0"),
                    coverage=float(t.get("coverage", 0)),
                    files=t.get("files", 0),
                    iteration=t.get("iteration", 0),
                ))

        artifacts = [
            {"name": Path(p).name, "path": p}
            for p in result.get("generated_files", {}).values()
        ]

        return PipelineResponse(
            design_name=result.get("design_name", "unknown"),
            status="passed" if result.get("passed") else "failed",
            versions=versions,
            coverage_trend=result.get("coverage_trend") or [],
            coverage_gaps=gaps,
            artifacts=artifacts,
            total_files=len(artifacts),
            iterations=result.get("auto_train_iterations", 0),
            simulator=result.get("simulator", "stub"),
        )
    except UVMGenError:
        raise
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        raise HTTPException(500, detail=str(e))


@app.post("/api/validate-spec")
async def validate_spec(req: PipelineRequest):
    try:
        import tempfile, os as _os, yaml
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(req.spec_yaml)
            spec_path = f.name

        loader = ConfigLoader()
        spec, _ = loader.load(spec_path)
        from src.data.validators import SpecValidator
        validator = SpecValidator()
        vr = validator.validate(spec, strict=True)
        try:
            _os.unlink(spec_path)
        except OSError:
            pass
        return {"valid": bool(vr), "design_name": spec.design_name,
                "errors": vr if vr else [], "registers": len(spec.registers),
                "interfaces": len(spec.interfaces)}
    except Exception as e:
        raise HTTPException(422, detail=str(e))


# ── Serve frontend (single deploy) ─────────────────────────────────

_IS_BUILT = FRONTEND_BUILD.exists()
if _IS_BUILT:
    logger.info("Serving frontend from %s", FRONTEND_BUILD)

EMBEDDED_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UVM Testbench Generator</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <style>
        .code-editor {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            tab-size: 2;
        }
        .fade-in {
            animation: fadeIn 0.3s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div id="app">
        <!-- Header -->
        <header class="bg-gray-800 border-b border-gray-700">
            <div class="max-w-7xl mx-auto px-4 py-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                            </svg>
                        </div>
                        <div>
                            <h1 class="text-xl font-bold text-white">UVM Testbench Generator</h1>
                            <p class="text-sm text-gray-400">AI-Powered Semiconductor Verification Pipeline</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 text-sm text-gray-400">
                        <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                        <span>API Online</span>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="max-w-7xl mx-auto px-4 py-8">
            <div class="grid lg:grid-cols-2 gap-8">
                <!-- Input Section -->
                <div class="space-y-6">
                    <!-- Spec Editor -->
                    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                        <div class="px-4 py-3 bg-gray-750 border-b border-gray-700 flex items-center justify-between">
                            <h2 class="font-semibold text-gray-200">Specification</h2>
                            <select id="example-select" class="bg-gray-700 text-gray-200 text-sm rounded px-3 py-1 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="uart">UART Example</option>
                                <option value="spi">SPI Example</option>
                                <option value="i2c">I2C Example</option>
                            </select>
                        </div>
                        <div class="p-4">
                            <textarea id="spec-editor" class="code-editor w-full h-96 bg-gray-900 text-green-400 p-4 rounded-lg border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" placeholder="Paste your YAML or .core specification here..."></textarea>
                        </div>
                    </div>

                    <!-- Options -->
                    <div class="bg-gray-800 rounded-xl border border-gray-700 p-6">
                        <h2 class="font-semibold text-gray-200 mb-4">Options</h2>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm text-gray-400 mb-1">Design Name</label>
                                <input type="text" id="design-name" value="my_design" class="w-full bg-gray-900 text-gray-200 px-3 py-2 rounded border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm text-gray-400 mb-1">Max Iterations</label>
                                <input type="number" id="max-iterations" value="1" min="1" max="50" class="w-full bg-gray-900 text-gray-200 px-3 py-2 rounded border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                            </div>
                        </div>
                        <div class="mt-4 flex items-center gap-2">
                            <input type="checkbox" id="auto-train" class="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500">
                            <label for="auto-train" class="text-sm text-gray-300">Enable Auto-Training (Coverage-Driven)</label>
                        </div>
                    </div>

                    <!-- Run Button -->
                    <button id="run-btn" class="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold py-4 px-6 rounded-xl transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-2">
                        <svg id="run-icon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <span id="btn-text">Generate UVM Testbench</span>
                    </button>
                </div>

                <!-- Output Section -->
                <div class="space-y-6">
                    <!-- Status -->
                    <div id="status-panel" class="hidden bg-gray-800 rounded-xl border border-gray-700 p-6 fade-in">
                        <div class="flex items-center gap-3 mb-4">
                            <div id="status-icon" class="w-8 h-8 rounded-full flex items-center justify-center">
                            </div>
                            <div>
                                <h3 id="status-title" class="font-semibold text-gray-200"></h3>
                                <p id="status-message" class="text-sm text-gray-400"></p>
                            </div>
                        </div>
                        <div id="progress-bar" class="hidden">
                            <div class="w-full bg-gray-700 rounded-full h-2">
                                <div class="bg-blue-600 h-2 rounded-full pulse" style="width: 100%"></div>
                            </div>
                        </div>
                    </div>

                    <!-- Results -->
                    <div id="results-panel" class="hidden space-y-6 fade-in">
                        <!-- Metrics -->
                        <div class="bg-gray-800 rounded-xl border border-gray-700 p-6">
                            <h3 class="font-semibold text-gray-200 mb-4">Generation Metrics</h3>
                            <div class="grid grid-cols-3 gap-4">
                                <div class="text-center p-3 bg-gray-900 rounded-lg">
                                    <p id="metric-files" class="text-2xl font-bold text-blue-400">-</p>
                                    <p class="text-xs text-gray-400">Files Generated</p>
                                </div>
                                <div class="text-center p-3 bg-gray-900 rounded-lg">
                                    <p id="metric-status" class="text-2xl font-bold text-green-400">-</p>
                                    <p class="text-xs text-gray-400">Status</p>
                                </div>
                                <div class="text-center p-3 bg-gray-900 rounded-lg">
                                    <p id="metric-iterations" class="text-2xl font-bold text-indigo-400">-</p>
                                    <p class="text-xs text-gray-400">Iterations</p>
                                </div>
                            </div>
                        </div>

                        <!-- Generated Files -->
                        <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                            <div class="px-4 py-3 bg-gray-750 border-b border-gray-700">
                                <h3 class="font-semibold text-gray-200">Generated Files</h3>
                            </div>
                            <div class="p-4 max-h-96 overflow-y-auto">
                                <div id="files-list" class="space-y-2">
                                </div>
                            </div>
                        </div>

                        <!-- Download Button -->
                        <button id="download-btn" class="hidden w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-semibold py-3 px-6 rounded-xl transition-all">
                            <span class="flex items-center justify-center gap-2">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                                </svg>
                                Download All Files as ZIP
                            </span>
                        </button>
                    </div>

                    <!-- Logs -->
                    <div id="logs-panel" class="hidden bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                        <div class="px-4 py-3 bg-gray-750 border-b border-gray-700 flex items-center justify-between">
                            <h3 class="font-semibold text-gray-200">Logs</h3>
                            <button id="clear-logs" class="text-xs text-gray-400 hover:text-gray-200">Clear</button>
                        </div>
                        <div class="p-4 max-h-64 overflow-y-auto">
                            <div id="logs" class="code-editor text-xs text-gray-300 space-y-1">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <!-- Footer -->
        <footer class="mt-auto py-6 border-t border-gray-800">
            <div class="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
                <p>UVM Testbench Generator | AI-Powered by <span class="text-blue-400 font-semibold">Sai Kumar Taraka</span></p>
            </div>
        </footer>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>
    <script>
        // Example specs
        const examples = {
            uart: `design_name: uart
clock_reset:
  clock: clk
  reset: rst_n

interfaces:
  - name: wb
    signals:
      - name: wb_cyc
        direction: input
      - name: wb_stb
        direction: input
      - name: wb_we
        direction: input
      - name: wb_addr
        direction: input
        width: 3
      - name: wb_data_o
        direction: output
        width: 8
      - name: wb_data_i
        direction: input
        width: 8
      - name: wb_ack
        direction: output

  - name: uart
    signals:
      - name: uart_tx
        direction: output
      - name: uart_rx
        direction: input

registers:
  - name: RBR_THR
    address: 0x0
    description: Receiver Buffer / Transmitter Holding
  - name: IER
    address: 0x1
    description: Interrupt Enable
  - name: IIR
    address: 0x2
    description: Interrupt Identification
  - name: LCR
    address: 0x3
    description: Line Control
  - name: MCR
    address: 0x4
    description: Modem Control
  - name: LSR
    address: 0x5
    description: Line Status
  - name: MSR
    address: 0x6
    description: Modem Status
  - name: SCR
    address: 0x7
    description: Scratch

protocol: uart`,
            spi: `design_name: spi_controller
clock_reset:
  clock: clk
  reset: rst_n

interfaces:
  - name: apb
    signals:
      - name: psel
        direction: input
      - name: penable
        direction: input
      - name: pwrite
        direction: input
      - name: paddr
        direction: input
        width: 8
      - name: pwdata
        direction: input
        width: 32
      - name: prdata
        direction: output
        width: 32
      - name: pready
        direction: output

  - name: spi
    signals:
      - name: sclk
        direction: output
      - name: mosi
        direction: output
      - name: miso
        direction: input
      - name: cs_n
        direction: output
        width: 4

registers:
  - name: CTRL
    address: 0x0
    description: Control Register
  - name: TXDATA
    address: 0x4
    description: TX Data
  - name: RXDATA
    address: 0x8
    description: RX Data
  - name: STATUS
    address: 0xC
    description: Status Register
  - name: DIVIDER
    address: 0x10
    description: Clock Divider
  - name: CS
    address: 0x14
    description: Chip Select

protocol: spi`,
            i2c: `design_name: i2c_master
clock_reset:
  clock: clk
  reset: rst_n

interfaces:
  - name: axi4lite
    signals:
      - name: awvalid
        direction: input
      - name: awready
        direction: output
      - name: awaddr
        direction: input
        width: 16
      - name: wvalid
        direction: input
      - name: wready
        direction: output
      - name: wdata
        direction: input
        width: 32
      - name: bvalid
        direction: output
      - name: bready
        direction: input
      - name: arvalid
        direction: input
      - name: arready
        direction: output
      - name: araddr
        direction: input
        width: 16
      - name: rvalid
        direction: output
      - name: rready
        direction: input
      - name: rdata
        direction: output
        width: 32

  - name: i2c
    signals:
      - name: scl
        direction: inout
      - name: sda
        direction: inout

registers:
  - name: PRESCALE
    address: 0x0
    description: Clock Prescale
  - name: CTRL
    address: 0x4
    description: Control
  - name: TX_RX
    address: 0x8
    description: TX/RX Data
  - name: CMD_STATUS
    address: 0xC
    description: Command / Status

protocol: i2c`
        };

        // State
        let generatedFiles = {};
        let isRunning = false;

        // DOM Elements
        const specEditor = document.getElementById('spec-editor');
        const exampleSelect = document.getElementById('example-select');
        const designNameInput = document.getElementById('design-name');
        const maxIterationsInput = document.getElementById('max-iterations');
        const autoTrainCheckbox = document.getElementById('auto-train');
        const runBtn = document.getElementById('run-btn');
        const btnText = document.getElementById('btn-text');
        const runIcon = document.getElementById('run-icon');
        const statusPanel = document.getElementById('status-panel');
        const statusIcon = document.getElementById('status-icon');
        const statusTitle = document.getElementById('status-title');
        const statusMessage = document.getElementById('status-message');
        const progressBar = document.getElementById('progress-bar');
        const resultsPanel = document.getElementById('results-panel');
        const logsPanel = document.getElementById('logs-panel');
        const logsDiv = document.getElementById('logs');
        const filesList = document.getElementById('files-list');
        const downloadBtn = document.getElementById('download-btn');
        const clearLogsBtn = document.getElementById('clear-logs');

        // Initialize
        specEditor.value = examples.uart;

        // Example selection
        exampleSelect.addEventListener('change', () => {
            specEditor.value = examples[exampleSelect.value];
        });

        // Log function
        function log(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const color = {
                info: 'text-gray-300',
                success: 'text-green-400',
                warning: 'text-yellow-400',
                error: 'text-red-400'
            }[type] || 'text-gray-300';
            
            const line = document.createElement('div');
            line.className = color;
            line.textContent = `[${timestamp}] ${message}`;
            logsDiv.appendChild(line);
            logsDiv.scrollTop = logsDiv.scrollHeight;
            
            logsPanel.classList.remove('hidden');
        }

        // Update status
        function updateStatus(title, message, status = 'running') {
            statusPanel.classList.remove('hidden');
            
            const iconColors = {
                running: 'bg-blue-500',
                success: 'bg-green-500',
                error: 'bg-red-500',
                warning: 'bg-yellow-500'
            };
            
            const icons = {
                running: `<svg class="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`,
                success: `<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`,
                error: `<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`,
                warning: `<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`
            };
            
            statusIcon.className = `w-8 h-8 rounded-full flex items-center justify-center ${iconColors[status] || iconColors.running}`;
            statusIcon.innerHTML = icons[status] || icons.running;
            statusTitle.textContent = title;
            statusMessage.textContent = message;
            
            progressBar.classList.toggle('hidden', status !== 'running');
        }

        // Set button state
        function setButtonState(running) {
            isRunning = running;
            runBtn.disabled = running;
            
            if (running) {
                btnText.textContent = 'Generating...';
                runBtn.classList.add('opacity-75', 'cursor-not-allowed');
                runBtn.classList.remove('hover:from-blue-700', 'hover:to-indigo-700');
            } else {
                btnText.textContent = 'Generate UVM Testbench';
                runBtn.classList.remove('opacity-75', 'cursor-not-allowed');
                runBtn.classList.add('hover:from-blue-700', 'hover:to-indigo-700');
            }
        }

        // Run pipeline
        async function runPipeline() {
            if (isRunning) return;
            
            setButtonState(true);
            resultsPanel.classList.add('hidden');
            generatedFiles = {};
            
            const specYaml = specEditor.value;
            const designName = designNameInput.value;
            const maxIterations = parseInt(maxIterationsInput.value);
            const autoTrain = autoTrainCheckbox.checked;
            
            log('Starting UVM testbench generation...', 'info');
            log(`Design: ${designName}, Iterations: ${maxIterations}, Auto-Train: ${autoTrain}`, 'info');
            
            updateStatus('Running Pipeline', 'Generating UVM testbench...', 'running');
            
            try {
                const response = await fetch('/api/run-pipeline', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        spec_yaml: specYaml,
                        design_name: designName,
                        auto_train: autoTrain,
                        max_iterations: maxIterations,
                        coverage_target: 90.0,
                        num_seeds: 3,
                        overwrite: true
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.message || error.detail || 'Request failed');
                }
                
                const result = await response.json();
                
                log(`Generation complete! Status: ${result.status}`, 'success');
                log(`Files generated: ${result.total_files}`, 'success');
                
                // Fetch file contents
                generatedFiles = {};
                if (result.artifacts && result.artifacts.length > 0) {
                    // For now, we'll use the artifact info. In a real deployment, 
                    // we'd need endpoints to download individual files.
                    log('Note: File download requires artifact endpoints', 'warning');
                }
                
                updateStatus('Complete', 'UVM testbench generated successfully', 'success');
                
                // Show results
                document.getElementById('metric-files').textContent = result.total_files;
                document.getElementById('metric-status').textContent = result.status.toUpperCase();
                document.getElementById('metric-iterations').textContent = result.iterations;
                
                // Show files list
                filesList.innerHTML = '';
                if (result.artifacts) {
                    result.artifacts.forEach((artifact, index) => {
                        const div = document.createElement('div');
                        div.className = 'flex items-center justify-between p-3 bg-gray-900 rounded-lg';
                        div.innerHTML = `
                            <div class="flex items-center gap-2">
                                <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                </svg>
                                <span class="text-sm text-gray-300">${artifact.name}</span>
                            </div>
                        `;
                        filesList.appendChild(div);
                    });
                }
                
                resultsPanel.classList.remove('hidden');
                
            } catch (error) {
                log(`Error: ${error.message}`, 'error');
                updateStatus('Error', error.message, 'error');
            }
            
            setButtonState(false);
        }

        // Event listeners
        runBtn.addEventListener('click', runPipeline);
        
        clearLogsBtn.addEventListener('click', () => {
            logsDiv.innerHTML = '';
        });

        // Health check on load
        fetch('/api/health')
            .then(r => r.json())
            .then(data => {
                log(`API ready: ${data.status} (v${data.version})`, 'success');
            })
            .catch(e => {
                log('API health check failed', 'warning');
            });
    </script>
</body>
</html>
"""

from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def serve_index():
    if _IS_BUILT:
        index = FRONTEND_BUILD / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return HTMLResponse(EMBEDDED_UI)


@app.get("/static/{rest_of_path:path}", include_in_schema=False)
async def serve_static(rest_of_path: str):
    if not _IS_BUILT:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    file_path = FRONTEND_BUILD / "static" / rest_of_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return JSONResponse(status_code=404, content={"error": "Not found"})


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi"):
        return JSONResponse(status_code=404, content={"error": "Not found"})
    if _IS_BUILT:
        file_path = FRONTEND_BUILD / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        index = FRONTEND_BUILD / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return HTMLResponse(EMBEDDED_UI)


# ── Direct execution ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
