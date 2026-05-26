"""
UVM Generator Backend - FastAPI Application

REST + WebSocket API for real-time pipeline updates
"""

import sys
import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, List
import asyncio
import json
import zipfile
import io
from datetime import datetime
import tempfile

# Add repo root to path for imports
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, "backend"))

from schemas import (
    PipelineStatus,
    PipelineStep,
    GenerationConfig,
    GenerationResponse,
    PipelineUpdate,
    MetricsResponse
)
from core.pipeline_manager import pipeline_manager

app = FastAPI(
    title="UVM Generator API",
    description="AI-Powered UVM Testbench Generator",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}


@app.get("/")
async def root():
    return {
        "name": "UVM Generator API",
        "version": "2.1.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/generate", response_model=GenerationResponse)
async def start_generation(config: GenerationConfig):
    """Start a new generation pipeline"""
    task_id = pipeline_manager.create_pipeline(config)
    
    # Run generation in background
    asyncio.create_task(pipeline_manager.run_generation(task_id))
    
    # Broadcast via WebSocket
    await broadcast_task_update(task_id)
    
    return pipeline_manager.get_response(task_id)


@app.get("/api/generate/{task_id}", response_model=GenerationResponse)
async def get_generation_status(task_id: str):
    """Get the status of a generation pipeline"""
    response = pipeline_manager.get_response(task_id)
    if not response:
        raise HTTPException(status_code=404, detail=f"Pipeline {task_id} not found")
    return response


@app.get("/api/generate/{task_id}/logs")
async def get_generation_logs(task_id: str):
    """Get logs for a pipeline"""
    pipeline = pipeline_manager.get_pipeline(task_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline {task_id} not found")
    return {
        "task_id": task_id,
        "logs": pipeline.logs
    }


@app.get("/api/generate/{task_id}/metrics", response_model=MetricsResponse)
async def get_generation_metrics(task_id: str):
    """Get metrics for a completed pipeline"""
    pipeline = pipeline_manager.get_pipeline(task_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline {task_id} not found")
    
    if not pipeline.metrics:
        raise HTTPException(status_code=400, detail=f"Metrics not available for pipeline {task_id}")
    
    return MetricsResponse(
        completeness=pipeline.metrics.get("completeness", 0),
        signal_coverage=pipeline.metrics.get("signal_coverage", 0),
        register_coverage=pipeline.metrics.get("register_coverage", 0),
        files_generated=pipeline.metrics.get("files_generated", 0),
        passed=pipeline.metrics.get("passed", False)
    )


@app.get("/api/generate/{task_id}/files")
async def get_generated_files(task_id: str):
    """Get list of generated files"""
    pipeline = pipeline_manager.get_pipeline(task_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline {task_id} not found")
    
    return {
        "task_id": task_id,
        "files": list(pipeline.generated_files.keys()) if pipeline.generated_files else []
    }


@app.get("/api/generate/{task_id}/files/{file_name:path}")
async def get_file_content(task_id: str, file_name: str):
    """Get content of a generated file"""
    pipeline = pipeline_manager.get_pipeline(task_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline {task_id} not found")
    
    if not pipeline.generated_files or file_name not in pipeline.generated_files:
        raise HTTPException(status_code=404, detail=f"File {file_name} not found")
    
    file_path = pipeline.generated_files[file_name]
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {file_name} not found on disk")
    
    return FileResponse(
        path=file_path,
        media_type="text/plain",
        filename=file_name
    )


@app.get("/api/generate/{task_id}/download")
async def download_all_files(task_id: str):
    """Download all generated files as ZIP"""
    pipeline = pipeline_manager.get_pipeline(task_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline {task_id} not found")
    
    if not pipeline.generated_files:
        raise HTTPException(status_code=404, detail=f"No files available for pipeline {task_id}")
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for name, path in pipeline.generated_files.items():
            if os.path.exists(path):
                zipf.write(path, arcname=name)
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={pipeline.config.design_name}_uvm_testbench.zip"
        }
    )


@app.get("/api/pipelines")
async def list_pipelines():
    """List all pipelines"""
    pipelines = pipeline_manager.get_all_pipelines()
    return {
        "count": len(pipelines),
        "pipelines": [
            {
                "task_id": p.task_id,
                "design_name": p.config.design_name,
                "protocol": p.config.protocol,
                "status": p.status.value,
                "progress": p.progress,
                "current_step": p.current_step.value if p.current_step else None,
                "created_at": p.created_at.isoformat()
            }
            for p in pipelines
        ]
    }


# WebSocket for real-time updates
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    if task_id not in active_connections:
        active_connections[task_id] = []
    active_connections[task_id].append(websocket)
    
    try:
        # Send initial status
        pipeline = pipeline_manager.get_pipeline(task_id)
        if pipeline:
            await send_pipeline_update(websocket, pipeline)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except:
                pass
                
    except WebSocketDisconnect:
        if task_id in active_connections:
            if websocket in active_connections[task_id]:
                active_connections[task_id].remove(websocket)


async def broadcast_task_update(task_id: str):
    """Broadcast pipeline update to all connected WebSockets"""
    pipeline = pipeline_manager.get_pipeline(task_id)
    if not pipeline or task_id not in active_connections:
        return
    
    for websocket in active_connections[task_id]:
        try:
            await send_pipeline_update(websocket, pipeline)
        except:
            pass


async def send_pipeline_update(websocket: WebSocket, pipeline):
    """Send pipeline update to a single WebSocket"""
    response = pipeline_manager.get_response(pipeline.task_id)
    
    update = {
        "type": "pipeline_update",
        "task_id": pipeline.task_id,
        "status": pipeline.status.value,
        "current_step": pipeline.current_step.value if pipeline.current_step else None,
        "progress": pipeline.progress,
        "message": pipeline.message,
        "logs": pipeline.logs[-50:],  # Last 50 logs
        "completed_steps": [s.value for s in pipeline.completed_steps],
        "metrics": pipeline.metrics if pipeline.metrics else None
    }
    
    await websocket.send_json(update)


# Fix imports properly
from fastapi.responses import Response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
