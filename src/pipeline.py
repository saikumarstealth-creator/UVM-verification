from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import ConfigLoader, DesignSpec, PipelineConfig
from src.data.collector import SpecCollector
from src.data.preprocessor import SpecPreprocessor
from src.data.validators import SpecValidator
from src.evaluation.coverage_analyzer import CoverageAnalyzer
from src.evaluation.metrics import TBMetrics
from src.evaluation.reporters import Reporter, Report
from src.features.extractors import SpecFeatureExtractor
from src.generation.engine import GenerationEngine
from src.models.base_model import GenerationModel
from src.models.enhanced_ml_model import EnhancedMLGenerationModel
from src.models.ml_generation_model import MLGenerationModel, MLModelConfig
from src.models.registry import ModelRegistry
from src.models.template_model import TemplateModel
from src.simulation import Simulator
from src.simulation.base import CoverageDB
from src.simulation.icarus import IcarusSimulator
from src.simulation.stub_sim import StubSimulator
from src.tracking.experiments import ExperimentTracker
from src.tracking.logger import setup_logging
from src.utils.decorators import timer


class TBPipeline:
    """End-to-end pipeline with auto-training loop over coverage feedback."""

    def __init__(self, pipeline_cfg: Optional[PipelineConfig] = None):
        self.cfg = pipeline_cfg or PipelineConfig()
        self.logger = setup_logging(self.cfg.logging)
        self.validator = SpecValidator()
        self.preprocessor = SpecPreprocessor()
        self.feature_extractor = SpecFeatureExtractor()
        self.model = self._create_model()
        self.engine = GenerationEngine(self.model)
        self.metrics_calc = TBMetrics()
        self.reporter = Reporter(output_dir=self.cfg.generation.output_dir)
        self.tracker = ExperimentTracker() if self.cfg.tracking.enabled else None
        self.registry = ModelRegistry()
        self.simulator: Simulator = self._create_simulator()
        self.coverage_analyzer: Optional[CoverageAnalyzer] = None
        self.coverage_analysis: Optional[Any] = None

    def _create_model(self) -> GenerationModel:
        """Create the appropriate model based on ML config."""
        ml_cfg = self.cfg.ml

        if not ml_cfg.enabled:
            self.logger.info("Using template-based generation (ML disabled)")
            return TemplateModel(templates_dir=self.cfg.generation.templates_dir)

        model_type = ml_cfg.model_type
        self.logger.info("ML generation enabled, model_type=%s", model_type)

        if model_type in ("ml", "hybrid", "llm", "semantic"):
            ml_model_config = MLModelConfig(
                similarity_threshold=ml_cfg.similarity_threshold,
                auto_learn=ml_cfg.auto_learn,
                index_path=ml_cfg.index_path,
                top_k_retrieval=ml_cfg.top_k_retrieval,
                fallback_to_templates=ml_cfg.fallback_to_templates,
            )
            model = EnhancedMLGenerationModel(
                name="enhanced_ml_model",
                config=ml_model_config,
                templates_dir=self.cfg.generation.templates_dir,
                strict_validation=True,
                use_llm=ml_cfg.use_llm,
                use_semantic_encoder=ml_cfg.use_semantic_encoder,
                use_learning=ml_cfg.use_learning,
                llm_model_name=ml_cfg.llm_model_name,
                learning_storage_path=ml_cfg.learning_storage_path,
            )
            self.logger.info("Created EnhancedMLGenerationModel with index size: %d", len(model.index))

            if model_type == "llm":
                self.logger.info("LLM mode: will prioritize LLM generation")
            elif model_type == "semantic":
                self.logger.info("Semantic mode: will use semantic embeddings for similarity")

            return model

        self.logger.info("Falling back to template model")
        return TemplateModel(templates_dir=self.cfg.generation.templates_dir)

    def _create_simulator(self) -> Simulator:
        sim_type = self.cfg.auto_train.simulator
        if sim_type == "icarus":
            return IcarusSimulator(
                work_dir=sim_output_path(self.cfg),
                iverilog_path="iverilog",
                vvp_path="vvp"
            )
        return StubSimulator(work_dir=sim_output_path(self.cfg))

    def _merge_cfg(self, loaded: PipelineConfig) -> None:
        user_dict = self.cfg.model_dump(exclude_none=True)
        loaded_dict = loaded.model_dump()
        for section in loaded_dict:
            if section in user_dict and isinstance(loaded_dict[section], dict):
                for key, val in user_dict[section].items():
                    if val is not None:
                        loaded_dict[section][key] = val
        self.cfg = PipelineConfig(**loaded_dict)

    @timer
    def run(self, spec_path: str, pipeline_config_path: Optional[str] = None) -> Dict[str, Any]:
        self.logger.info("Pipeline start — spec: %s", spec_path)

        # 1. Load
        loader = ConfigLoader()
        design_spec, pipeline_cfg = loader.load(spec_path, pipeline_config_path)
        self._merge_cfg(pipeline_cfg)
        self.logger.info("Design spec loaded: %s", design_spec.design_name)

        # 2. Validate
        validation = self.validator.validate(design_spec, strict=self.cfg.generation.strict_validation)
        if not validation:
            self.logger.error("Validation failed:\n%s", validation)
            raise ValueError(str(validation))
        self.logger.info("Validation passed")

        # 3. Feature extraction
        features = self.feature_extractor.extract(design_spec)
        self.logger.info("Features extracted: protocol=%s, complexity=%.2f",
                         features.protocol_type, features.complexity_score)

        # 4. Train model
        self.logger.info("Training model...")
        train_meta = self.model.train([design_spec])
        self.logger.info("Model trained: %s", train_meta)

        # 5. Setup coverage analyzer
        self.coverage_analyzer = CoverageAnalyzer(design_spec)

        # 6. Auto-training loop: generate → simulate → analyze → improve
        extra_seqs: List[str] = []
        all_versions: List[str] = []
        final_metrics: Dict[str, float] = {}
        all_generated: Dict[str, str] = {}
        auto_train = self.cfg.auto_train

        for iteration in range(1, auto_train.max_iterations + 1):
            self.cfg.generation.iteration = iteration
            self.logger.info("=== Auto-train iteration %d/%d ===", iteration, auto_train.max_iterations)

            # 6a. Generate TB (with extra sequences from previous iteration)
            self.logger.info("Generating testbench (iteration %d)...", iteration)
            generated = self.engine.generate(design_spec, self.cfg, extra_seqs=extra_seqs)
            all_generated.update(generated)
            self.logger.info("Generated %d files (total %d)", len(generated), len(all_generated))

            # 6b. Evaluate static metrics (against all accumulated files)
            eval_metrics = self.metrics_calc.evaluate_all(
                design_spec, list(all_generated.keys()),
                coverage_analysis=self.coverage_analysis
            )
            final_metrics = eval_metrics

            # 6c. Simulate (multi-seed regression)
            sim_result = None
            coverage_db = None
            if auto_train.enabled:
                self.logger.info("Running simulation (simulator=%s, seeds=%d)...",
                                 self.simulator.name(), auto_train.num_seeds)
                file_list = list(all_generated.values())
                sim_result, coverage_db = self.simulator.run_multi_seed(
                    file_list, num_seeds=auto_train.num_seeds, top="testbench"
                )
                self.logger.info("Simulation complete — coverage=%.1f%%, passed=%s (merged %d seeds)",
                                 sim_result.coverage_pct, sim_result.passed, auto_train.num_seeds)

                # 6d. Analyze coverage
                self.coverage_analysis = self.coverage_analyzer.analyze(sim_result)
                self.logger.info("Coverage analysis: %s", self.coverage_analysis.summary())

                # Update metrics with simulation data
                eval_metrics.update(self.metrics_calc.coverage_gap_metrics(self.coverage_analysis))

                # 6e. Generate targeted sequences for uncovered bins
                extra_seqs = self.coverage_analyzer.generate_target_sequences(self.coverage_analysis)
                if extra_seqs:
                    self.logger.info("Generated %d targeted sequences for uncovered bins",
                                     len(extra_seqs))

                # 6f. Check termination conditions
                if self.coverage_analysis.meets_goal(auto_train.coverage_target):
                    self.logger.info("Coverage target reached (%.1f%% >= %.1f%%) — stopping",
                                     sim_result.coverage_pct, auto_train.coverage_target)
                elif iteration >= 2 and self.coverage_analysis.coverage_gain_rate < auto_train.coverage_gain_min:
                    self.logger.info("Coverage gain rate too low (%.1f%% < %.1f%%) — stopping",
                                     self.coverage_analysis.coverage_gain_rate,
                                     auto_train.coverage_gain_min)
                elif iteration >= auto_train.max_iterations:
                    self.logger.info("Max iterations reached (%d)", auto_train.max_iterations)

            # 6g. Evaluate pass/fail (only quality metrics, not diagnostic ones)
            quality_keys = {"completeness", "interface_signal_coverage", "register_coverage"}
            quality_values = [v for k, v in eval_metrics.items() if k in quality_keys and isinstance(v, float)]
            passed = all(v >= self.cfg.evaluation.threshold for v in quality_values) if quality_values else True
            report = Report(eval_metrics, design_spec.design_name, passed)
            self.reporter.report(report)

            # 6h. Register version
            sim_cov = sim_result.coverage_pct if sim_result else None
            version = self.registry.register(
                self.model,
                metrics=eval_metrics,
                artifacts=generated,
                spec_name=design_spec.design_name,
                sim_coverage=sim_cov,
                iteration=iteration
            )
            all_versions.append(version)
            self.logger.info("Registered version %s (coverage=%s)", version, sim_cov)

            # 6i. Track experiment
            if self.tracker:
                run_id = self.tracker.start_run(params={
                    "design": design_spec.design_name,
                    "iteration": iteration,
                    "version": version,
                    "simulator": self.simulator.name(),
                    "interfaces": len(design_spec.interfaces),
                    "registers": len(design_spec.registers),
                    "complexity": features.complexity_score,
                    "coverage_target": auto_train.coverage_target,
                })
                for k, v in eval_metrics.items():
                    if isinstance(v, (int, float)):
                        self.tracker.log_metric(k, float(v))
                for path in generated.values():
                    self.tracker.log_artifact(path)
                self.tracker.finish_run()

            # 6j. Stop if simulation didn't improve coverage (only from iteration 2+)
            if auto_train.enabled and (
                self.coverage_analysis.meets_goal(auto_train.coverage_target) or
                (iteration >= 2 and self.coverage_analysis.coverage_gain_rate < auto_train.coverage_gain_min)
            ):
                break

        # 7. Compare versions
        version_comparison = {}
        if len(all_versions) >= 2:
            version_comparison = self.registry.compare_versions(
                all_versions[-2], all_versions[-1]
            )
            self.logger.info("Version comparison (%s vs %s): %s",
                             all_versions[-2], all_versions[-1],
                             version_comparison.get("metric_deltas", {}))

        # 8. Coverage trend
        trend = self.registry.coverage_trend() if auto_train.enabled else []

        return {
            "design_name": design_spec.design_name,
            "generated_files": all_generated,
            "features": features.model_dump(),
            "evaluation": final_metrics,
            "passed": passed,
            "model_version": all_versions[-1] if all_versions else "v0",
            "all_versions": all_versions,
            "version_comparison": version_comparison,
            "coverage_trend": trend,
            "auto_train_iterations": len(all_versions),
            "simulator": self.simulator.name(),
            "coverage_analysis": {
                "total_bins": self.coverage_analysis.sim_result.total_bins if self.coverage_analysis else 0,
                "covered_bins": self.coverage_analysis.sim_result.covered_bins if self.coverage_analysis else 0,
                "coverage_pct": self.coverage_analysis.sim_result.coverage_pct if self.coverage_analysis else 0.0,
                "gaps": [{"bin": g.bin_name, "addr": g.register_addr, "dir": g.direction}
                         for g in (self.coverage_analysis.gaps if self.coverage_analysis else [])],
            } if self.coverage_analysis else None,
        }


def sim_output_path(cfg: PipelineConfig) -> str:
    import os
    return os.path.join(cfg.generation.output_dir, "sim_output")
