# src/evaluation/reporters.py — Generate evaluation reports

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class Report:
    def __init__(self, metrics: Dict[str, float], spec_name: str, passed: bool):
        self.metrics = metrics
        self.spec_name = spec_name
        self.passed = passed
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_name": self.spec_name,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "passed": self.passed,
        }

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] Evaluation for '{self.spec_name}'"]
        for k, v in self.metrics.items():
            lines.append(f"  {k}: {v:.2%}")
        return "\n".join(lines)


class Reporter:
    """Generates evaluation reports in multiple formats."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)

    def report(self, report: Report, formats: Optional[List[str]] = None) -> Dict[str, str]:
        formats = formats or ["console", "json"]
        outputs = {}
        if "console" in formats:
            print(report.summary())
            outputs["console"] = report.summary()
        if "json" in formats:
            path = self.output_dir / f"eval_{report.spec_name}.json"
            path.write_text(json.dumps(report.to_dict(), indent=2))
            outputs["json"] = str(path)
        if "markdown" in formats:
            path = self.output_dir / f"eval_{report.spec_name}.md"
            lines = [
                f"# Evaluation Report: `{report.spec_name}`",
                f"**Status**: {'PASS' if report.passed else 'FAIL'}",
                f"**Timestamp**: {report.timestamp}",
                "",
                "| Metric | Value |",
                "|--------|-------|",
            ]
            for k, v in report.metrics.items():
                lines.append(f"| {k} | {v:.2%} |")
            path.write_text("\n".join(lines))
            outputs["markdown"] = str(path)
        return outputs
