from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigLoader, DesignSpec, PipelineConfig
from src.features.extractors import SpecFeatureExtractor, RichSpecFeatureExtractor
from src.models.coverage_predictor import CoveragePredictor, SpecFeatures
from src.models.enhanced_ml_model_v2 import EnhancedMLGenerationModelV2
from src.models.registry import ModelRegistry
from src.models.similarity_index import SimilarityIndex
from src.models.ml_utils import HybridVectorizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("uvmgen.train")


def collect_training_data(
    spec_dir: str,
    label_file: Optional[str] = None,
    max_samples: int = 5000,
) -> tuple[List[np.ndarray], List[float], List[DesignSpec]]:
    features_list: List[np.ndarray] = []
    targets_list: List[float] = []
    specs: List[DesignSpec] = []

    labels: Dict[str, float] = {}
    if label_file and os.path.exists(label_file):
        with open(label_file) as f:
            labels = {k: float(v) for k, v in json.load(f).items()}
        logger.info("Loaded %d labels from %s", len(labels), label_file)

    spec_paths = list(Path(spec_dir).glob("*.yaml")) + list(Path(spec_dir).glob("*.core"))
    logger.info("Found %d spec files in %s", len(spec_paths), spec_dir)

    count = 0
    for spec_path in spec_paths:
        if count >= max_samples:
            break
        try:
            loader = ConfigLoader()
            design_spec, _ = loader.load(str(spec_path))
            specs.append(design_spec)
            feat = SpecFeatures.from_spec(design_spec)
            features_list.append(feat.to_array())

            spec_name = design_spec.design_name
            if spec_name in labels:
                targets_list.append(labels[spec_name])
            else:
                complexity = (
                    feat.interface_count * 1.5
                    + feat.total_signals * 0.8
                    + feat.register_count * 2.0
                    + feat.total_fields * 0.5
                )
                heuristic = min(95.0, 45.0 + complexity * 0.5)
                targets_list.append(heuristic / 100.0)
            count += 1
        except Exception as e:
            logger.warning("Skipping %s: %s", spec_path, e)

    logger.info("Collected %d training samples", len(features_list))
    return features_list, targets_list, specs


def train_coverage_predictor(
    predictor: CoveragePredictor,
    features: List[np.ndarray],
    targets: List[float],
    auto_tune: bool = False,
    save_path: Optional[str] = None,
) -> CoveragePredictor:
    logger.info("Training coverage predictor on %d samples (auto_tune=%s)", len(features), auto_tune)
    predictor.train_real(features, targets, auto_tune=auto_tune)

    if save_path:
        predictor.save(save_path)
        logger.info("Coverage predictor saved to %s", save_path)

    summary = predictor.get_model_summary()
    logger.info("Coverage predictor summary: %s", json.dumps(summary, indent=2))
    return predictor


def train_ensemble_model(
    specs: List[DesignSpec],
    predictor: CoveragePredictor,
    save_path: Optional[str] = None,
    **model_kwargs: Any,
) -> EnhancedMLGenerationModelV2:
    logger.info("Training EnhancedMLGenerationModelV2 on %d specs", len(specs))
    model = EnhancedMLGenerationModelV2(**model_kwargs)
    model.train(specs)
    model._coverage_predictor = predictor

    if save_path:
        model.save(save_path)
        logger.info("Ensemble model saved to %s", save_path)

    logger.info("Model health: %s", json.dumps(model.get_health_status(), indent=2))
    return model


def evaluate_model(
    model: EnhancedMLGenerationModelV2,
    specs: List[DesignSpec],
    registry: ModelRegistry,
    stage: str = "development",
) -> Dict[str, Any]:
    logger.info("Evaluating model on %d specs", len(specs))
    results = []
    for spec in specs[:10]:
        try:
            spec_dict = spec.model_dump() if hasattr(spec, 'model_dump') else {"design_name": spec.design_name, "protocol": spec.protocol}
            result = model.generate(spec_dict)
            results.append({
                "design": spec.design_name,
                "passed": result.get("passed", False),
                "source": result.get("source", "unknown"),
                "strategy": result.get("strategy", "unknown"),
            })
        except Exception as e:
            logger.warning("Evaluation failed for %s: %s", spec.design_name, e)

    passed_count = sum(1 for r in results if r["passed"])
    metrics = {
        "pass_rate": passed_count / max(1, len(results)),
        "total_evaluated": len(results),
        "passed": passed_count,
    }

    version = registry.register(
        model,
        metrics=metrics,
        spec_name="evaluation_batch",
        tags={"type": "evaluation", "stage": stage},
        stage=stage,
    )
    logger.info("Registered version %s with metrics: %s", version, metrics)
    return {"version": version, "metrics": metrics, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Production model training for UVM Verification")
    parser.add_argument("--spec-dir", default="configs", help="Directory with spec YAML/core files")
    parser.add_argument("--labels", default=None, help="JSON file with design_name -> coverage labels")
    parser.add_argument("--auto-tune", action="store_true", help="Enable hyperparameter auto-tuning")
    parser.add_argument("--save-predictor", default="model_registry/coverage_predictor.pkl", help="Save path for coverage predictor")
    parser.add_argument("--save-model", default="model_registry/ensemble_model.json", help="Save path for ensemble model")
    parser.add_argument("--registry-dir", default="model_registry", help="Model registry directory")
    parser.add_argument("--stage", default="development", choices=["development", "staging", "production"], help="Deployment stage")
    parser.add_argument("--max-samples", type=int, default=5000, help="Maximum training samples")
    parser.add_argument("--use-neural-rl", action="store_true", help="Enable neural Q-network in RL learner")
    parser.add_argument("--use-cosine-decay", action="store_true", default=True, help="Use cosine LR decay")
    parser.add_argument("--exploration-strategy", default="sac", choices=["epsilon_greedy", "softmax", "ucb", "thompson", "sac"], help="RL exploration strategy")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Production Model Training Pipeline")
    logger.info("=" * 60)
    logger.info("Args: %s", vars(args))

    registry = ModelRegistry(registry_dir=args.registry_dir)

    logger.info("Step 1: Collecting training data from %s", args.spec_dir)
    features, targets, specs = collect_training_data(
        args.spec_dir, label_file=args.labels, max_samples=args.max_samples,
    )

    logger.info("Step 2: Training coverage predictor")
    predictor = CoveragePredictor(random_state=42)
    predictor = train_coverage_predictor(
        predictor, features, targets,
        auto_tune=args.auto_tune,
        save_path=args.save_predictor,
    )

    logger.info("Step 3: Training ensemble generation model")
    model = train_ensemble_model(
        specs, predictor,
        save_path=args.save_model,
        use_learning=True,
        exploration_strategy=args.exploration_strategy,
        use_neural_rl=args.use_neural_rl,
        use_cosine_decay=args.use_cosine_decay,
        enable_adaptive_weights=True,
        enable_auto_tune=args.auto_tune,
    )

    logger.info("Step 4: Evaluating and registering model")
    eval_result = evaluate_model(model, specs, registry, stage=args.stage)

    if args.stage == "production":
        logger.info("Model promoted to PRODUCTION!")
    elif args.stage == "staging":
        logger.info("Model deployed to STAGING for validation")

    summary = {
        "training_samples": len(features),
        "model_version": model._model_version,
        "registry_version": eval_result["version"],
        "eval_metrics": eval_result["metrics"],
        "predictor_summary": predictor.get_model_summary(),
        "model_health": model.get_health_status(),
        "stage": args.stage,
        "exploration_strategy": args.exploration_strategy,
        "use_neural_rl": args.use_neural_rl,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    summary_path = os.path.join(args.registry_dir, "training_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Training summary saved to %s", summary_path)
    logger.info("Summary: %s", json.dumps(summary, indent=2))
    logger.info("=" * 60)
    logger.info("Training complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
