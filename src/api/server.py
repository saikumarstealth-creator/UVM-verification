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

from fastapi.responses import HTMLResponse


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def serve_index():
    if _IS_BUILT:
        index = FRONTEND_BUILD / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return HTMLResponse("<h1>UVM TB Generator API</h1><p>Frontend not built. Run <code>cd frontend && npm run build</code></p>")


@app.get("/static/{rest_of_path:path}", include_in_schema=False)
async def serve_static(rest_of_path: str):
    if not _IS_BUILT:
        return JSONResponse(404, {"error": "Not found"})
    file_path = FRONTEND_BUILD / "static" / rest_of_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return JSONResponse(404, {"error": "Not found"})


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
    return JSONResponse(404, {"error": "Not found"})


# ── Direct execution ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
