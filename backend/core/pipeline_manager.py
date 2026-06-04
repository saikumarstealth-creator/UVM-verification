"""
Pipeline Manager - Manages generation pipelines with real-time updates
"""

import uuid
import asyncio
import json
import os
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from schemas import (
    PipelineStatus,
    PipelineStep,
    GenerationConfig,
    GenerationResponse,
    PipelineUpdate
)

logger = logging.getLogger("pipeline_manager")

# Directory for cross-worker pipeline state persistence
PIPELINE_STATE_DIR = os.environ.get(
    "UVMGEN_PIPELINE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output", ".pipelines")
)
_state_lock = threading.Lock()


def _serialize_pipeline(p: "PipelineState") -> dict:
    return {
        "task_id": p.task_id,
        "config": {
            "design_name": p.config.design_name,
            "protocol": p.config.protocol,
            "model_type": p.config.model_type,
            "rl_strategy": p.config.rl_strategy,
            "enable_learning": p.config.enable_learning,
            "strict_uvm": p.config.strict_uvm,
            "max_iterations": p.config.max_iterations,
        },
        "status": p.status.value,
        "current_step": p.current_step.value if p.current_step else None,
        "progress": p.progress,
        "message": p.message,
        "logs": p.logs[-200:],
        "generated_files": p.generated_files,
        "metrics": p.metrics,
        "created_at": p.created_at.isoformat(),
        "completed_steps": [s.value for s in p.completed_steps],
    }


def _deserialize_pipeline(d: dict) -> "PipelineState":
    from schemas import GenerationConfig as GConfig
    cfg = GConfig(
        design_name=d["config"]["design_name"],
        protocol=d["config"]["protocol"],
        model_type=d["config"]["model_type"],
        rl_strategy=d["config"]["rl_strategy"],
        enable_learning=d["config"]["enable_learning"],
        strict_uvm=d["config"]["strict_uvm"],
        max_iterations=d["config"]["max_iterations"],
    )
    p = PipelineState(d["task_id"], cfg)
    p.status = PipelineStatus(d["status"])
    p.current_step = PipelineStep(d["current_step"]) if d.get("current_step") else None
    p.progress = d.get("progress", 0)
    p.message = d.get("message", "")
    p.logs = d.get("logs", [])
    p.generated_files = d.get("generated_files", {})
    p.metrics = d.get("metrics", {})
    p.completed_steps = [PipelineStep(s) for s in d.get("completed_steps", [])]
    if d.get("created_at"):
        try:
            p.created_at = datetime.fromisoformat(d["created_at"])
        except Exception:
            pass
    return p


def _state_path(task_id: str) -> str:
    return os.path.join(PIPELINE_STATE_DIR, f"{task_id}.json")


def _save_state(pipeline: "PipelineState") -> None:
    os.makedirs(PIPELINE_STATE_DIR, exist_ok=True)
    path = _state_path(pipeline.task_id)
    with _state_lock:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_serialize_pipeline(pipeline), f, indent=2)
        except Exception as e:
            logger.warning("Failed to save pipeline state %s: %s", pipeline.task_id, e)


def _load_state(task_id: str) -> Optional["PipelineState"]:
    path = _state_path(task_id)
    if not os.path.exists(path):
        return None
    with _state_lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return _deserialize_pipeline(json.load(f))
        except Exception as e:
            logger.warning("Failed to load pipeline state %s: %s", task_id, e)
    return None


class PipelineState:
    def __init__(self, task_id: str, config: GenerationConfig):
        self.task_id = task_id
        self.config = config
        self.status = PipelineStatus.PENDING
        self.current_step: Optional[PipelineStep] = None
        self.progress = 0
        self.message = "Pending"
        self.logs: List[str] = []
        self.generated_files: Dict[str, str] = {}
        self.metrics: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.completed_steps: List[PipelineStep] = []
        
        self._observers: List[Any] = []
    
    def add_log(self, line: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.logs.append(f"[{timestamp}] {line}")
    
    def update_step(self, step: PipelineStep, progress: int, message: str):
        self.current_step = step
        self.progress = progress
        self.message = message
        self.add_log(f"{step.value}: {message}")
        logger.info(f"Pipeline {self.task_id}: {step.value} - {message} ({progress}%)")
        _save_state(self)
    
    def complete_step(self, step: PipelineStep):
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.add_log(f"✓ {step.value} completed")
        _save_state(self)


class PipelineManager:
    def __init__(self):
        self.pipelines: Dict[str, PipelineState] = {}
        self._websocket_connections: Dict[str, List[Any]] = {}
    
    def create_pipeline(self, config: GenerationConfig) -> str:
        task_id = str(uuid.uuid4())[:8]
        pipeline = PipelineState(task_id, config)
        self.pipelines[task_id] = pipeline
        pipeline.add_log(f"Pipeline created: {config.design_name}")
        _save_state(pipeline)
        logger.info(f"Created pipeline {task_id} for {config.design_name}")
        return task_id
    
    def get_pipeline(self, task_id: str) -> Optional[PipelineState]:
        # Check local cache first
        p = self.pipelines.get(task_id)
        if p is not None:
            return p
        # Fall back to file-based state (cross-worker)
        p = _load_state(task_id)
        if p is not None:
            self.pipelines[task_id] = p
        return p
    
    def get_all_pipelines(self) -> List[PipelineState]:
        # Merge local cache with files
        os.makedirs(PIPELINE_STATE_DIR, exist_ok=True)
        try:
            for fn in os.listdir(PIPELINE_STATE_DIR):
                if fn.endswith(".json"):
                    tid = fn[:-5]
                    if tid not in self.pipelines:
                        p = _load_state(tid)
                        if p is not None:
                            self.pipelines[tid] = p
        except Exception:
            pass
        return list(self.pipelines.values())
    
    async def run_generation(self, task_id: str) -> GenerationResponse:
        pipeline = self.get_pipeline(task_id)
        if not pipeline:
            raise ValueError(f"Pipeline {task_id} not found")
        
        pipeline.status = PipelineStatus.RUNNING
        
        try:
            cfg = pipeline.config

            # ── Local path ──────────────────────────────────────────────────
            import sys
            import os
            
            # Calculate repo root from backend/core/pipeline_manager.py
            # Need to go up 3 levels: backend/core/pipeline_manager.py -> backend/core -> backend -> repo_root
            file_path = os.path.abspath(__file__)
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
            
            sys.path.insert(0, repo_root)
            
            from src.config import PipelineConfig, MLConfig, GenerationConfig, AutoTrainConfig
            from src.pipeline import TBPipeline
            import tempfile
            import yaml
            
            # Step 1: Spec Parse
            pipeline.update_step(PipelineStep.SPEC_PARSE, 10, "Parsing specification...")
            await asyncio.sleep(0.1)
            
            # Determine input type: RTL or YAML spec
            if cfg.rtl_content:
                suffix = '.v'
                content = cfg.rtl_content
                input_type = "Verilog RTL"
            else:
                suffix = '.yaml'
                content = cfg.spec_yaml
                input_type = "YAML specification"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
                f.write(content)
                spec_path = f.name
            
            pipeline.update_step(PipelineStep.SPEC_PARSE, 20, f"{input_type} parsed successfully")
            pipeline.complete_step(PipelineStep.SPEC_PARSE)
            await asyncio.sleep(0.1)
            
            # Step 2: Feature Extract
            pipeline.update_step(PipelineStep.FEATURE_EXTRACT, 25, "Extracting features...")
            
            num_interfaces = 0
            num_registers = 0
            if not cfg.rtl_content:
                spec_dict = yaml.safe_load(cfg.spec_yaml)
                num_interfaces = len(spec_dict.get('interfaces', []))
                num_registers = len(spec_dict.get('registers', []))
            
            pipeline.update_step(PipelineStep.FEATURE_EXTRACT, 35, 
                f"Found {num_interfaces} interfaces, {num_registers} registers")
            pipeline.complete_step(PipelineStep.FEATURE_EXTRACT)
            await asyncio.sleep(0.1)
            
            # Step 3: ML Generation
            pipeline.update_step(PipelineStep.ML_GENERATION, 40, "Starting ML generation...")
            
            ml_cfg = MLConfig(
                enabled=(cfg.model_type != "template"),
                model_type=cfg.model_type,
                use_llm=False,
                use_semantic_encoder=False,
            )
            
            if cfg.model_type == "v2":
                ml_cfg.exploration_strategy = cfg.rl_strategy
                ml_cfg.use_learning = cfg.enable_learning
                ml_cfg.strict_validation = cfg.strict_uvm
            
            pipeline_cfg = PipelineConfig(
                ml=ml_cfg,
                generation=GenerationConfig(
                    templates_dir=os.path.join(repo_root, "src", "generation", "templates"),
                    output_dir=os.path.join(repo_root, "output", task_id),
                    overwrite=True
                ),
                auto_train=AutoTrainConfig(
                    enabled=(cfg.max_iterations > 1),
                    max_iterations=cfg.max_iterations
                )
            )
            
            pipeline.update_step(PipelineStep.ML_GENERATION, 50, 
                f"Engine: {cfg.model_type.upper()}, RL: {cfg.rl_strategy}")
            await asyncio.sleep(0.1)
            
            tb_pipeline = TBPipeline(pipeline_cfg)
            pipeline.update_step(PipelineStep.ML_GENERATION, 60, "Generating testbench...")
            
            # Run pipeline in a thread executor to avoid blocking the event loop
            # (keeps WebSocket broadcasts flowing during generation)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, tb_pipeline.run, spec_path)
            
            try:
                os.unlink(spec_path)
            except:
                pass
            
            pipeline.update_step(PipelineStep.ML_GENERATION, 75, 
                f"Generated {len(result.get('generated_files', {}))} files")
            pipeline.complete_step(PipelineStep.ML_GENERATION)
            await asyncio.sleep(0.1)
            
            # Step 4: UVM Validation
            pipeline.update_step(PipelineStep.UVM_VALIDATION, 80, "Validating UVM structure...")
            
            eval_metrics = result.get('evaluation', {})
            passed = result.get('passed', False)
            
            pipeline.generated_files = result.get('generated_files', {})
            sv_check = result.get('sv_check', {})
            quality = result.get('quality_score', 0.0)
            cross_val = result.get('cross_file_validation', {}) or {}
            pipeline.metrics = {
                "completeness": eval_metrics.get('completeness', 0),
                "signal_coverage": eval_metrics.get('interface_signal_coverage', 0),
                "register_coverage": eval_metrics.get('register_coverage', 0),
                "files_generated": len(pipeline.generated_files),
                "passed": passed,
                "sv_compile_confidence": sv_check.get('sv_compile_confidence', 0.0),
                "sv_errors": sv_check.get('sv_errors', 0),
                "sv_warnings": sv_check.get('sv_warnings', 0),
                "quality_overall": quality,
                "quality_syntax": eval_metrics.get('quality_syntax', 0.0),
                "quality_ral": eval_metrics.get('quality_ral', 0.0),
                "spec_coverage_score": eval_metrics.get('spec_coverage_score', 0.0),
                "hallucination_count": eval_metrics.get('hallucination_count', 0),
            }
            
            validation_status = "PASSED" if passed else "COMPLETED"
            pipeline.update_step(PipelineStep.UVM_VALIDATION, 85, 
                f"Validation {validation_status}")
            pipeline.complete_step(PipelineStep.UVM_VALIDATION)
            await asyncio.sleep(0.1)
            
            # Step 5: Coverage Analysis
            pipeline.update_step(PipelineStep.COVERAGE_ANALYSIS, 90, "Analyzing coverage...")
            await asyncio.sleep(0.1)
            
            completeness = eval_metrics.get('completeness', 0) * 100
            signal_cov = eval_metrics.get('interface_signal_coverage', 0) * 100
            reg_cov = eval_metrics.get('register_coverage', 0) * 100
            
            pipeline.update_step(PipelineStep.COVERAGE_ANALYSIS, 93,
                f"Completeness: {completeness:.1f}%, Signal Cov: {signal_cov:.1f}%, Reg Cov: {reg_cov:.1f}%")
            pipeline.complete_step(PipelineStep.COVERAGE_ANALYSIS)
            await asyncio.sleep(0.1)
            
            # Step 6: Export
            pipeline.update_step(PipelineStep.EXPORT, 95, "Preparing export package...")
            await asyncio.sleep(0.1)
            
            pipeline.update_step(PipelineStep.EXPORT, 100, "Generation complete!")
            pipeline.complete_step(PipelineStep.EXPORT)
            
            pipeline.status = PipelineStatus.COMPLETED if passed else PipelineStatus.PENDING
            pipeline.progress = 100
            pipeline.message = f"Generation {'passed' if passed else 'completed'} with {len(pipeline.generated_files)} files"
            pipeline.add_log(f"Pipeline complete - Status: {validation_status}")
            _save_state(pipeline)
            
            return GenerationResponse(
                task_id=task_id,
                status=pipeline.status,
                current_step=PipelineStep.EXPORT,
                progress=100,
                message=pipeline.message,
                generated_files=pipeline.generated_files,
                metrics=pipeline.metrics
            )
            
        except Exception as e:
            pipeline.status = PipelineStatus.FAILED
            pipeline.message = f"Error: {str(e)}"
            pipeline.add_log(f"ERROR: {str(e)}")
            import traceback
            pipeline.add_log(traceback.format_exc())
            logger.error(f"Pipeline {task_id} failed: {e}")
            _save_state(pipeline)
            
            return GenerationResponse(
                task_id=task_id,
                status=PipelineStatus.FAILED,
                current_step=pipeline.current_step,
                progress=pipeline.progress,
                message=pipeline.message
            )

    def get_response(self, task_id: str) -> Optional[GenerationResponse]:
        pipeline = self.get_pipeline(task_id)
        if not pipeline:
            return None
        
        return GenerationResponse(
            task_id=task_id,
            status=pipeline.status,
            current_step=pipeline.current_step,
            progress=pipeline.progress,
            message=pipeline.message,
            generated_files=pipeline.generated_files if pipeline.generated_files else None,
            metrics=pipeline.metrics if pipeline.metrics else None
        )


# Global pipeline manager instance
pipeline_manager = PipelineManager()
