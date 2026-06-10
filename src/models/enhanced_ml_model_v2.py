"""
Enhanced ML Generation Model V2 — Production-Grade.

Architecture:
  1. Ensemble strategy selection (run top-K strategies, pick best result)
  2. Quality gate with retry and fallback chain
  3. Generation metrics tracking (latency, success rate, avg score)
  4. Spec-driven caching (MD5-based, TTL-aware)
  5. Concurrent strategy execution (thread pool)
  6. Feedback loop for online learning
  7. Model versioning with full state serialization
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
import pickle
import itertools
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import numpy as np

from src.models.base_model import GenerationModel
from src.models.template_model import TemplateModel
from src.models.coverage_predictor import CoveragePredictor, SpecFeatures
from src.config import PipelineConfig, DesignSpec

HAS_OPTUNA = False
try:
    import optuna
    HAS_OPTUNA = True
except ImportError:
    pass


def _retry_with_backoff(
    fn, max_retries: int = 3, base_delay: float = 0.5, backoff: float = 2.0,
) -> Any:
    """Execute fn with exponential backoff on transient failures."""
    import functools
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn()
        except (ConnectionError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = base_delay * (backoff ** attempt)
                logger.warning("Transient failure (attempt %d/%d): %s — retrying in %.1fs", attempt + 1, max_retries, e, delay)
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _content_dict_to_path_dict(
    files: Dict[str, str],
    output_dir: Path,
) -> Dict[str, str]:
    """Write a {filename: content} dict to disk and return {filename: path}."""
    result: Dict[str, str] = {}
    for fname, content in files.items():
        out_path = output_dir / fname
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        result[fname] = str(out_path)
    return result


def _validate_spec_dict(spec_dict: Dict[str, Any]) -> None:
    """Validate spec dict has required fields before generation."""
    if not isinstance(spec_dict, dict):
        raise TypeError(f"Expected dict, got {type(spec_dict).__name__}")
    if "design_name" not in spec_dict:
        raise ValueError("spec_dict must contain 'design_name'")
    if "protocol" not in spec_dict:
        logger.warning("spec_dict missing 'protocol', defaulting to 'unknown'")
    if not spec_dict.get("design_name"):
        raise ValueError("'design_name' must be a non-empty string")

try:
    from src.features.extractors import RichSpecFeatureExtractor
    from src.models.similarity_index import SimilarityIndex, SearchResult
    from src.models.ml_utils import (
        RichFeatureVector,
        combined_similarity,
        HybridVectorizer,
    )
    from src.models.spec_adapter import SpecAdapter, AdaptationPlan
    from src.models.code_validator import (
        CodeValidator,
        ValidationReport,
        FileValidationResult,
    )
    from src.models.advanced_pattern_learner import (
        AdvancedPatternLearner,
        PatternType,
        Pattern,
    )
    from src.models.advanced_rl_learner import (
        AdvancedReinforcementLearner,
        ExplorationStrategy,
        Experience,
    )
    from src.models.advanced_code_validator import (
        AdvancedCodeValidator,
        ValidationReport as AdvancedValidationReport,
    )
    HAS_ADVANCED = True
except ImportError as e:
    logger = logging.getLogger("uvmgen.ml")
    logger.warning("Some advanced components not available: %s", e)
    HAS_ADVANCED = False


logger = logging.getLogger("uvmgen.ml.enhanced")


class GenerationSource(Enum):
    RETRIEVAL = "retrieval"
    LLM = "llm"
    TEMPLATE = "template"
    HYBRID = "hybrid"
    ENSEMBLE = "ensemble"


@dataclass
class RetrievalInfo:
    used_similarity: bool = True
    similar_specs: int = 0
    best_score: float = 0.0
    best_spec_name: str = ""
    adaptation_score: float = 0.0
    pre_validation_score: float = 0.0
    retrieval_strategy: str = "default"


@dataclass
class GenerationResult:
    files: Dict[str, str] = field(default_factory=dict)
    source: GenerationSource = GenerationSource.TEMPLATE
    retrieval_info: Optional[RetrievalInfo] = None
    validation_report: Optional[AdvancedValidationReport] = None
    score: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    strategy_used: str = "template"
    model_version: int = 1


@dataclass
class StrategyWeights:
    retrieval_weight: float = 0.4
    llm_weight: float = 0.3
    template_weight: float = 0.3
    ensemble_weight: float = 0.2

    def normalize(self) -> StrategyWeights:
        total = self.retrieval_weight + self.llm_weight + self.template_weight + self.ensemble_weight
        if total <= 0:
            return StrategyWeights(0.3, 0.25, 0.25, 0.2)
        return StrategyWeights(
            retrieval_weight=self.retrieval_weight / total,
            llm_weight=self.llm_weight / total,
            template_weight=self.template_weight / total,
            ensemble_weight=self.ensemble_weight / total,
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "retrieval": self.retrieval_weight,
            "llm": self.llm_weight,
            "template": self.template_weight,
            "ensemble": self.ensemble_weight,
        }

    def adapt(self, strategy_performance: Dict[str, float], lr: float = 0.05) -> None:
        if not strategy_performance:
            return
        for key, attr in [("retrieval", "retrieval_weight"), ("llm", "llm_weight"),
                          ("template", "template_weight"), ("ensemble", "ensemble_weight")]:
            if key in strategy_performance:
                current = getattr(self, attr)
                delta = lr * (strategy_performance[key] - 0.5)
                setattr(self, attr, max(0.05, min(0.8, current + delta)))
        norm = self.normalize()
        self.retrieval_weight = norm.retrieval_weight
        self.llm_weight = norm.llm_weight
        self.template_weight = norm.template_weight
        self.ensemble_weight = norm.ensemble_weight


class MetricsTracker:
    def __init__(self, max_history: int = 2000):
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history
        self._strategy_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "runs": 0, "successes": 0, "avg_score": 0.0, "avg_latency": 0.0,
        })

    def record(self, entry: Dict[str, Any]) -> None:
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        strategy = entry.get("strategy", "unknown")
        s = self._strategy_stats[strategy]
        s["runs"] += 1
        if entry.get("passed", False):
            s["successes"] += 1
        s["avg_score"] = (s["avg_score"] * (s["runs"] - 1) + entry.get("score", 0.0)) / s["runs"]
        s["avg_latency"] = (s["avg_latency"] * (s["runs"] - 1) + entry.get("latency_ms", 0.0)) / s["runs"]

    def get_strategy_performance(self) -> Dict[str, float]:
        return {
            name: stats["avg_score"]
            for name, stats in self._strategy_stats.items()
            if stats["runs"] > 0
        }

    def get_summary(self, n_recent: int = 50) -> Dict[str, Any]:
        recent = self._history[-n_recent:] if self._history else []
        passed = sum(1 for h in recent if h.get("passed", False))
        return {
            "total_generations": len(self._history),
            "recent_window": len(recent),
            "recent_pass_rate": passed / len(recent) if recent else 0.0,
            "recent_avg_score": sum(h.get("score", 0.0) for h in recent) / len(recent) if recent else 0.0,
            "strategy_stats": dict(self._strategy_stats),
            "strategy_performance": self.get_strategy_performance(),
        }


class GenerationCache:
    """Spec-driven cache with content-addressable keys, TTL, and size limits."""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 256):
        self._cache: Dict[str, Tuple[float, Dict[str, str]]] = {}
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._access_order: List[str] = []

    def _make_key(self, spec_dict: Dict[str, Any], protocol: str) -> str:
        raw = json.dumps(spec_dict, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest() + f"@{protocol}"

    def _evict_if_needed(self) -> None:
        if len(self._cache) > self._max_entries:
            over = len(self._cache) - self._max_entries
            for _ in range(over):
                if self._access_order:
                    oldest = self._access_order.pop(0)
                    self._cache.pop(oldest, None)

    def _clean_expired(self) -> None:
        now = time.time()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts >= self._ttl]
        for k in expired:
            del self._cache[k]
            if k in self._access_order:
                self._access_order.remove(k)

    def get(self, spec_dict: Dict[str, Any], protocol: str) -> Optional[Dict[str, str]]:
        key = self._make_key(spec_dict, protocol)
        if key in self._cache:
            timestamp, files = self._cache[key]
            if time.time() - timestamp < self._ttl:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return files
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
        return None

    def set(self, spec_dict: Dict[str, Any], protocol: str, files: Dict[str, str]) -> None:
        key = self._make_key(spec_dict, protocol)
        self._cache[key] = (time.time(), files)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        self._evict_if_needed()

    def invalidate(self, spec_dict: Dict[str, Any], protocol: str) -> None:
        key = self._make_key(spec_dict, protocol)
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()


class EnhancedMLGenerationModelV2(GenerationModel):
    """
    Production-grade generation model with:
      - Ensemble strategy execution (run top-K, pick best)
      - Quality gate with retry + fallback chain
      - Metrics tracking with per-strategy stats
      - Spec-driven caching (MD5-based)
      - RL-based strategy selection (Double Q, prioritized replay, n-step)
      - Coverage predictor with uncertainty quantification
      - Full model serialization / versioning
    """

    def __init__(
        self,
        name: Any = "enhanced_ml_model_v2",
        config: Optional[Any] = None,
        templates_dir: str = "src/generation/templates",
        strict_validation: bool = True,
        use_llm: bool = False,
        use_semantic_encoder: bool = False,
        use_learning: bool = True,
        llm_model_name: Optional[str] = None,
        learning_storage_path: Optional[str] = None,
        exploration_strategy: str = "ucb",
        max_concurrent_strategies: int = 6,
        quality_threshold: float = 0.6,
        enable_caching: bool = True,
        cache_ttl: int = 86400,
        enable_adaptive_weights: bool = True,
        enable_auto_tune: bool = False,
        use_neural_rl: bool = False,
        sac_entropy_coef: float = 0.2,
        use_cosine_decay: bool = True,
    ):
        if isinstance(name, PipelineConfig):
            cfg = name
            name_str = "enhanced_ml_model_v2"
            self._user_cfg = cfg
            if cfg.ml:
                exploration_strategy = cfg.ml.exploration_strategy or exploration_strategy
                use_llm = cfg.ml.use_llm if hasattr(cfg.ml, 'use_llm') else use_llm
                use_semantic_encoder = cfg.ml.use_semantic_encoder if hasattr(cfg.ml, 'use_semantic_encoder') else use_semantic_encoder
                use_learning = cfg.ml.use_learning if hasattr(cfg.ml, 'use_learning') else use_learning
                learning_storage_path = cfg.ml.learning_storage_path or learning_storage_path
                strict_validation = cfg.ml.strict_validation if hasattr(cfg.ml, 'strict_validation') else strict_validation
        elif isinstance(name, str):
            name_str = name
        else:
            name_str = "enhanced_ml_model_v2"
        super().__init__(name_str)

        self._templates_dir = templates_dir
        self._strict_validation = strict_validation
        self._use_llm = use_llm
        self._use_semantic_encoder = use_semantic_encoder
        self._use_learning = use_learning
        self._llm_model_name = llm_model_name
        self._learning_storage_path = learning_storage_path
        self._max_concurrent = max_concurrent_strategies
        self._quality_threshold = quality_threshold
        self._enable_caching = enable_caching
        self._enable_adaptive_weights = enable_adaptive_weights
        self._enable_auto_tune = enable_auto_tune

        self._template_model = TemplateModel(templates_dir=templates_dir)
        self._index: Optional[SimilarityIndex] = None
        self._extractor: Optional[RichSpecFeatureExtractor] = None
        self._adapter: Optional[SpecAdapter] = None
        self._vectorizer: Optional[HybridVectorizer] = None
        self._pattern_learner: Optional[AdvancedPatternLearner] = None
        self._rl_learner: Optional[AdvancedReinforcementLearner] = None
        self._code_validator: Optional[AdvancedCodeValidator] = None
        self._coverage_predictor = CoveragePredictor(random_state=42)

        self._metrics = MetricsTracker()
        self._cache = GenerationCache(ttl_seconds=cache_ttl) if enable_caching else None

        self.last_retrieval: Optional[RetrievalInfo] = None
        self.last_coverage_prediction: Optional[Dict[str, Any]] = None
        self._generation_history: List[Dict[str, Any]] = []
        self._model_version: int = 1
        self._changelog: List[str] = []

        strategy_map = {
            "epsilon_greedy": ExplorationStrategy.EPSILON_GREEDY,
            "softmax": ExplorationStrategy.SOFTMAX,
            "ucb": ExplorationStrategy.UCB,
            "thompson": ExplorationStrategy.THOMPSON_SAMPLING,
            "sac": ExplorationStrategy.SAC,
        }
        self._exploration_strategy = strategy_map.get(
            exploration_strategy.lower(), ExplorationStrategy.UCB
        )
        self._strategy_weights = StrategyWeights()
        self._initialize_components(use_neural_rl=use_neural_rl, sac_entropy_coef=sac_entropy_coef, use_cosine_decay=use_cosine_decay)

    def _initialize_components(self, use_neural_rl: bool = False, sac_entropy_coef: float = 0.2, use_cosine_decay: bool = True) -> None:
        if HAS_ADVANCED:
            self._extractor = RichSpecFeatureExtractor()
            self._index = SimilarityIndex()
            self._adapter = SpecAdapter()
            self._vectorizer = HybridVectorizer()
            if self._use_learning:
                self._pattern_learner = AdvancedPatternLearner()
                rl_kwargs = {
                    "exploration_strategy": self._exploration_strategy,
                    "use_eligibility_traces": True,
                    "replay_buffer_capacity": 100000,
                    "use_neural_q": use_neural_rl,
                    "sac_entropy_coef": sac_entropy_coef,
                    "use_cosine_decay": use_cosine_decay,
                }
                self._rl_learner = AdvancedReinforcementLearner(**rl_kwargs)
            if self._learning_storage_path and os.path.exists(self._learning_storage_path):
                self._load_learning_state()
            logger.info(
                "EnhancedMLGenerationModelV2 v%d initialized (strategy=%s, ensemble=%d strats, neural_rl=%s, adaptive_weights=%s, auto_tune=%s)",
                self._model_version, self._exploration_strategy.value, self._max_concurrent,
                use_neural_rl, self._enable_adaptive_weights, self._enable_auto_tune,
            )
        else:
            logger.warning("Advanced components not available, using template fallback only")

    def train(
        self,
        specs: List[DesignSpec],
        pre_generated: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        if not HAS_ADVANCED or not self._extractor or not self._index:
            self._template_model.train(specs)
            return {"index_size": 0, "model_name": self.name}
        for spec in specs:
            features = self._extractor.extract(spec)
            spec_dict = spec.model_dump() if hasattr(spec, 'model_dump') else dict(spec)
            generated = (pre_generated or {}).get(spec.design_name, {})
            self._index.add(features, spec_dict, generated)
        all_features = []
        for entry in self._index:
            if hasattr(entry, 'feature_vector'):
                all_features.append(entry.feature_vector.to_text_repr())
        if all_features and self._vectorizer:
            self._vectorizer.fit(all_features)
        logger.info("Trained on %d specs (index=%d)", len(specs), len(self._index))
        return {"index_size": len(self._index), "model_name": self.name}

    def train_on_real_data(
        self,
        features: List[np.ndarray],
        coverage_targets: List[float],
        auto_tune: bool = False,
    ) -> Dict[str, Any]:
        result = self._coverage_predictor.train_real(features, coverage_targets, auto_tune=auto_tune)
        self._model_version += 1
        self._changelog.append(f"v{self._model_version}: trained on {len(features)} real samples (auto_tune={auto_tune})")
        logger.info("Real-data training: v%d, %d samples", self._model_version, len(features))
        return {
            "model_version": self._model_version,
            "samples": len(features),
            "models": list(self._coverage_predictor._models.keys()),
            "best_score": self._coverage_predictor._best_score,
        }

    def auto_tune_hyperparams(self, specs: List[DesignSpec]) -> Dict[str, Any]:
        if not HAS_OPTUNA or not HAS_ADVANCED:
            return {"error": "optuna not available"}
        if not specs:
            return {"error": "no specs provided"}

        self._extractor = RichSpecFeatureExtractor()

        def objective(trial):
            n_estimators = trial.suggest_int("n_estimators", 50, 300)
            max_depth = trial.suggest_int("max_depth", 3, 15)
            min_samples_leaf = trial.suggest_int("min_samples_leaf", 2, 8)
            similarity_threshold = trial.suggest_float("similarity_threshold", 0.3, 0.9)
            top_k = trial.suggest_int("top_k", 2, 7)
            quality_threshold = trial.suggest_float("quality_threshold", 0.4, 0.8)

            from src.models.ml_utils import HybridVectorizer
            local_vectorizer = HybridVectorizer()
            texts = []
            for spec in specs:
                fv = self._extractor.extract(spec)
                texts.append(fv.to_text_repr())
            if texts:
                local_vectorizer.fit(texts)
            score = 0.0
            for spec in specs:
                fv = self._extractor.extract(spec)
                if self._index and len(self._index) > 0:
                    results = self._index.search(fv, top_k=top_k, min_similarity=similarity_threshold)
                    score += len(results) / max(1, top_k) * 0.3
            return score / max(1, len(specs))

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(objective, n_trials=15, timeout=60)
        best = study.best_params
        self._quality_threshold = best.get("quality_threshold", self._quality_threshold)
        self._changelog.append(f"v{self._model_version}: auto-tuned params {best}")
        logger.info("Auto-tune complete: %s (score=%.4f)", best, study.best_value)
        return {"best_params": best, "best_score": study.best_value, "trials": len(study.trials)}

    def predict(
        self,
        spec: DesignSpec,
        cfg: PipelineConfig,
        extra_seqs: Optional[List[str]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, str]:
        if not HAS_ADVANCED:
            return self._template_model.predict(spec, cfg)

        rid = request_id or f"gen_{int(time.time() * 1000)}_{id(spec)}"
        def _log(msg: str, *args: Any) -> None:
            logger.info("[%s] %s", rid, msg % args if args else msg)
        _log("Starting prediction for %s", spec.design_name)

        spec_dict = spec.model_dump() if hasattr(spec, 'model_dump') else dict(spec)
        _validate_spec_dict(spec_dict)
        design_name = spec.design_name
        protocol = spec_dict.get("protocol", "unknown")

        # Cache check
        if self._cache:
            cached = self._cache.get(spec_dict, protocol)
            if cached is not None:
                _log("Cache hit for %s@%s", design_name, protocol)
                return cached

        # Build validator
        self._code_validator = AdvancedCodeValidator(spec_dict)
        available_sources = self._get_available_sources()

        _log("Available sources: %s", available_sources)

        start_time = time.time()

        # Ensemble: run top-K strategies concurrently
        selected = self._select_generation_strategy(spec_dict, protocol, available_sources)
        strategies_to_run = self._get_strategy_plan(selected, available_sources)
        _log("Selected strategy=%s, plan=%s", selected.value, strategies_to_run)

        results: List[GenerationResult] = []
        with ThreadPoolExecutor(max_workers=min(self._max_concurrent, len(strategies_to_run))) as executor:
            future_map = {
                executor.submit(self._generate_with_strategy, s, spec, spec_dict, cfg, design_name, protocol): s
                for s in strategies_to_run
            }
            for future in as_completed(future_map):
                stra = future_map[future]
                try:
                    result = future.result(timeout=120)
                    result.strategy_used = stra
                    results.append(result)
                except Exception as e:
                    logger.warning("Strategy %s failed: %s", stra, e)
                    results.append(GenerationResult(
                        source=GenerationSource.TEMPLATE,
                        errors=[f"Strategy {stra} failed: {e}"],
                        strategy_used=stra,
                    ))

        latency_ms = (time.time() - start_time) * 1000

        # Quality gate: pick best result
        final_result = self._apply_quality_gate(results, spec, cfg, spec_dict, design_name, protocol)
        final_result.latency_ms = latency_ms

        # Record metrics
        self._record_learning(final_result, spec_dict, design_name, protocol, selected)
        self._metrics.record({
            "strategy": final_result.strategy_used,
            "score": final_result.score,
            "latency_ms": latency_ms,
            "passed": not final_result.errors,
            "design": design_name,
            "protocol": protocol,
        })

        # Coverage prediction (lazy-trained by CoveragePredictor on first call)
        try:
            self.last_coverage_prediction = self._coverage_predictor.predict_coverage(spec, final_result.files)
            if self.last_coverage_prediction:
                _log("Coverage prediction: %.1f%% expected", self.last_coverage_prediction.get("coverage", {}).get("expected", 0))
        except Exception as e:
            logger.warning("[%s] Coverage prediction failed: %s", rid, e)
            self.last_coverage_prediction = None

        # Store last result for learn() / generate() introspect
        self._last_generation_result = final_result
        self._last_spec_dict = spec_dict
        self._last_design_name = design_name
        self._last_protocol = protocol
        self._last_selected_source = selected
        self._last_spec = spec

        # Update cache
        if self._cache and final_result.files and not final_result.errors:
            self._cache.set(spec_dict, protocol, final_result.files)

        return final_result.files

    @staticmethod
    def _coerce_spec_dict(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce raw YAML dict types to what DesignSpec Pydantic model expects."""
        sd = dict(spec_dict)
        # Registers: address must be hex string, bits must be string
        registers = sd.get("registers", [])
        if registers:
            coerced = []
            for r in registers:
                r = dict(r)
                addr = r.get("address")
                if addr is not None:
                    r["address"] = f"0x{int(addr):x}" if isinstance(addr, int) else str(addr)
                fields = r.get("fields", [])
                if fields:
                    cf = []
                    for f in fields:
                        f = dict(f)
                        b = f.get("bits")
                        if b is not None:
                            f["bits"] = str(b)
                        cf.append(f)
                    r["fields"] = cf
                coerced.append(r)
            sd["registers"] = coerced
        return sd

    def generate(
        self,
        spec_dict: Dict[str, Any],
        cfg: Optional[PipelineConfig] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Public API: generate from raw spec dict (test-compatible interface).

        Returns a rich result dict with ``passed``, ``generated_files``,
        ``source``, ``strategy``, and ``validation_results``.

        Parameters
        ----------
        spec_dict : Dict[str, Any]
            Specification dictionary with at minimum ``design_name`` and ``protocol``.
        cfg : Optional[PipelineConfig]
            Generation pipeline configuration. Auto-created from stored config if None.
        request_id : Optional[str]
            Correlation ID for request tracing across logs.
        """
        rid = request_id or f"gen_{int(time.time() * 1000)}_{id(spec_dict)}"
        try:
            _validate_spec_dict(spec_dict)
        except (TypeError, ValueError) as e:
            logger.error("[%s] Input validation failed: %s", rid, e)
            return {"passed": False, "generated_files": {}, "source": "error", "strategy": "error", "request_id": rid}
        try:
            spec = DesignSpec(**self._coerce_spec_dict(spec_dict))
        except Exception as e:
            logger.error("[%s] Failed to build DesignSpec from dict: %s", rid, e)
            return {"passed": False, "generated_files": {}, "source": "error", "strategy": "error", "request_id": rid}

        # Auto-train template model if not yet trained
        if not self._template_model._is_trained:
            self._template_model.train([spec])

        if cfg is None:
            cfg = getattr(self, '_user_cfg', None)
        if cfg is None:
            from src.config import GenerationConfig, MLConfig
            strategy_name = self._exploration_strategy.value if hasattr(self._exploration_strategy, 'value') else "ucb"
            rev = {"epsilon_greedy": "epsilon_greedy", "softmax": "softmax", "ucb": "ucb",
                   "thompson_sampling": "thompson", "sac": "sac"}
            strategy_name = rev.get(strategy_name, "ucb")
            cfg = PipelineConfig(
                generation=GenerationConfig(templates_dir=self._templates_dir),
                ml=MLConfig(
                    enabled=True,
                    model_type="v2",
                    use_llm=self._use_llm,
                    use_semantic_encoder=self._use_semantic_encoder,
                    use_learning=self._use_learning,
                    exploration_strategy=strategy_name,
                    learning_storage_path=self._learning_storage_path,
                ),
            )

        files = self.predict(spec, cfg, request_id=rid)

        # Build result dict from stored generation result
        gen = getattr(self, '_last_generation_result', None)
        passed = bool(files) and (gen is None or not gen.errors)

        result = {
            "passed": passed,
            "generated_files": files,
            "source": gen.source.value if gen else "template",
            "strategy": gen.strategy_used if gen else "template",
            "request_id": rid,
        }

        # Attach validation results if available
        if gen and gen.validation_report:
            val_details = {}
            for f in gen.validation_report.files:
                checks = [
                    {"check_name": i.message.split(":")[0] if ":" in i.message else "syntax",
                     "passed": i.severity.value != "error",
                     "message": i.message}
                    for i in (f.issues or [])
                ]
                val_details[f.filename] = {
                    "passed": f.passed,
                    "score": f.score,
                    "error_count": f.error_count,
                    "checks": checks,
                }
            result["validation_results"] = val_details

        self._last_generation_result_dict = result
        return result

    def learn(self, result: Dict[str, Any], reward: float) -> None:
        """Feed back a generation result for online learning."""
        gen = getattr(self, '_last_generation_result', None)
        if gen is None:
            logger.warning("No last generation result to learn from")
            return

        spec_dict = getattr(self, '_last_spec_dict', {})
        design_name = getattr(self, '_last_design_name', "unknown")
        protocol = getattr(self, '_last_protocol', "unknown")
        selected_source = getattr(self, '_last_selected_source', GenerationSource.TEMPLATE)

        # Override auto-computed reward with user-provided one
        if not self._use_learning:
            return

        score = gen.score
        cov_bonus = 0.0
        if self.last_coverage_prediction:
            cov_pct = self.last_coverage_prediction.get("coverage", {}).get("expected", 50)
            cov_bonus = 0.3 if cov_pct >= 80 else (0.1 if cov_pct >= 60 else (-0.2 if cov_pct < 40 else 0.0))

        adjusted_reward = max(-1.0, min(1.0, reward + cov_bonus))

        used_source = gen.source.value if gen.source != selected_source else selected_source.value

        if gen.validation_report:
            for file_result in gen.validation_report.files:
                if self._rl_learner:
                    self._rl_learner.update(
                        protocol=protocol, file_type=file_result.file_type,
                        generation_source=used_source,
                        reward=adjusted_reward if file_result.passed else -0.3,
                        spec_dict=spec_dict,
                        metadata={"design_name": design_name, "score": file_result.score,
                                  "error_count": file_result.error_count},
                    )
                if self._pattern_learner:
                    if file_result.passed and file_result.score >= 0.7:
                        self._pattern_learner.record_success(
                            file_type=file_result.file_type, protocol=protocol, score=file_result.score)
                    else:
                        for issue in file_result.issues:
                            if issue.severity.value == "error":
                                self._pattern_learner.record_error(
                                    error_msg=issue.message, file_type=file_result.file_type,
                                    line_num=issue.line_number)

        self._generation_history.append({
            "timestamp": datetime.now().isoformat(),
            "design_name": design_name, "protocol": protocol,
            "selected_source": selected_source.value,
            "actual_source": gen.source.value,
            "strategy_used": gen.strategy_used, "score": score,
            "passed": result.get("passed", False), "reward": adjusted_reward,
        })

        if self._rl_learner and len(self._generation_history) % 10 == 0:
            self._rl_learner.replay_experiences(batch_size=32)

    def save_learning_state(self, path: str) -> None:
        """Public: persist learning state to disk."""
        old_path = self._learning_storage_path
        self._learning_storage_path = path
        self._save_learning_state()
        self._learning_storage_path = old_path

    def load_learning_state(self, path: str) -> None:
        """Public: restore learning state from disk."""
        old_path = self._learning_storage_path
        self._learning_storage_path = path
        self._load_learning_state()
        self._learning_storage_path = old_path

    def _get_strategy_plan(self, primary: GenerationSource, available: List[str]) -> List[str]:
        all_strategies = ["template"]
        if "retrieval" in available:
            all_strategies.append("retrieval")
        if self._use_llm and "llm" in available:
            all_strategies.append("llm")
        ordered = [primary.value] if primary.value != "ensemble" else []
        for s in ["retrieval", "llm", "template"]:
            if s not in ordered and s in all_strategies:
                ordered.append(s)
        return ordered[:self._max_concurrent]

    def _apply_quality_gate(
        self,
        results: List[GenerationResult],
        spec: DesignSpec,
        config: PipelineConfig,
        spec_dict: Dict[str, Any],
        design_name: str,
        protocol: str,
    ) -> GenerationResult:
        if not results:
            return self._generate_by_template(spec, config, design_name, protocol)

        valid = [r for r in results if r.files and not r.errors and r.score >= self._quality_threshold]

        if valid:
            valid.sort(key=lambda r: r.score, reverse=True)
            best = valid[0]
            if len(valid) > 1:
                best.warnings.append(f"Ensemble: picked best of {len(valid)} valid results (scores: {[f'{r.score:.2f}' for r in valid[:3]]})")
            return best

        # No valid result — fallback to template
        template_result = self._generate_by_template(spec, config, design_name, protocol)
        template_result.warnings.append(f"Quality gate: all {len(results)} strategies failed quality threshold ({self._quality_threshold}), fell back to template")
        template_result.strategy_used = "template_fallback"
        return template_result

    def _get_available_sources(self) -> List[str]:
        sources = ["template"]
        if self._index and len(self._index) > 0:
            sources.append("retrieval")
        if self._use_llm:
            sources.append("llm")
        return sources

    @staticmethod
    def _ensure_content_dict(files: Dict[str, str]) -> Dict[str, str]:
        """Convert {filename: path} to {filename: content} if needed."""
        result: Dict[str, str] = {}
        for fname, val in files.items():
            path = Path(val)
            if path.is_file():
                result[fname] = path.read_text(encoding="utf-8")
            else:
                result[fname] = val
        return result

    def _select_generation_strategy(
        self,
        spec_dict: Dict[str, Any],
        protocol: str,
        available_sources: List[str],
    ) -> GenerationSource:
        if len(available_sources) == 1:
            return GenerationSource(available_sources[0])

        if not self._use_learning or not self._rl_learner:
            if "retrieval" in available_sources and self._index and len(self._index) > 0:
                return GenerationSource.RETRIEVAL
            return GenerationSource.TEMPLATE

        file_types = ["testbench", "interface", "test", "sequence", "driver", "monitor"]
        source_scores: Dict[str, float] = defaultdict(float)
        for file_type in file_types:
            source, value = self._rl_learner.select_best_action(
                protocol=protocol, file_type=file_type, available_sources=available_sources, spec_dict=spec_dict,
            )
            source_scores[source] += value

        try:
            feat = SpecFeatures.from_spec(spec_dict)
            coverage_hint = self._coverage_predictor.predict_coverage(spec_dict)
            cov_pct = coverage_hint.get("coverage", {}).get("expected", 50)
            if cov_pct < 60 and "llm" in source_scores:
                source_scores["llm"] += 2.0
            if feat.register_count > 8 and "retrieval" in source_scores:
                source_scores["retrieval"] += 1.0
        except Exception as e:
            logger.debug("Coverage hint in strategy selection failed: %s", e)

        if not source_scores:
            return GenerationSource.TEMPLATE
        best_source = max(source_scores.keys(), key=lambda s: source_scores[s])
        return GenerationSource(best_source)

    def _generate_with_strategy(
        self,
        strategy: str,
        spec: DesignSpec,
        spec_dict: Dict[str, Any],
        config: PipelineConfig,
        design_name: str,
        protocol: str,
    ) -> GenerationResult:
        def _exec() -> GenerationResult:
            if strategy == "retrieval":
                return self._generate_by_retrieval(spec, spec_dict, config, design_name, protocol)
            elif strategy == "llm" and self._use_llm:
                return self._generate_by_llm(spec, spec_dict, config, design_name, protocol)
            else:
                return self._generate_by_template(spec, config, design_name, protocol)
        try:
            return _retry_with_backoff(_exec, max_retries=2, base_delay=0.25)
        except Exception as e:
            logger.error("Strategy %s failed after retries: %s", strategy, e)
            return GenerationResult(
                source=GenerationSource.TEMPLATE,
                errors=[f"Strategy {strategy} failed after retries: {e}"],
                strategy_used=strategy,
            )

    def _generate_by_retrieval(
        self, spec: DesignSpec, spec_dict: Dict[str, Any], config: PipelineConfig,
        design_name: str, protocol: str,
    ) -> GenerationResult:
        if not self._index or not self._extractor or not self._adapter:
            return GenerationResult(source=GenerationSource.TEMPLATE)
        features = self._extractor.extract(spec)
        search_results = self._index.search(features, top_k=5)
        if not search_results:
            return GenerationResult(source=GenerationSource.TEMPLATE)
        best_result = search_results[0]
        best_spec = best_result.spec_dict
        retrieval_info = RetrievalInfo(
            used_similarity=True, similar_specs=len(search_results),
            best_score=best_result.similarity, best_spec_name=best_result.design_name,
            retrieval_strategy="similarity_search",
        )
        if best_result.generated_files:
            source_files_content = self._ensure_content_dict(best_result.generated_files)
            adaptation = self._adapter.adapt(
                source_spec=best_spec, target_spec=spec_dict, source_files=source_files_content,
            )
            retrieval_info.adaptation_score = adaptation.overall_score
            if adaptation.is_safe() and adaptation.overall_score >= 0.7:
                output_dir = Path(config.generation.output_dir) / f"{design_name}_tb"
                files = _content_dict_to_path_dict(adaptation.adapted_files, output_dir)
                if self._code_validator:
                    report = self._code_validator.validate_files(adaptation.adapted_files, design_name)
                    retrieval_info.pre_validation_score = report.avg_score
                    if report.overall_passed or not self._strict_validation:
                        return GenerationResult(
                            files=files, source=GenerationSource.RETRIEVAL,
                            retrieval_info=retrieval_info, validation_report=report,
                            score=report.avg_score,
                        )
                else:
                    return GenerationResult(files=files, source=GenerationSource.RETRIEVAL, retrieval_info=retrieval_info, score=0.7)
            if adaptation.overall_score < 0.7:
                logger.warning("Adaptation score too low (%.2f)", adaptation.overall_score)
        if len(search_results) > 1:
            for alt_result in search_results[1:3]:
                if alt_result.generated_files and alt_result.similarity >= 0.5:
                    alt_source_files = self._ensure_content_dict(alt_result.generated_files)
                    adaptation = self._adapter.adapt(
                        source_spec=alt_result.spec_dict, target_spec=spec_dict,
                        source_files=alt_source_files,
                    )
                    if adaptation.is_safe() and adaptation.overall_score >= 0.7:
                        output_dir = Path(config.generation.output_dir) / f"{design_name}_tb"
                        files = _content_dict_to_path_dict(adaptation.adapted_files, output_dir)
                        if self._code_validator:
                            report = self._code_validator.validate_files(adaptation.adapted_files, design_name)
                            retrieval_info.best_spec_name = alt_result.design_name
                            retrieval_info.best_score = alt_result.similarity
                            retrieval_info.adaptation_score = adaptation.overall_score
                            retrieval_info.pre_validation_score = report.avg_score
                            return GenerationResult(files=files, source=GenerationSource.RETRIEVAL, retrieval_info=retrieval_info, validation_report=report, score=report.avg_score)
        return GenerationResult(
            source=GenerationSource.RETRIEVAL, retrieval_info=retrieval_info,
            errors=["Retrieval generation did not pass validation thresholds"],
        )

    def _generate_by_llm(
        self, spec: DesignSpec, spec_dict: Dict[str, Any], config: PipelineConfig,
        design_name: str, protocol: str = "uart",
    ) -> GenerationResult:
        base_result = self._generate_by_template(spec, config, design_name, protocol)
        if not base_result.files:
            return base_result
        try:
            cov_pred = self._coverage_predictor.predict_coverage(spec, base_result.files)
            gaps = cov_pred.get("coverage", {}).get("gaps", [])
            recommended = cov_pred.get("recommended_sequences", [])
        except Exception as e:
            gaps = []
            recommended = []
        if gaps:
            output_dir = Path(config.generation.output_dir) / f"{design_name}_tb"
            extra_seqs = self._generate_targeted_sequences(spec_dict, recommended, design_name, output_dir)
            base_result.files.update(extra_seqs)
        base_result.source = GenerationSource.LLM
        base_result.warnings.append(f"Coverage-driven: predicted {len(gaps)} gap(s), added {len(recommended)} targeted sequence(s)")
        return base_result

    def _generate_targeted_sequences(
        self, spec_dict: Dict[str, Any], recommended: List[str],
        design_name: str, output_dir: Optional[Path] = None,
    ) -> Dict[str, str]:
        seqs: Dict[str, str] = {}
        interfaces = spec_dict.get("interfaces", [])
        registers = spec_dict.get("registers", [])
        if output_dir:
            seq_dir = output_dir / "sequences"
            seq_dir.mkdir(parents=True, exist_ok=True)
            for seq_name in recommended:
                content = self._build_targeted_sequence(seq_name, design_name, interfaces, registers)
                out_path = seq_dir / f"{seq_name}.sv"
                out_path.write_text(content, encoding="utf-8")
                seqs[f"sequences/{seq_name}.sv"] = str(out_path)
            lib_content = self._build_seq_lib(design_name, recommended)
            lib_path = seq_dir / f"{design_name}_targeted_seq_lib.sv"
            lib_path.write_text(lib_content, encoding="utf-8")
            seqs[f"sequences/{design_name}_targeted_seq_lib.sv"] = str(lib_path)
        else:
            for seq_name in recommended:
                content = self._build_targeted_sequence(seq_name, design_name, interfaces, registers)
                seqs[f"sequences/{seq_name}.sv"] = content
            seqs[f"sequences/{design_name}_targeted_seq_lib.sv"] = self._build_seq_lib(design_name, recommended)
        return seqs

    def _build_targeted_sequence(
        self, seq_name: str, design_name: str,
        interfaces: List[Dict[str, Any]], registers: List[Dict[str, Any]],
    ) -> str:
        lines = [
            f"// {seq_name} — coverage-driven sequence",
            f"// Target: {design_name} ({len(interfaces)} interfaces, {len(registers)} registers)",
            "",
            "`ifndef GUARD_{0}_SV".format(seq_name.upper()),
            "`define GUARD_{0}_SV".format(seq_name.upper()),
            "",
            f'class {seq_name} extends uvm_sequence #(uvm_sequence_item);',
            f"    `uvm_object_utils({seq_name})",
            f"    function new(string name = \"{seq_name}\");",
            "        super.new(name);",
            "    endfunction",
            "    extern virtual task body();",
            "endclass",
            "",
        ]
        body_lines = [f"task {seq_name}::body();"]
        if "coverage" in seq_name:
            body_lines.append("    `uvm_info(get_type_name(), \"Starting coverage sequence\", UVM_MEDIUM)")
            for i, iface in enumerate(interfaces[:3]):
                body_lines.append(f"    // Coverage for {iface.get('name', f'iface_{i}')}")
            body_lines.extend([
                "    repeat (50) begin",
                "        req = uvm_sequence_item::type_id::create(\"req\");",
                "        start_item(req);",
                "        assert(req.randomize());",
                "        finish_item(req);",
                "    end",
            ])
        elif "random_regs" in seq_name:
            body_lines.append("    `uvm_info(get_type_name(), \"Starting random register sequence\", UVM_MEDIUM)")
            for r in registers[:8]:
                body_lines.append(f"    // Register: {r.get('name', 'reg')} @ 0x{r.get('address', 0):04x}")
            body_lines.extend(["    repeat (100) begin", "        #10ns;", "    end"])
        elif "loopback" in seq_name:
            body_lines.append("    `uvm_info(get_type_name(), \"Starting loopback validation\", UVM_MEDIUM)")
            body_lines.extend(["    repeat (20) begin", "        #5ns;", "    end"])
        elif "interrupt" in seq_name:
            body_lines.append("    `uvm_info(get_type_name(), \"Starting interrupt test sequence\", UVM_MEDIUM)")
            body_lines.extend([
                "    fork",
                "        begin",
                "            #1ms;",
                "            `uvm_error(get_type_name(), \"Interrupt timeout\")",
                "        end",
                "        begin",
                "        end",
                "    join_any",
            ])
        else:
            body_lines.append(f"    // Generic sequence: {seq_name}")
            body_lines.append("    #10ns;")
        body_lines.append("endtask\n")
        return "\n".join(lines) + "\n".join(body_lines)

    def _build_seq_lib(self, design_name: str, seq_names: List[str]) -> str:
        lines = [f"// {design_name}_targeted_seq_lib — coverage-driven library", ""]
        for name in seq_names:
            lines.append(f'`include "{name}.sv"')
        lines.append("")
        return "\n".join(lines)

    def _generate_by_template(
        self, spec: DesignSpec, config: PipelineConfig, design_name: str, protocol: str,
    ) -> GenerationResult:
        files = self._template_model.predict(spec, config)
        score = 0.7
        report = None
        if self._code_validator:
            report = self._code_validator.validate_files(files, design_name)
            score = report.avg_score
        return GenerationResult(files=files, source=GenerationSource.TEMPLATE, validation_report=report, score=score)

    def _record_learning(
        self, final_result: GenerationResult, spec_dict: Dict[str, Any],
        design_name: str, protocol: str, selected_source: GenerationSource,
    ) -> None:
        if not self._use_learning:
            return
        score = final_result.score
        passed = final_result.validation_report.overall_passed if final_result.validation_report else (score >= 0.7)

        cov_bonus = 0.0
        if self.last_coverage_prediction:
            cov_pct = self.last_coverage_prediction.get("coverage", {}).get("expected", 50)
            cov_bonus = 0.3 if cov_pct >= 80 else (0.1 if cov_pct >= 60 else (-0.2 if cov_pct < 40 else 0.0))

        latency_bonus = 0.0
        if final_result.latency_ms > 0:
            if final_result.latency_ms < 1000:
                latency_bonus = 0.05
            elif final_result.latency_ms > 10000:
                latency_bonus = -0.1

        reward = (1.0 if passed else -0.5) + cov_bonus + latency_bonus
        reward = max(-1.0, min(1.0, reward))

        used_source = final_result.source.value if final_result.source != selected_source else selected_source.value

        file_type_rewards = {}
        if final_result.validation_report:
            for file_result in final_result.validation_report.files:
                file_type_rewards[file_result.file_type] = 1.0 if file_result.passed else -0.3
                if self._rl_learner:
                    self._rl_learner.update(
                        protocol=protocol, file_type=file_result.file_type,
                        generation_source=used_source, reward=file_type_rewards[file_result.file_type],
                        spec_dict=spec_dict, metadata={"design_name": design_name, "score": file_result.score, "error_count": file_result.error_count},
                    )
                if self._pattern_learner:
                    if file_result.passed and file_result.score >= 0.7:
                        self._pattern_learner.record_success(file_type=file_result.file_type, protocol=protocol, score=file_result.score)
                    else:
                        for issue in file_result.issues:
                            if issue.severity.value == "error":
                                self._pattern_learner.record_error(error_msg=issue.message, file_type=file_result.file_type, line_num=issue.line_number)

        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(), "design_name": design_name, "protocol": protocol,
            "selected_source": selected_source.value, "actual_source": final_result.source.value,
            "strategy_used": final_result.strategy_used, "score": score, "latency_ms": final_result.latency_ms,
            "passed": passed, "reward": reward,
            "error_count": final_result.validation_report.total_errors if final_result.validation_report else 0,
        }
        self._generation_history.append(history_entry)
        if len(self._generation_history) > 2000:
            self._generation_history = self._generation_history[-2000:]

        if self._enable_adaptive_weights and final_result.validation_report:
            strategy_perf = self._metrics.get_strategy_performance()
            self._strategy_weights.adapt(strategy_perf)

        if self._rl_learner and len(self._generation_history) % 10 == 0:
            self._rl_learner.replay_experiences(batch_size=128)
        if self._learning_storage_path:
            self._save_learning_state()

    def _save_learning_state(self) -> None:
        if not self._learning_storage_path:
            return
        try:
            os.makedirs(os.path.dirname(self._learning_storage_path), exist_ok=True)
            state = {
                "version": self._model_version,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "generation_history": self._generation_history[-500:],
                "metrics": self._metrics.get_summary(),
                "strategy_weights": self._strategy_weights.to_dict(),
                "changelog": self._changelog[-100:],
                "enable_adaptive_weights": self._enable_adaptive_weights,
                "enable_auto_tune": self._enable_auto_tune,
                "quality_threshold": self._quality_threshold,
                "strict_validation": self._strict_validation,
            }
            if self._rl_learner:
                state["rl_learner"] = self._rl_learner.to_dict()
            if self._pattern_learner:
                state["pattern_learner"] = self._pattern_learner.to_dict()
            with open(self._learning_storage_path, "w") as f:
                json.dump(state, f, indent=2)
            logger.info("Learning state saved (v%d)", self._model_version)
        except Exception as e:
            logger.warning("Could not save learning state: %s", e)

    def _load_learning_state(self) -> None:
        if not self._learning_storage_path or not os.path.exists(self._learning_storage_path):
            return
        try:
            with open(self._learning_storage_path, "r") as f:
                state = json.load(f)
            self._generation_history = state.get("generation_history", [])
            self._model_version = state.get("version", 1)
            self._changelog = state.get("changelog", [])
            self._enable_adaptive_weights = state.get("enable_adaptive_weights", self._enable_adaptive_weights)
            self._enable_auto_tune = state.get("enable_auto_tune", self._enable_auto_tune)
            self._quality_threshold = state.get("quality_threshold", self._quality_threshold)
            self._strict_validation = state.get("strict_validation", self._strict_validation)
            weights = state.get("strategy_weights", {})
            if weights:
                self._strategy_weights = StrategyWeights(
                    retrieval_weight=weights.get("retrieval", 0.4),
                    llm_weight=weights.get("llm", 0.3),
                    template_weight=weights.get("template", 0.3),
                    ensemble_weight=weights.get("ensemble", 0.2),
                )
            if "rl_learner" in state and self._rl_learner:
                self._rl_learner = AdvancedReinforcementLearner.from_dict(state["rl_learner"])
            if "pattern_learner" in state and self._pattern_learner:
                self._pattern_learner = AdvancedPatternLearner.from_dict(state["pattern_learner"])
            logger.info("Learning state loaded (v%d, %d history entries, %d changelog entries)",
                       self._model_version, len(self._generation_history), len(self._changelog))
        except Exception as e:
            logger.warning("Could not load learning state: %s", e)

    def get_learning_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "total_generations": len(self._generation_history),
            "model_version": self._model_version,
            "metrics": self._metrics.get_summary(),
            "strategy_weights": self._strategy_weights.to_dict(),
            "adaptive_weights_enabled": self._enable_adaptive_weights,
            "auto_tune_enabled": self._enable_auto_tune,
            "changelog": self._changelog[-20:],
            "coverage_predictor_version": self._coverage_predictor._version,
        }
        if self._generation_history:
            recent = self._generation_history[-50:]
            passed = sum(1 for h in recent if h.get("passed", False))
            avg_score = sum(h.get("score", 0) for h in recent) / len(recent)
            avg_latency = sum(h.get("latency_ms", 0) for h in recent) / len(recent)
            stats["recent_performance"] = {
                "window_size": len(recent), "pass_rate": passed / len(recent),
                "avg_score": avg_score, "avg_latency_ms": avg_latency,
            }
            sources = [h.get("actual_source", "unknown") for h in recent]
            stats["source_distribution"] = dict(Counter(sources))
        if self._rl_learner:
            stats["rl_learner"] = self._rl_learner.get_performance_stats()
        if self._pattern_learner:
            stats["pattern_learner"] = self._pattern_learner.get_suggestions(file_type="any", protocol="any")
        cp_summary = self._coverage_predictor.get_model_summary()
        stats["coverage_predictor"] = {
            "version": cp_summary["version"],
            "models": cp_summary["models"],
            "training_data_size": cp_summary["training_data_size"],
            "best_score": cp_summary["best_score"],
            "conformal_calibrated": cp_summary["conformal_calibrated"],
        }
        return stats

    def get_health_status(self) -> Dict[str, Any]:
        components = {
            "template_model": self._template_model is not None,
            "similarity_index": self._index is not None and len(self._index) > 0,
            "feature_extractor": self._extractor is not None,
            "spec_adapter": self._adapter is not None,
            "code_validator": self._code_validator is not None,
            "rl_learner": self._rl_learner is not None,
            "pattern_learner": self._pattern_learner is not None,
            "coverage_predictor": self._coverage_predictor is not None,
        }
        all_ok = all(components.values())
        cov_pred_models = list(self._coverage_predictor._models.keys()) if self._coverage_predictor._models else []
        return {
            "status": "healthy" if all_ok else "degraded",
            "version": self._model_version,
            "components": components,
            "index_size": len(self._index) if self._index else 0,
            "cache_enabled": self._enable_caching,
            "use_learning": self._use_learning,
            "use_llm": self._use_llm,
            "exploration_strategy": self._exploration_strategy.value if self._exploration_strategy else None,
            "total_generations": len(self._generation_history),
            "rl_converged": self._rl_learner.is_converged() if self._rl_learner else None,
            "quality_threshold": self._quality_threshold,
            "max_concurrent_strategies": self._max_concurrent,
            "enable_adaptive_weights": self._enable_adaptive_weights,
            "enable_auto_tune": self._enable_auto_tune,
            "coverage_predictor_models": cov_pred_models,
            "coverage_predictor_version": self._coverage_predictor._version,
            "coverage_predictor_fitted": self._coverage_predictor._fitted,
            "changelog_count": len(self._changelog),
        }

    def invalidate_cache(self, spec: Optional[DesignSpec] = None) -> None:
        if not self._cache:
            return
        if spec:
            spec_dict = spec.model_dump() if hasattr(spec, 'model_dump') else {"design_name": spec.design_name}
            protocol = getattr(spec, "protocol", "unknown")
            self._cache.invalidate(spec_dict, protocol)
        else:
            self._cache.clear()
        logger.info("Cache invalidated")

    def clear_history(self) -> None:
        self._generation_history.clear()
        self._metrics = MetricsTracker()
        logger.info("Generation history cleared")

    @staticmethod
    def _spec_to_dict(spec: DesignSpec) -> Dict[str, Any]:
        return {
            "design_name": spec.design_name,
            "protocol": spec.protocol,
            "clock_reset": {
                "clock": spec.clock_reset.clock,
                "reset": spec.clock_reset.reset,
                "reset_active": spec.clock_reset.reset_active,
            },
            "interfaces": [
                {"name": iface.name, "signals": [{"name": s.name, "direction": s.direction, "width": s.width} for s in iface.signals]}
                for iface in spec.interfaces
            ],
            "registers": [
                {"name": r.name, "address": r.address, "access": r.access, "size": r.size,
                 "reset_value": r.reset_value,
                 "fields": [{"name": f.name, "bits": f.bits, "description": f.description} for f in r.fields]}
                for r in spec.registers
            ],
        }

    def save(self, path: str) -> None:
        full_state = {
            "model_version": self._model_version,
            "name": self.name,
            "class": self.__class__.__name__,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "generation_history": self._generation_history,
            "metrics": self._metrics.get_summary(),
            "strategy_weights": self._strategy_weights.to_dict(),
            "changelog": self._changelog[-200:],
            "enable_adaptive_weights": self._enable_adaptive_weights,
            "enable_auto_tune": self._enable_auto_tune,
            "quality_threshold": self._quality_threshold,
            "strict_validation": self._strict_validation,
        }
        if self._rl_learner:
            full_state["rl_learner"] = self._rl_learner.to_dict()
        if self._pattern_learner:
            full_state["pattern_learner"] = self._pattern_learner.to_dict()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(full_state, f, indent=2)
        logger.info("Saved EnhancedMLGenerationModelV2 v%d to %s", self._model_version, path)

    @classmethod
    def load(cls, path: str, **kwargs: Any) -> EnhancedMLGenerationModelV2:
        model = cls(name="enhanced_ml_model_v2", use_learning=True, **kwargs)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    state = json.load(f)
                model._model_version = state.get("model_version", 1)
                model._generation_history = state.get("generation_history", [])
                model._changelog = state.get("changelog", [])
                model._enable_adaptive_weights = state.get("enable_adaptive_weights", model._enable_adaptive_weights)
                model._enable_auto_tune = state.get("enable_auto_tune", model._enable_auto_tune)
                model._quality_threshold = state.get("quality_threshold", model._quality_threshold)
                model._strict_validation = state.get("strict_validation", model._strict_validation)
                weights = state.get("strategy_weights", {})
                if weights:
                    model._strategy_weights = StrategyWeights(
                        retrieval_weight=weights.get("retrieval", 0.4),
                        llm_weight=weights.get("llm", 0.3),
                        template_weight=weights.get("template", 0.3),
                        ensemble_weight=weights.get("ensemble", 0.2),
                    )
                if "rl_learner" in state and model._rl_learner:
                    model._rl_learner = AdvancedReinforcementLearner.from_dict(state["rl_learner"])
                if "pattern_learner" in state and model._pattern_learner:
                    model._pattern_learner = AdvancedPatternLearner.from_dict(state["pattern_learner"])
                logger.info("Loaded EnhancedMLGenerationModelV2 v%d from %s", model._model_version, path)
            except Exception as e:
                logger.warning("Could not load full state from %s: %s", path, e)
        else:
            logger.warning("Model file not found at %s, using fresh instance", path)
        return model

    @property
    def is_trained(self) -> bool:
        if self._index is not None:
            return len(self._index) > 0
        return False

    @property
    def index(self) -> Optional[SimilarityIndex]:
        return self._index
