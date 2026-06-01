"""
UVM Testbench Generator — Replicate Predictor

Industry-level ML-powered UVM testbench generation with coverage optimization.
"""

import os
import sys
import json
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
import numpy as np

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)
os.environ["UVMGEN_OUTPUT_DIR"] = os.path.join(repo_root, "output")
os.environ["LOG_LEVEL"] = "warning"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("replicate.predictor")

try:
    from cog import BasePredictor, Input, Path as CogPath
except ImportError:
    class BasePredictor: pass
    def Input(**kw): return None
    class CogPath: pass


class Predictor(BasePredictor):
    def setup(self) -> None:
        """Load ML models and infrastructure once at startup."""
        self.logger = logging.getLogger("replicate.predictor")
        self.logger.info("Initializing UVM Generation System...")

        from src.config import ConfigLoader
        from src.features.extractors import SpecFeatureExtractor
        from src.generation.engine import GenerationEngine
        from src.models.enhanced_ml_model_v2 import EnhancedMLGenerationModelV2
        from src.models.template_model import TemplateModel
        from src.models.registry import ModelRegistry
        from src.tracking.logger import setup_logging

        from src.models.ml_generation_model import MLModelConfig

        from src.data.collector import SpecCollector
        from src.data.preprocessor import SpecPreprocessor
        from src.data.validators import SpecValidator

        self.validator = SpecValidator()
        self.preprocessor = SpecPreprocessor()
        self.feature_extractor = SpecFeatureExtractor()
        self.registry = ModelRegistry()
        self.collector = SpecCollector()

        try:
            from src.models.coverage_predictor import CoveragePredictor
            self.coverage_predictor = CoveragePredictor()
            self.coverage_predictor.train_synthetic()
            self.logger.info("CoveragePredictor trained on synthetic data")
        except Exception as e:
            self.logger.warning("CoveragePredictor not available: %s", e)
            self.coverage_predictor = None

        self.model_v2 = EnhancedMLGenerationModelV2(
            templates_dir=os.path.join(repo_root, "src", "generation", "templates")
        )
        self.template_model = TemplateModel(
            templates_dir=os.path.join(repo_root, "src", "generation", "templates")
        )

        self.engine_v2 = GenerationEngine(self.model_v2)
        self.engine_template = GenerationEngine(self.template_model)

        self.cfg_loader = ConfigLoader()
        self.logger.info("System ready")

    def predict(
        self,
        spec_yaml: str = Input(
            description="YAML specification for the UART/SPI/I2C/AXI/Wishbone design",
            default="",
        ),
        design_name: str = Input(
            description="Design name (overrides spec)",
            default="uart_top",
        ),
        protocol: str = Input(
            description="Protocol: uart, spi, i2c, axi4lite, wishbone, apb",
            default="uart",
        ),
        model_type: str = Input(
            description="Model: v2 (full ML ensemble), template (fast Jinja2), hybrid",
            default="v2",
            choices=["v2", "template", "hybrid"],
        ),
        rl_strategy: str = Input(
            description="RL exploration strategy",
            default="ucb",
            choices=["ucb", "softmax", "epsilon_greedy", "thompson"],
        ),
        enable_learning: bool = Input(
            description="Enable online learning from coverage feedback",
            default=True,
        ),
        strict_uvm: bool = Input(
            description="Strict UVM compliance validation",
            default=True,
        ),
        max_iterations: int = Input(
            description="Auto-training iterations (coverage closure loops)",
            default=1,
            ge=1,
            le=20,
        ),
        coverage_target: float = Input(
            description="Coverage target percentage (auto-train until met)",
            default=90.0,
            ge=0.0,
            le=100.0,
        ),
        optimize_parameters: bool = Input(
            description="Use ML to predict optimal test parameters",
            default=True,
        ),
    ) -> CogPath:
        """Generate a UVM testbench with ML-optimized coverage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "output"
            outdir.mkdir(parents=True, exist_ok=True)

            spec = self._build_spec(spec_yaml, design_name, protocol)

            if optimize_parameters and self.coverage_predictor:
                params = self.coverage_predictor.predict_optimal_params(spec)
                self.logger.info("ML-optimized parameters: %s", params)

            gen_config = self._build_gen_config(
                spec, model_type, rl_strategy, enable_learning,
                strict_uvm, max_iterations
            )

            results = self._run_pipeline(spec, gen_config, outdir)

            report_path = outdir / "generation_report.json"
            with open(report_path, "w") as f:
                json.dump({
                    "design_name": design_name,
                    "protocol": protocol,
                    "model_type": model_type,
                    "files": list(results.get("files", {}).keys()),
                    "metrics": results.get("metrics", {}),
                    "coverage_prediction": results.get("coverage_prediction", {}),
                }, f, indent=2, default=str)

            summary_path = outdir / "summary.txt"
            with open(summary_path, "w") as f:
                f.write(self._format_summary(results))

            zip_path = outdir / "uvm_testbench.zip"
            self._zip_output(outdir, zip_path, results.get("files", {}))

            return CogPath(str(zip_path))

    def _build_spec(self, spec_yaml: str, design_name: str, protocol: str) -> Any:
        from src.config import DesignSpec

        if spec_yaml.strip():
            spec = self.cfg_loader.load_yaml(spec_yaml)
        else:
            spec_path = os.path.join(repo_root, "protocols", f"{protocol}.yaml")
            spec = self.cfg_loader.load(str(spec_path))

        if hasattr(spec, "design_name"):
            spec.design_name = design_name
        return spec

    def _build_gen_config(
        self, spec, model_type: str, rl_strategy: str,
        enable_learning: bool, strict_uvm: bool, max_iterations: int,
    ) -> Any:
        from src.config import PipelineConfig

        cfg = PipelineConfig()
        cfg.ml.enabled = model_type != "template"
        cfg.ml.model_type = "v2" if model_type == "v2" else model_type
        cfg.ml.rl_strategy = rl_strategy
        cfg.ml.enabled = enable_learning
        cfg.generation.strict_uvm = strict_uvm
        cfg.generation.max_iterations = max_iterations
        cfg.generation.output_dir = str(Path(tempfile.gettempdir()) / "uvmgen_output")
        return cfg

    def _run_pipeline(self, spec, config, outdir: Path) -> Dict:
        from src.pipeline import TBPipeline

        pipeline = TBPipeline(config)
        pipeline.cfg = config

        files = {}
        coverage_prediction = {}

        try:
            result = pipeline.run(spec)
            files = result.get("files", {}) if isinstance(result, dict) else {}
        except Exception as e:
            self.logger.warning("Pipeline error: %s — falling back to engine-only", e)
            engine = self.engine_v2 if config.ml.enabled else self.engine_template
            try:
                result = engine.generate(spec)
                files = result if isinstance(result, dict) else {}
            except Exception as e2:
                self.logger.error("Engine error: %s", e2)

        if self.coverage_predictor and files:
            coverage_prediction = self.coverage_predictor.predict_coverage(
                spec, files
            )

        metrics = {}
        if coverage_prediction:
            cov = coverage_prediction.get("coverage", {})
            metrics = {
                "predicted_coverage": cov.get("expected", 0),
                "coverage_gaps": cov.get("gaps", []),
                "recommended_sequences": coverage_prediction.get("recommended_sequences", []),
            }

        return {
            "files": files,
            "metrics": metrics,
            "coverage_prediction": coverage_prediction,
        }

    def _zip_output(self, outdir: Path, zip_path: Path, files: Dict) -> None:
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                file_path = outdir / name
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                zf.write(file_path, name)

            report = outdir / "generation_report.json"
            if report.exists():
                zf.write(report, "generation_report.json")

            summary = outdir / "summary.txt"
            if summary.exists():
                zf.write(summary, "summary.txt")

    def _format_summary(self, results: Dict) -> str:
        files = results.get("files", {})
        metrics = results.get("metrics", {})
        cov = results.get("coverage_prediction", {})

        lines = [
            "=" * 60,
            "UVM TESTBENCH GENERATION REPORT",
            "=" * 60,
            "",
            f"Files generated: {len(files)}",
            "",
        ]
        for name in files:
            lines.append(f"  - {name}")

        if metrics:
            lines.extend([
                "",
                "--- ML Metrics ---",
                f"Predicted coverage: {metrics.get('predicted_coverage', 'N/A')}%",
                f"Coverage gaps: {metrics.get('coverage_gaps', 'N/A')}",
                f"Recommended sequences: {metrics.get('recommended_sequences', 'N/A')}",
            ])

        if cov:
            lines.extend([
                "",
                "--- Coverage Prediction ---",
                f"Model confidence: {cov.get('confidence', 'N/A')}",
            ])

        lines.extend([
            "",
            "=" * 60,
        ])
        return "\n".join(lines)
