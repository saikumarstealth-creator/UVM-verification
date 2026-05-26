"""
Backend Schemas - Pydantic models for API
"""

from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from enum import Enum


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStep(str, Enum):
    SPEC_PARSE = "spec_parse"
    FEATURE_EXTRACT = "feature_extract"
    ML_GENERATION = "ml_generation"
    UVM_VALIDATION = "uvm_validation"
    COVERAGE_ANALYSIS = "coverage_analysis"
    EXPORT = "export"


class GenerationConfig(BaseModel):
    design_name: str
    protocol: str
    model_type: str = "v2"
    rl_strategy: str = "ucb"
    enable_learning: bool = True
    strict_uvm: bool = True
    max_iterations: int = 1
    spec_yaml: str


class GenerationResponse(BaseModel):
    task_id: str
    status: PipelineStatus
    current_step: Optional[PipelineStep] = None
    progress: int = 0
    message: str = ""
    generated_files: Optional[Dict[str, str]] = None
    metrics: Optional[Dict[str, Any]] = None


class PipelineUpdate(BaseModel):
    task_id: str
    step: PipelineStep
    status: PipelineStatus
    progress: int
    message: str
    log_lines: List[str] = []


class FileContent(BaseModel):
    path: str
    content: str


class MetricsResponse(BaseModel):
    completeness: float
    signal_coverage: float
    register_coverage: float
    files_generated: int
    passed: bool


class ProjectConfig(BaseModel):
    name: str
    protocol: str
    created_at: str
    last_modified: str
