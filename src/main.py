# src/main.py — CLI entry point

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.pipeline import TBPipeline


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UVM TB Generator — ML-style pipeline with coverage-driven auto-training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main --spec configs/uart16550-1.5.core
  python -m src.main --spec configs/uart_demo.yaml --auto-train --max-iterations 10
  python -m src.main --spec configs/uart_demo.yaml --simulator icarus
  python -m src.main --spec configs/uart_demo.yaml --pipeline-config configs/base_config.yaml --output-dir my_tbs
  python -m src.main --spec configs/uart_demo.yaml --eval-only
        """,
    )
    parser.add_argument("--spec", required=True, help="Design spec YAML/.core/JSON path")
    parser.add_argument("--pipeline-config", default=None, help="Pipeline config YAML path")
    parser.add_argument("--output-dir", default=None, help="Override output directory")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate (no generation)")
    parser.add_argument("--log-level", default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--auto-train", action="store_true", help="Enable coverage-driven auto-training loop")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max auto-training iterations (default: 5)")
    parser.add_argument("--coverage-target", type=float, default=90.0, help="Coverage target %% (default: 90)")
    parser.add_argument("--simulator", default="stub", choices=["stub", "icarus", "vcs", "questa"],
                        help="Simulator backend (default: stub)")
    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if not Path(args.spec).exists():
        print(f"ERROR: Spec file not found: {args.spec}", file=sys.stderr)
        sys.exit(1)

    pipeline = TBPipeline()

    if args.output_dir:
        pipeline.cfg.generation.output_dir = args.output_dir
    if args.log_level:
        pipeline.cfg.logging.level = args.log_level

    if args.auto_train:
        pipeline.cfg.auto_train.enabled = True
        pipeline.cfg.auto_train.max_iterations = args.max_iterations
        pipeline.cfg.auto_train.coverage_target = args.coverage_target
        pipeline.cfg.auto_train.simulator = args.simulator

    if args.eval_only:
        from src.config import ConfigLoader
        from src.data.validators import SpecValidator
        from src.evaluation.metrics import TBMetrics
        from src.evaluation.reporters import Reporter, Report
        from src.features.extractors import SpecFeatureExtractor

        loader = ConfigLoader()
        spec, _ = loader.load(args.spec)
        validator = SpecValidator()
        vr = validator.validate(spec)
        if not vr:
            print(vr)
            sys.exit(1)
        extractor = SpecFeatureExtractor()
        features = extractor.extract(spec)
        print(f"Features: {features.model_dump_json(indent=2)}")
        metrics = TBMetrics().evaluate_all(spec, list(TemplateModel.TEMPLATE_MAP.keys()))
        report = Report(metrics, spec.design_name, all(v >= 0.7 for v in metrics.values()))
        Reporter().report(report)
        return

    try:
        result = pipeline.run(args.spec, args.pipeline_config)
    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        ev = result["evaluation"]
        print(f"\n{'='*60}")
        print(f"Design:      {result['design_name']}")
        print(f"Status:      {'PASS' if result['passed'] else 'FAIL'}")
        print(f"Simulator:   {result['simulator']}")
        print(f"Versions:    {result.get('all_versions', [])}")
        print(f"Latest ver:  {result['model_version']}")
        print(f"Iterations:  {result['auto_train_iterations']}")
        print(f"--- Metrics ---")
        for k, v in ev.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2%}" if v <= 1.0 else f"  {k}: {v:.1f}")
            else:
                print(f"  {k}: {v}")

        if result.get("coverage_trend"):
            print(f"--- Coverage Trend ---")
            for ver, cov in result["coverage_trend"]:
                bar = "#" * int(cov / 5)
                print(f"  {ver}: {cov:5.1f}% |{bar}")

        if result.get("coverage_analysis"):
            ca = result["coverage_analysis"]
            print(f"--- Coverage Analysis ---")
            print(f"  Bins: {ca['covered_bins']}/{ca['total_bins']} ({ca['coverage_pct']:.1f}%)")
            if ca["gaps"]:
                print(f"  Gaps:")
                for g in ca["gaps"]:
                    print(f"    - {g['bin']} (addr={g['addr']}, dir={g['dir']})")

        if result.get("version_comparison"):
            vc = result["version_comparison"]
            print(f"--- Version Delta ---")
            for k, d in vc.get("metric_deltas", {}).items():
                arrow = "+" if d["delta"] > 0 else ("-" if d["delta"] < 0 else "=")
                print(f"  {k}: {d['from']:.2f} {arrow} {d['to']:.2f} ({d['delta']:+.2f})")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
