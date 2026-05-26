"""
Industry-level AI/ML generation model with:
- LLM-based code generation (CodeGen, CodeT5, StarCoder)
- Semantic code embeddings for intelligent similarity
- Reinforcement learning from validation feedback
- Multi-strategy retrieval (protocol-first, semantic, text)
- Spec-aware adaptation
- Code validation
- Multi-level fallback
- Comprehensive reporting

This model uses actual AI/ML:
1. Neural semantic embeddings (CodeBERT) for similarity
2. LLM generation (CodeGen, CodeT5) for actual code generation
3. Reinforcement learning that learns from validation feedback
4. Pattern learning from success/failure patterns
5. Auto-improving generation strategies
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import DesignSpec, PipelineConfig
from src.models.base_model import GenerationModel
from src.models.code_validator import (
    CodeValidator,
    FileValidationResult,
    ValidationReport,
    ValidationSeverity,
)
from src.models.ml_utils import RichFeatureVector
from src.models.ml_generation_model import MLModelConfig, NameNormalizer
from src.models.spec_adapter import (
    AdaptationPlan,
    MappingConfidence,
    SpecAdapter,
)
from src.models.similarity_index import SimilarityIndex, get_global_index
from src.models.template_model import TemplateModel

try:
    from src.models.semantic_encoder import SemanticCodeEncoder, SemanticEmbedding
    from src.models.llm_generator import LLMCodeGenerator, LLMGenerationResult
    from src.models.learning_module import LearningModule, ValidationFeedback

    ML_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning("Advanced ML modules not available: %s", e)
    ML_MODULES_AVAILABLE = False

logger = logging.getLogger("uvmgen")


class GenerationSource(Enum):
    RETRIEVAL_HIGH_CONF = "retrieval_high_confidence"
    RETRIEVAL_MEDIUM_CONF = "retrieval_medium_confidence"
    RETRIEVAL_LOW_CONF = "retrieval_low_confidence"
    LLM_GENERATION = "llm_generation"
    LLM_FALLBACK = "llm_fallback"
    TEMPLATE_FALLBACK = "template_fallback"
    BLENDED = "blended"
    HYBRID = "hybrid"
    LEARNING_IMPROVED = "learning_improved"


@dataclass
class GenerationResult:
    """
    Enhanced generation result with full validation and audit trail.
    """
    design_name: str
    source: GenerationSource
    passed: bool
    generated_files: Dict[str, str] = field(default_factory=dict)
    validation_report: Optional[ValidationReport] = None
    adaptation_plan: Optional[AdaptationPlan] = None
    similar_specs_found: int = 0
    best_match_score: float = 0.0
    files_from_retrieval: List[str] = field(default_factory=list)
    files_from_template: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_name": self.design_name,
            "source": self.source.value,
            "passed": self.passed,
            "file_count": len(self.generated_files),
            "similar_specs_found": self.similar_specs_found,
            "best_match_score": self.best_match_score,
            "files_from_retrieval": self.files_from_retrieval,
            "files_from_template": self.files_from_template,
            "warnings": self.warnings,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "validation": (
                self.validation_report.to_dict()
                if self.validation_report else None
            ),
            "adaptation": (
                {
                    "overall_score": self.adaptation_plan.overall_score,
                    "overall_confidence": self.adaptation_plan.overall_confidence.value,
                    "warnings": self.adaptation_plan.warnings,
                    "errors": self.adaptation_plan.errors,
                }
                if self.adaptation_plan else None
            ),
        }


@dataclass
class RetrievalCandidate:
    """A candidate from retrieval with pre-validation info."""
    result: Any
    feature_vector: RichFeatureVector
    spec_dict: Dict[str, Any]
    generated_files: Dict[str, str]
    adaptation_plan: Optional[AdaptationPlan] = None
    pre_validation_score: float = 0.0
    rank: int = 0


class EnhancedMLGenerationModel(GenerationModel):
    """
    Industry-level AI/ML generation model with actual learning capabilities.

    Key AI/ML features:
    1. LLM-based code generation (CodeGen, CodeT5, StarCoder)
    2. Semantic code embeddings (CodeBERT) for intelligent similarity
    3. Reinforcement learning from validation feedback
    4. Pattern learning from success/failure patterns
    5. Multi-strategy retrieval with intelligent selection
    6. Auto-improving generation strategies

    Traditional features:
    - Spec-aware adaptation with signal/register mapping
    - Pre-validation before output
    - Multi-level fallback strategies
    - Comprehensive reporting and audit trail
    """

    def __init__(
        self,
        name: str = "enhanced_ml_model",
        config: Optional[MLModelConfig] = None,
        index: Optional[SimilarityIndex] = None,
        templates_dir: Optional[str] = None,
        strict_validation: bool = True,
        use_llm: bool = True,
        use_semantic_encoder: bool = True,
        use_learning: bool = True,
        llm_model_name: Optional[str] = None,
        learning_storage_path: Optional[str] = None,
    ):
        super().__init__(name)
        self.config = config or MLModelConfig()
        self._index = index
        self._templates_dir = templates_dir
        self._template_model: Optional[TemplateModel] = None
        self._strict_validation = strict_validation
        self._metadata: Dict[str, Any] = {}
        self._last_result: Optional[GenerationResult] = None
        self._last_retrieval: Optional[Any] = None

        self._use_llm = use_llm and ML_MODULES_AVAILABLE
        self._use_semantic = use_semantic_encoder and ML_MODULES_AVAILABLE
        self._use_learning = use_learning and ML_MODULES_AVAILABLE

        self._llm_generator: Optional[LLMCodeGenerator] = None
        self._semantic_encoder: Optional[SemanticCodeEncoder] = None
        self._learning_module: Optional[LearningModule] = None

        if self._use_llm:
            self._llm_generator = LLMCodeGenerator(model_name=llm_model_name)
            logger.info("LLM generator enabled: %s", llm_model_name or "default")

        if self._use_semantic:
            self._semantic_encoder = SemanticCodeEncoder()
            logger.info("Semantic encoder enabled")

        if self._use_learning:
            self._learning_module = LearningModule(storage_path=learning_storage_path)
            logger.info("Learning module enabled")

    @property
    def index(self) -> SimilarityIndex:
        if self._index is None:
            if self.config.index_path:
                self._index = SimilarityIndex.load(self.config.index_path)
            else:
                self._index = get_global_index()
        return self._index

    @property
    def template_model(self) -> TemplateModel:
        if self._template_model is None:
            self._template_model = TemplateModel(
                name="fallback_template",
                templates_dir=self._templates_dir,
            )
        return self._template_model

    @property
    def last_retrieval(self) -> Optional[Any]:
        """Get information about the last retrieval operation."""
        from src.models.ml_generation_model import RetrievalInfo

        if self._last_retrieval is not None:
            return self._last_retrieval

        if self._last_result is not None:
            return RetrievalInfo(
                used_similarity=(self._last_result.similar_specs_found > 0),
                similar_specs=self._last_result.similar_specs_found,
                best_score=self._last_result.best_match_score,
            )

        return RetrievalInfo(used_similarity=False, similar_specs=0, best_score=0.0)

    def train(self, specs: List[DesignSpec]) -> Dict[str, Any]:
        """Train the model by adding specs to the similarity index."""
        from src.features.extractors import RichSpecFeatureExtractor

        if not self._templates_dir:
            import os
            self._templates_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "src", "generation", "templates"
            )

        self.template_model.train([])

        extractor = RichSpecFeatureExtractor()
        added_count = 0

        for spec in specs:
            try:
                fv = extractor.extract(spec)
                spec_dict = self._spec_to_dict(spec)

                cfg = PipelineConfig()
                if self._templates_dir:
                    cfg.generation.templates_dir = self._templates_dir

                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    cfg.generation.output_dir = tmp
                    files = self.template_model.predict(spec, cfg)
                    file_contents: Dict[str, str] = {}
                    for fname, fpath in files.items():
                        try:
                            file_contents[fname] = Path(fpath).read_text(encoding="utf-8")
                        except Exception:
                            pass

                self.index.add(fv, spec_dict, file_contents)
                added_count += 1
            except Exception as e:
                logger.warning("Failed to add spec to index: %s", e)

        self._metadata = {
            "model_type": "enhanced_ml",
            "strict_validation": self._strict_validation,
            "config": {
                "similarity_threshold": self.config.similarity_threshold,
                "auto_learn": self.config.auto_learn,
                "fallback_to_templates": self.config.fallback_to_templates,
            },
            "index_size": len(self.index),
            "added_in_train": added_count,
            "trained_on_specs": len(specs),
        }
        self._is_trained = True
        logger.info("Trained enhanced ML model: index has %d entries", len(self.index))
        return self._metadata

    def predict(
        self,
        spec: DesignSpec,
        cfg: PipelineConfig,
        extra_seqs: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Generate testbench with AI/ML-powered generation and fallback.

        AI/ML Workflow:
        1. Use learning module to select best generation strategy
        2. Try semantic similarity search (if semantic encoder available)
        3. Try LLM-based code generation (if LLM available)
        4. Try traditional retrieval-based generation
        5. Fallback to templates
        6. Record validation feedback to learning module
        7. Auto-learn from successful generation

        Traditional features:
        - Spec-aware adaptation
        - Pre-validation before writing
        - Multi-level fallback
        """
        if not self._is_trained:
            self.train([])

        from src.features.extractors import RichSpecFeatureExtractor
        extractor = RichSpecFeatureExtractor()
        query_fv = extractor.extract(spec)
        query_dict = self._spec_to_dict(spec)

        protocol = query_dict.get("protocol", "unknown")

        available_strategies = ["retrieval"]
        if self._use_llm and self._llm_generator:
            available_strategies.append("llm")
        available_strategies.append("template")

        selected_strategy = "retrieval"
        strategy_confidence = 0.5

        if self._use_learning and self._learning_module:
            selected_strategy, strategy_confidence = (
                self._learning_module.select_best_generation_strategy(
                    spec_dict=query_dict,
                    file_type="testbench",
                    available_sources=available_strategies,
                )
            )
            logger.info(
                "Learning module selected strategy: '%s' (confidence: %.2f)",
                selected_strategy,
                strategy_confidence,
            )

        similar = self.index.search(
            query_fv,
            top_k=self.config.top_k_retrieval,
            min_similarity=0.3,
        )

        if self._use_semantic and self._semantic_encoder and similar:
            similar = self._enhance_with_semantic_similarity(
                similar, query_dict
            )

        logger.info(
            "Enhanced ML generation: found %d similar specs, best score: %.3f",
            len(similar), similar[0].similarity if similar else 0.0
        )

        result: Optional[GenerationResult] = None

        if selected_strategy == "llm" and self._use_llm and self._llm_generator:
            logger.info("Trying LLM-based generation (selected by learning module)")
            result = self._try_llm_generation(query_dict, spec, cfg)

        if result is None and similar and similar[0].similarity >= self.config.similarity_threshold:
            result = self._try_retrieval_generation(
                similar, query_fv, query_dict, spec, cfg
            )

        if result is None and self._use_llm and self._llm_generator:
            logger.info("Trying LLM-based generation as fallback")
            result = self._try_llm_generation(query_dict, spec, cfg)

        if (
            result is None
            or (self._strict_validation and not result.passed)
            and self.config.fallback_to_templates
        ):
            if result is None:
                logger.info("No valid ML/LLM candidate, falling back to templates")
            else:
                logger.warning(
                    "LLM/retrieval generation failed validation (errors: %d), falling back to templates",
                    result.validation_report.total_errors if result.validation_report else 0
                )
            result = self._generate_with_fallback(spec, cfg, extra_seqs, result)

        if result is None:
            raise RuntimeError("All generation strategies failed")

        if self._use_learning and self._learning_module and result.validation_report:
            logger.info("Recording validation feedback to learning module")
            self._learning_module.record_feedback(
                design_name=spec.design_name,
                generation_source=result.source.value,
                spec_dict=query_dict,
                validation_results=result.validation_report.to_dict(),
            )

        if self.config.auto_learn and result.passed:
            self._learn_from_result(result, query_fv, query_dict)

        self._last_result = result
        self._log_result_summary(result)

        return result.generated_files

    def _enhance_with_semantic_similarity(
        self,
        similar: List[Any],
        query_dict: Dict[str, Any],
    ) -> List[Any]:
        """Enhance similarity scores using semantic code embeddings."""
        if not self._semantic_encoder or not self._semantic_encoder.is_available():
            return similar

        try:
            query_text = self._spec_dict_to_text(query_dict)
            query_emb = self._semantic_encoder.encode(
                text=query_text,
                embedding_type="spec",
                metadata=query_dict,
            )

            for item in similar:
                spec_text = self._spec_dict_to_text(item.spec_dict)
                cand_emb = self._semantic_encoder.encode(
                    text=spec_text,
                    embedding_type="spec",
                    metadata=item.spec_dict,
                )

                semantic_sim = self._semantic_encoder.similarity(query_emb, cand_emb)

                original_sim = item.similarity
                item.similarity = (original_sim * 0.6) + (semantic_sim * 0.4)

                logger.debug(
                    "Semantic enhancement: original=%.3f, semantic=%.3f, combined=%.3f",
                    original_sim, semantic_sim, item.similarity
                )

            similar = sorted(similar, key=lambda x: x.similarity, reverse=True)

        except Exception as e:
            logger.warning("Semantic similarity enhancement failed: %s", e)

        return similar

    def _spec_dict_to_text(self, spec_dict: Dict[str, Any]) -> str:
        """Convert spec dict to text for semantic encoding."""
        parts = []
        parts.append(f"design: {spec_dict.get('design_name', 'unknown')}")
        parts.append(f"protocol: {spec_dict.get('protocol', 'unknown')}")

        signals = spec_dict.get("signals", [])
        if signals:
            signal_names = [s.get("name", "") for s in signals if isinstance(s, dict)]
            parts.append(f"signals: {', '.join(signal_names[:20])}")

        registers = spec_dict.get("registers", [])
        if registers:
            reg_names = [r.get("name", "") for r in registers if isinstance(r, dict)]
            parts.append(f"registers: {', '.join(reg_names[:10])}")

        features = spec_dict.get("features", [])
        if features:
            parts.append(f"features: {', '.join(features[:10])}")

        return " | ".join(parts)

    def _try_llm_generation(
        self,
        query_dict: Dict[str, Any],
        spec: DesignSpec,
        cfg: PipelineConfig,
    ) -> Optional[GenerationResult]:
        """
        Try LLM-based code generation.

        This uses actual AI/ML:
        1. LLM (CodeGen, CodeT5, etc.) generates SystemVerilog code
        2. Uses few-shot examples for UVM patterns
        3. Validates generated code
        4. Falls back to templates if needed
        """
        if not self._llm_generator:
            return None

        design_name = spec.design_name.lower()

        file_types_to_generate = [
            "driver",
            "monitor",
            "agent",
        ]

        generated_files: Dict[str, str] = {}
        llm_results: Dict[str, LLMGenerationResult] = {}
        all_warnings: List[str] = []
        avg_confidence = 0.0

        for file_type in file_types_to_generate:
            try:
                llm_result = self._llm_generator.generate(
                    spec_dict=query_dict,
                    file_type=file_type,
                    use_few_shot=True,
                    max_tokens=1024,
                    temperature=0.2,
                )

                llm_results[file_type] = llm_result
                avg_confidence += llm_result.confidence
                all_warnings.extend(llm_result.warnings)

                file_name = f"{design_name}_{file_type}.sv"
                generated_files[file_name] = llm_result.generated_code

                logger.info(
                    "LLM generated %s (confidence: %.2f, tokens: %d)",
                    file_name,
                    llm_result.confidence,
                    llm_result.tokens_generated,
                )

            except Exception as e:
                logger.warning("LLM generation failed for %s: %s", file_type, e)
                all_warnings.append(f"LLM generation failed for {file_type}: {e}")

        if not generated_files:
            logger.warning("LLM generated no files, falling back")
            return None

        if llm_results:
            avg_confidence /= len(llm_results)

        try:
            template_files = self.template_model.predict(spec, cfg)
            template_contents: Dict[str, str] = {}
            for fname, fpath in template_files.items():
                try:
                    template_contents[fname] = Path(fpath).read_text(encoding="utf-8")
                except Exception:
                    pass

            for fname, content in template_contents.items():
                if fname not in generated_files:
                    generated_files[fname] = content

        except Exception as e:
            logger.warning("Could not fill missing files from templates: %s", e)

        validator = CodeValidator()
        val_report = validator.validate_files(generated_files, query_dict)

        total_errors = val_report.total_errors
        total_warnings = val_report.total_warnings + len(all_warnings)

        passed = val_report.overall_passed
        if self._strict_validation:
            passed = passed and (total_errors == 0)

        generation_source = GenerationSource.LLM_GENERATION
        if avg_confidence < 0.5:
            generation_source = GenerationSource.LLM_FALLBACK

        result = GenerationResult(
            design_name=spec.design_name,
            source=generation_source,
            passed=passed,
            generated_files=generated_files,
            validation_report=val_report,
            adaptation_plan=None,
            similar_specs_found=0,
            best_match_score=avg_confidence,
            files_from_retrieval=[],
            files_from_template=list(template_contents.keys()) if "template_contents" in dir() else [],
            warnings=all_warnings + [
                f"LLM confidence: {avg_confidence:.2f}",
                f"LLM warnings: {len(all_warnings)}",
            ],
            errors=[f"LLM errors: {total_errors}"] if total_errors > 0 else [],
        )

        return result

    def _try_retrieval_generation(
        self,
        similar: List[Any],
        query_fv: RichFeatureVector,
        query_dict: Dict[str, Any],
        spec: DesignSpec,
        cfg: PipelineConfig,
    ) -> Optional[GenerationResult]:
        """Try retrieval-based generation with validation."""
        candidates = self._rank_candidates(similar, query_fv, query_dict)

        if not candidates:
            return None

        best_candidate = candidates[0]
        logger.info(
            "Best candidate: '%s' (score: %.3f, pre-val: %.2f)",
            best_candidate.spec_dict.get("design_name", "unknown"),
            best_candidate.result.similarity,
            best_candidate.pre_validation_score,
        )

        if best_candidate.pre_validation_score < 0.5:
            logger.info("Candidate pre-validation score too low (%.2f)", best_candidate.pre_validation_score)
            return None

        adapted = self._adapt_candidate(best_candidate, query_dict, spec, cfg)
        if adapted is None:
            return None

        final_files, val_report, source = adapted

        passed = val_report.overall_passed if val_report else True
        if self._strict_validation:
            passed = passed and (val_report.total_errors == 0 if val_report else True)

        if best_candidate.result.similarity >= 0.9:
            generation_source = GenerationSource.RETRIEVAL_HIGH_CONF
        elif best_candidate.result.similarity >= 0.7:
            generation_source = GenerationSource.RETRIEVAL_MEDIUM_CONF
        else:
            generation_source = GenerationSource.RETRIEVAL_LOW_CONF

        result = GenerationResult(
            design_name=spec.design_name,
            source=generation_source,
            passed=passed,
            generated_files=final_files,
            validation_report=val_report,
            adaptation_plan=best_candidate.adaptation_plan,
            similar_specs_found=len(similar),
            best_match_score=best_candidate.result.similarity,
            files_from_retrieval=list(final_files.keys()),
            files_from_template=[],
            warnings=self._collect_warnings(best_candidate, val_report),
            errors=self._collect_errors(best_candidate, val_report),
        )

        return result

    def _rank_candidates(
        self,
        similar: List[Any],
        query_fv: RichFeatureVector,
        query_dict: Dict[str, Any],
    ) -> List[RetrievalCandidate]:
        """Rank candidates by similarity + pre-validation score."""
        candidates: List[RetrievalCandidate] = []

        for rank, result in enumerate(similar):
            if not result.generated_files:
                continue

            spec_dict = result.spec_dict
            gen_files = result.generated_files

            adapter = SpecAdapter(
                source_protocol=spec_dict.get("protocol"),
                target_protocol=query_fv.protocol_type,
                strict_mode=self._strict_validation,
            )
            plan = adapter.create_adaptation_plan(spec_dict, query_dict)

            pre_val_score = self._compute_pre_validation_score(plan, result)

            candidate = RetrievalCandidate(
                result=result,
                feature_vector=result.spec_dict,
                spec_dict=spec_dict,
                generated_files=gen_files,
                adaptation_plan=plan,
                pre_validation_score=pre_val_score,
                rank=rank,
            )
            candidates.append(candidate)

        candidates.sort(
            key=lambda c: (
                c.pre_validation_score * 0.6 +
                c.result.similarity * 0.4
            ),
            reverse=True,
        )

        return candidates

    def _compute_pre_validation_score(
        self,
        plan: AdaptationPlan,
        result: Any,
    ) -> float:
        """Compute a pre-validation score from the adaptation plan."""
        if plan.errors:
            return 0.0

        score = plan.overall_score

        if plan.unmapped_target_signals:
            score *= 0.5

        if plan.warnings:
            score *= 0.9

        if plan.overall_confidence == MappingConfidence.EXACT:
            score = min(1.0, score + 0.1)
        elif plan.overall_confidence == MappingConfidence.HIGH:
            score = min(1.0, score + 0.05)

        return max(0.0, min(1.0, score))

    def _adapt_candidate(
        self,
        candidate: RetrievalCandidate,
        query_dict: Dict[str, Any],
        spec: DesignSpec,
        cfg: PipelineConfig,
    ) -> Optional[Tuple[Dict[str, str], Optional[ValidationReport], GenerationSource]]:
        """Adapt the candidate to the target spec."""
        if not candidate.adaptation_plan:
            return None

        output_dir = Path(cfg.generation.output_dir) / f"{spec.design_name}_tb"
        output_dir.mkdir(parents=True, exist_ok=True)

        final_files: Dict[str, str] = {}
        adapted_contents: Dict[str, str] = {}

        adapter = SpecAdapter(
            source_protocol=candidate.spec_dict.get("protocol"),
            target_protocol=query_dict.get("protocol"),
            strict_mode=self._strict_validation,
        )

        total_changes: List[str] = []
        total_warnings: List[str] = []

        for filename, content in candidate.generated_files.items():
            new_filename = NameNormalizer.adapt_names(
                filename,
                candidate.spec_dict.get("design_name", ""),
                spec.design_name,
            )

            if new_filename == filename and candidate.spec_dict.get("design_name") != spec.design_name:
                base = os.path.splitext(filename)[0]
                ext = os.path.splitext(filename)[1]
                old_name = candidate.spec_dict.get("design_name", "")
                if old_name and old_name in base:
                    new_filename = base.replace(old_name, spec.design_name) + ext

            adapted_content, changes, warnings = adapter.apply_adaptation(
                candidate.adaptation_plan, content
            )

            total_changes.extend(changes)
            total_warnings.extend(warnings)
            adapted_contents[new_filename] = adapted_content

        validator = CodeValidator(query_dict)
        val_report = validator.validate_files(adapted_contents, spec.design_name)

        for filename, content in adapted_contents.items():
            out_path = output_dir / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            final_files[filename] = str(out_path)

        if total_changes:
            logger.info("Applied %d adaptations during generation", len(total_changes))
        if total_warnings:
            logger.warning("Adaptation produced %d warnings", len(total_warnings))

        source = GenerationSource.RETRIEVAL_MEDIUM_CONF
        if candidate.result.similarity >= 0.9:
            source = GenerationSource.RETRIEVAL_HIGH_CONF

        return final_files, val_report, source

    def _generate_with_fallback(
        self,
        spec: DesignSpec,
        cfg: PipelineConfig,
        extra_seqs: Optional[List[str]],
        previous_result: Optional[GenerationResult],
    ) -> GenerationResult:
        """Generate using template fallback."""
        logger.info("Using template-based generation as fallback")

        files = self.template_model.predict(spec, cfg, extra_seqs)

        query_dict = self._spec_to_dict(spec)
        validator = CodeValidator(query_dict)

        file_contents: Dict[str, str] = {}
        for fname, fpath in files.items():
            try:
                file_contents[fname] = Path(fpath).read_text(encoding="utf-8")
            except Exception:
                pass

        val_report = validator.validate_files(file_contents, spec.design_name)

        passed = val_report.overall_passed if val_report else True

        warnings: List[str] = []
        if previous_result:
            warnings.append("Fell back to template generation (retrieval validation failed)")
            if previous_result.errors:
                warnings.extend(previous_result.errors[:3])

        result = GenerationResult(
            design_name=spec.design_name,
            source=GenerationSource.TEMPLATE_FALLBACK,
            passed=passed,
            generated_files=files,
            validation_report=val_report,
            adaptation_plan=None,
            similar_specs_found=previous_result.similar_specs_found if previous_result else 0,
            best_match_score=previous_result.best_match_score if previous_result else 0.0,
            files_from_retrieval=[],
            files_from_template=list(files.keys()),
            warnings=warnings,
            errors=[],
        )

        return result

    def _learn_from_result(
        self,
        result: GenerationResult,
        query_fv: RichFeatureVector,
        query_dict: Dict[str, Any],
    ) -> None:
        """Learn from a successful generation."""
        try:
            file_contents: Dict[str, str] = {}
            for fname, fpath in result.generated_files.items():
                try:
                    file_contents[fname] = Path(fpath).read_text(encoding="utf-8")
                except Exception:
                    pass

            fp = self.index.add(query_fv, query_dict, file_contents)
            logger.debug("Learned from generation: added to index as %s", fp[:8])

            if self.config.index_path:
                self.index.save(self.config.index_path)
        except Exception as e:
            logger.warning("Failed to learn from generation: %s", e)

    def _collect_warnings(
        self,
        candidate: RetrievalCandidate,
        val_report: Optional[ValidationReport],
    ) -> List[str]:
        warnings: List[str] = []
        if candidate.adaptation_plan and candidate.adaptation_plan.warnings:
            warnings.extend(candidate.adaptation_plan.warnings[:5])
        if val_report and val_report.total_warnings > 0:
            warnings.append(f"Validation: {val_report.total_warnings} warning(s)")
        return warnings

    def _collect_errors(
        self,
        candidate: RetrievalCandidate,
        val_report: Optional[ValidationReport],
    ) -> List[str]:
        errors: List[str] = []
        if candidate.adaptation_plan and candidate.adaptation_plan.errors:
            errors.extend(candidate.adaptation_plan.errors)
        if val_report and val_report.total_errors > 0:
            errors.append(f"Validation: {val_report.total_errors} error(s)")
        return errors

    def _log_result_summary(self, result: GenerationResult) -> None:
        """Log a summary of the generation result."""
        status = "PASSED" if result.passed else "FAILED"
        logger.info(
            "Generation complete: %s (source=%s, files=%d, retrieval_specs=%d, best_score=%.2f)",
            status,
            result.source.value,
            len(result.generated_files),
            result.similar_specs_found,
            result.best_match_score,
        )
        if result.validation_report:
            logger.info(
                "  Validation: errors=%d, warnings=%d, pass_rate=%.1f%%",
                result.validation_report.total_errors,
                result.validation_report.total_warnings,
                result.validation_report.pass_rate * 100,
            )
        if result.warnings:
            for w in result.warnings[:3]:
                logger.warning("  %s", w)
        if result.errors:
            for e in result.errors[:3]:
                logger.error("  %s", e)

    @staticmethod
    def _spec_to_dict(spec: DesignSpec) -> Dict[str, Any]:
        """Convert DesignSpec to serializable dict."""
        return {
            "design_name": spec.design_name,
            "protocol": spec.protocol,
            "clock_reset": {
                "clock": spec.clock_reset.clock,
                "reset": spec.clock_reset.reset,
                "reset_active": spec.clock_reset.reset_active,
            },
            "interfaces": [
                {
                    "name": iface.name,
                    "signals": [
                        {"name": s.name, "direction": s.direction, "width": s.width}
                        for s in iface.signals
                    ],
                }
                for iface in spec.interfaces
            ],
            "registers": [
                {
                    "name": r.name,
                    "address": r.address,
                    "access": r.access,
                    "size": r.size,
                    "reset_value": r.reset_value,
                    "fields": [
                        {"name": f.name, "bits": f.bits, "description": f.description}
                        for f in r.fields
                    ],
                }
                for r in spec.registers
            ],
        }

    def save(self, path: str) -> None:
        """Save the model to disk."""
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "name": self.name,
            "model_type": "enhanced_ml",
            "strict_validation": self._strict_validation,
            "config": {
                "similarity_threshold": self.config.similarity_threshold,
                "auto_learn": self.config.auto_learn,
                "fallback_to_templates": self.config.fallback_to_templates,
                "index_path": self.config.index_path,
                "top_k_retrieval": self.config.top_k_retrieval,
            },
            "metadata": self._metadata,
            "index_size": len(self.index),
        }

        (save_dir / "model_metadata.json").write_text(
            json.dumps(meta, indent=2),
            encoding="utf-8",
        )

        index_path = save_dir / "similarity_index.json"
        self.index.save(str(index_path))

        if self._template_model:
            tmpl_dir = save_dir / "template_model"
            self._template_model.save(str(tmpl_dir))

        logger.info("Saved enhanced ML model to %s", save_dir)

    @classmethod
    def load(cls, path: str) -> "EnhancedMLGenerationModel":
        """Load the model from disk."""
        load_dir = Path(path)
        meta_path = load_dir / "model_metadata.json"

        if not meta_path.exists():
            raise FileNotFoundError(f"Model metadata not found: {meta_path}")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        config_dict = meta.get("config", {})

        config = MLModelConfig(
            similarity_threshold=config_dict.get("similarity_threshold", 0.75),
            auto_learn=config_dict.get("auto_learn", True),
            fallback_to_templates=config_dict.get("fallback_to_templates", True),
            index_path=config_dict.get("index_path"),
            top_k_retrieval=config_dict.get("top_k_retrieval", 3),
        )

        index_path = load_dir / "similarity_index.json"
        index = SimilarityIndex.load(str(index_path)) if index_path.exists() else None

        strict = meta.get("strict_validation", True)

        model = cls(
            name=meta["name"],
            config=config,
            index=index,
            strict_validation=strict,
        )
        model._metadata = meta.get("metadata", {})
        model._is_trained = True

        tmpl_dir = load_dir / "template_model"
        if tmpl_dir.exists():
            model._template_model = TemplateModel.load(str(tmpl_dir))

        logger.info("Loaded enhanced ML model from %s", load_dir)
        return model

    @property
    def last_result(self) -> Optional[GenerationResult]:
        """Get the last generation result with full details."""
        return self._last_result


import os
