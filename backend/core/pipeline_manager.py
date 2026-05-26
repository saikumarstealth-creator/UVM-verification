"""
Pipeline Manager - Manages generation pipelines with real-time updates
"""

import uuid
import asyncio
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
    
    def complete_step(self, step: PipelineStep):
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.add_log(f"✓ {step.value} completed")


class PipelineManager:
    def __init__(self):
        self.pipelines: Dict[str, PipelineState] = {}
        self._websocket_connections: Dict[str, List[Any]] = {}
    
    def create_pipeline(self, config: GenerationConfig) -> str:
        task_id = str(uuid.uuid4())[:8]
        pipeline = PipelineState(task_id, config)
        self.pipelines[task_id] = pipeline
        pipeline.add_log(f"Pipeline created: {config.design_name}")
        logger.info(f"Created pipeline {task_id} for {config.design_name}")
        return task_id
    
    def get_pipeline(self, task_id: str) -> Optional[PipelineState]:
        return self.pipelines.get(task_id)
    
    def get_all_pipelines(self) -> List[PipelineState]:
        return list(self.pipelines.values())
    
    async def run_generation(self, task_id: str) -> GenerationResponse:
        pipeline = self.get_pipeline(task_id)
        if not pipeline:
            raise ValueError(f"Pipeline {task_id} not found")
        
        pipeline.status = PipelineStatus.RUNNING
        
        try:
            # Import generation logic from existing code
            import sys
            import os
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, repo_root)
            
            from src.config import PipelineConfig, MLConfig, GenerationConfig, AutoTrainConfig
            from src.pipeline import TBPipeline
            import tempfile
            import yaml
            
            # Step 1: Spec Parse
            pipeline.update_step(PipelineStep.SPEC_PARSE, 10, "Parsing specification...")
            await asyncio.sleep(0.1)
            
            # Write spec to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
                f.write(pipeline.config.spec_yaml)
                spec_path = f.name
            
            pipeline.update_step(PipelineStep.SPEC_PARSE, 20, "Specification parsed successfully")
            pipeline.complete_step(PipelineStep.SPEC_PARSE)
            await asyncio.sleep(0.1)
            
            # Step 2: Feature Extract
            pipeline.update_step(PipelineStep.FEATURE_EXTRACT, 25, "Extracting features...")
            
            # Parse spec for feature extraction
            spec_dict = yaml.safe_load(pipeline.config.spec_yaml)
            num_interfaces = len(spec_dict.get('interfaces', []))
            num_registers = len(spec_dict.get('registers', []))
            
            pipeline.update_step(PipelineStep.FEATURE_EXTRACT, 35, 
                f"Found {num_interfaces} interfaces, {num_registers} registers")
            pipeline.complete_step(PipelineStep.FEATURE_EXTRACT)
            await asyncio.sleep(0.1)
            
            # Step 3: ML Generation
            pipeline.update_step(PipelineStep.ML_GENERATION, 40, "Starting ML generation...")
            
            # Configure pipeline
            ml_cfg = MLConfig(
                enabled=(pipeline.config.model_type != "template"),
                model_type=pipeline.config.model_type,
                use_llm=False,
                use_semantic_encoder=False,
            )
            
            if pipeline.config.model_type == "v2":
                ml_cfg.exploration_strategy = pipeline.config.rl_strategy
                ml_cfg.use_learning = pipeline.config.enable_learning
                ml_cfg.strict_validation = pipeline.config.strict_uvm
            
            pipeline_cfg = PipelineConfig(
                ml=ml_cfg,
                generation=GenerationConfig(
                    templates_dir=os.path.join(repo_root, "src", "generation", "templates"),
                    output_dir=os.path.join(repo_root, "output", task_id),
                    overwrite=True
                ),
                auto_train=AutoTrainConfig(
                    enabled=(pipeline.config.max_iterations > 1),
                    max_iterations=pipeline.config.max_iterations
                )
            )
            
            pipeline.update_step(PipelineStep.ML_GENERATION, 50, 
                f"Engine: {pipeline.config.model_type.upper()}, RL: {pipeline.config.rl_strategy}")
            await asyncio.sleep(0.1)
            
            # Create and run pipeline
            tb_pipeline = TBPipeline(pipeline_cfg)
            pipeline.update_step(PipelineStep.ML_GENERATION, 60, "Generating testbench...")
            
            result = tb_pipeline.run(spec_path)
            
            # Cleanup temp file
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
            pipeline.metrics = {
                "completeness": eval_metrics.get('completeness', 0),
                "signal_coverage": eval_metrics.get('interface_signal_coverage', 0),
                "register_coverage": eval_metrics.get('register_coverage', 0),
                "files_generated": len(pipeline.generated_files),
                "passed": passed
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
            
            # Final status
            pipeline.status = PipelineStatus.COMPLETED if passed else PipelineStatus.PENDING
            pipeline.progress = 100
            pipeline.message = f"Generation {'passed' if passed else 'completed'} with {len(pipeline.generated_files)} files"
            pipeline.add_log(f"Pipeline complete - Status: {validation_status}")
            
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
