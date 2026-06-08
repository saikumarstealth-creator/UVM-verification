# src/config.py — Central configuration with Pydantic validation

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, model_validator
import yaml


# ── Data Models ──────────────────────────────────────────────────────────────

class SignalDef(BaseModel):
    name: str
    direction: str = Field(default="inout", pattern=r"^(input|output|inout)$")
    width: int = Field(default=1, ge=1)
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def coerce_width(cls, data):
        if isinstance(data, dict) and "width" in data and isinstance(data["width"], str):
            try:
                data["width"] = int(data["width"])
            except ValueError:
                pass
        return data

class InterfaceDef(BaseModel):
    name: str = "bus"
    signals: List[SignalDef] = Field(min_length=1)
    description: Optional[str] = None

class FieldDef(BaseModel):
    name: str
    bits: str
    description: Optional[str] = None
    access: Optional[str] = None
    reset: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data):
        if isinstance(data, dict):
            if "width" in data:
                w = data.pop("width")
                data.setdefault("bits", str(w) if isinstance(w, int) else w)
            if "reset" in data and isinstance(data["reset"], (int, float)):
                val = int(data["reset"])
                data["reset"] = str(val) if val == 0 else f"'h{val:X}" if val > 9 else str(val)
        return data

class RegisterDef(BaseModel):
    name: str
    address: str
    fields: List[FieldDef] = []
    description: Optional[str] = None
    access: Optional[str] = None
    size: Optional[int] = None
    reset_value: Optional[str] = None
    volatile: bool = False

    @model_validator(mode="before")
    @classmethod
    def coerce_types(cls, data):
        if isinstance(data, dict):
            if "reset_value" in data and isinstance(data["reset_value"], (int, float)):
                val = int(data["reset_value"])
                data["reset_value"] = str(val) if val == 0 else f"'h{val:X}" if val > 9 else str(val)
        return data

class ClockResetDef(BaseModel):
    clock: str = "clk"
    reset: str = "rst_n"
    reset_active: int = Field(default=0, ge=0, le=1)

class SequenceDef(BaseModel):
    name: str
    type: str = "regression"
    description: str = ""


class CoverageDef(BaseModel):
    """Coverage specification from YAML (e.g. baud_rate bins, frame formats)."""
    coverpoints: Dict[str, List[Any]] = {}
    crosses: List[str] = []


class DesignSpec(BaseModel):
    design_name: str = Field(min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    clock_reset: ClockResetDef = ClockResetDef()
    interfaces: List[InterfaceDef] = Field(min_length=1)
    registers: List[RegisterDef] = []
    protocol: str = Field(default="", pattern=r"^(uart|spi|i2c|axi4lite|apb|wishbone|)$")
    sequences: List[SequenceDef] = []
    coverage: Optional[CoverageDef] = None

# Pydantic v2 needs explicit rebuild when using `from __future__ import annotations`
DesignSpec.model_rebuild()
RegisterDef.model_rebuild()


# ── Pipeline / Engine Config ─────────────────────────────────────────────────

class LoggingConfig(BaseModel):
    level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")
    file: Optional[str] = None
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

class EvaluationConfig(BaseModel):
    enabled: bool = True
    metrics: List[str] = ["completeness", "syntax_validity", "coverage_readiness"]
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)

class TrackingConfig(BaseModel):
    enabled: bool = False
    backend: str = Field(default="local", pattern=r"^(local|mlflow)$")
    experiment_name: Optional[str] = None
    tracking_uri: Optional[str] = None

class GenerationConfig(BaseModel):
    templates_dir: str = "src/generation/templates"
    output_dir: str = "output"
    overwrite: bool = False
    strict_validation: bool = True
    iteration: int = Field(default=0, ge=0)

class AutoTrainConfig(BaseModel):
    enabled: bool = False
    max_iterations: int = Field(default=5, ge=1, le=50)
    coverage_target: float = Field(default=90.0, ge=0.0, le=100.0)
    coverage_gain_min: float = Field(default=2.0, ge=0.0, description="Min % gain per iteration to continue")
    simulator: str = Field(default="stub", pattern=r"^(stub|icarus|vcs|questa|xcelium|xrun)$")
    sim_timeout: int = Field(default=300, ge=10)
    num_seeds: int = Field(default=3, ge=1, le=20, description="Number of regression seeds per iteration")
    generate_regression_test: bool = True


class MLConfig(BaseModel):
    """Configuration for AI/ML-augmented generation with actual learning capabilities."""
    enabled: bool = False
    model_type: str = Field(default="template", pattern=r"^(template|ml|hybrid|llm|semantic|v2)$")
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    auto_learn: bool = True
    index_path: Optional[str] = None
    top_k_retrieval: int = Field(default=3, ge=1, le=10)
    fallback_to_templates: bool = True

    use_llm: bool = True
    llm_model_name: Optional[str] = None
    llm_max_tokens: int = Field(default=1024, ge=64, le=4096)
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    llm_use_few_shot: bool = True

    use_semantic_encoder: bool = True
    semantic_model_name: str = "microsoft/codebert-base"

    use_learning: bool = True
    learning_storage_path: Optional[str] = None
    learning_rate: float = Field(default=0.1, ge=0.001, le=1.0)
    reinforcement_discount: float = Field(default=0.9, ge=0.0, le=1.0)
    exploration_epsilon: float = Field(default=0.05, ge=0.0, le=0.5)
    exploration_strategy: str = Field(default="ucb", pattern=r"^(epsilon_greedy|softmax|ucb|thompson)$")
    strict_validation: bool = False


class PipelineConfig(BaseModel):
    generation: GenerationConfig = GenerationConfig()
    evaluation: EvaluationConfig = EvaluationConfig()
    tracking: TrackingConfig = TrackingConfig()
    logging: LoggingConfig = LoggingConfig()
    auto_train: AutoTrainConfig = AutoTrainConfig()
    ml: MLConfig = MLConfig()


# ── Config Loader ────────────────────────────────────────────────────────────

class ConfigLoader:
    """Hierarchical config loader with env override support.

    Load order (later overrides earlier):
        1. Base defaults
        2. <env>.yaml (e.g. configs/production.yaml)
        3. Environment variables (UVMGEN_* prefix)
    """

    ENV_PREFIX = "UVMGEN_"

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or os.getcwd())

    def load(self, spec_path: str, pipeline_path: Optional[str] = None) -> tuple[DesignSpec, PipelineConfig]:
        design_spec = self._load_design_spec(spec_path)
        pipeline_cfg = self._load_pipeline(pipeline_path)
        self._apply_env_overrides(pipeline_cfg)
        return design_spec, pipeline_cfg

    def _load_design_spec(self, path: str) -> DesignSpec:
        from src.data.preprocessor import SpecPreprocessor
        from src.data.core_parser import CoreParser

        ext = Path(path).suffix.lower()
        if ext == ".core":
            raw = CoreParser().parse(Path(path).read_text(encoding="utf-8"))
        elif ext == ".v":
            from src.data.rtl_parser import RTLParser
            raw = RTLParser().parse(Path(path).read_text(encoding="utf-8"))
        else:
            raw = self._read_yaml(path)
            raw = SpecPreprocessor().preprocess(raw)
        return DesignSpec(**raw)

    def _load_pipeline(self, path: Optional[str] = None) -> PipelineConfig:
        base = PipelineConfig()
        if path and Path(path).exists():
            overrides = self._read_yaml(path)
            base = self._deep_merge(base, overrides)
        return base

    def _apply_env_overrides(self, cfg: PipelineConfig) -> None:
        prefix = self.ENV_PREFIX
        for key, val in os.environ.items():
            if key.startswith(prefix):
                parts = key[len(prefix):].lower().split("__")
                target = cfg
                for part in parts[:-1]:
                    target = getattr(target, part, None)
                    if target is None:
                        break
                else:
                    last = parts[-1]
                    if hasattr(target, last):
                        setattr(target, last, self._coerce(val, type(getattr(target, last))))

    @staticmethod
    def _read_yaml(path: str) -> dict:
        with open(path, "r") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _coerce(val: str, typ: type) -> Any:
        if typ is bool:
            return val.lower() in ("1", "true", "yes")
        if typ is int:
            return int(val)
        if typ is float:
            return float(val)
        return val

    @staticmethod
    def _deep_merge(base: PipelineConfig, overrides: dict) -> PipelineConfig:
        import json
        base_dict = json.loads(base.model_dump_json())
        for k, v in overrides.items():
            if k in base_dict and isinstance(base_dict[k], dict) and isinstance(v, dict):
                base_dict[k].update(v)
            else:
                base_dict[k] = v
        return PipelineConfig(**base_dict)
