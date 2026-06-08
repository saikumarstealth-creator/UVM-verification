from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class QualityScore:
    overall: float
    completeness_score: float
    syntax_score: float
    register_coverage_score: float
    ral_readiness: float
    coverage_readiness: float
    spec_coverage_score: float
    sequence_score: float
    protocol_correctness: float
    test_mapping_score: float
    hallucination_count: int
    details: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "syntax_score": round(self.syntax_score * 100, 1),
            "completeness_score": round(self.completeness_score * 100, 1),
            "ral_score": round(self.ral_readiness * 100, 1),
            "coverage_score": round(self.coverage_readiness * 100, 1),
            "sequence_score": round(self.sequence_score * 100, 1),
            "protocol_score": round(self.protocol_correctness * 100, 1),
            "test_mapping_score": round(self.test_mapping_score * 100, 1),
            "overall_score": round(self.overall * 100, 1),
        }

    def generate_report(self, spec_name: str = "uart") -> Dict[str, Any]:
        report = {
            "spec_name": spec_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ai_quality_scores": self.to_dict(),
            "breakdown": {
                "SV Syntax": f"{self.syntax_score * 100:.0f}% confidence",
                "Completeness": f"{self.completeness_score * 100:.0f}% files generated",
                "Register Coverage": f"{self.register_coverage_score * 100:.0f}%",
                "RAL Readiness": "ready" if self.ral_readiness > 0.5 else "missing registers",
                "Coverage Readiness": "ready" if self.coverage_readiness > 0.5 else "needs work",
                "Spec Coverage": f"{self.spec_coverage_score * 100:.0f}%",
                "Sequence Quality": f"{self.sequence_score * 100:.0f}%",
                "Protocol Correctness": f"{self.protocol_correctness * 100:.0f}%",
                "Test Mapping": f"{self.test_mapping_score * 100:.0f}%",
            },
            "hallucinations": self.hallucination_count,
            "details": self.details,
        }
        return report


def compute_quality_score(
    metrics: Dict[str, float],
    num_regs: int,
    spec_coverage: Optional[Dict[str, float]] = None,
    hallucination_count: int = 0,
    extra_metrics: Optional[Dict[str, float]] = None,
) -> QualityScore:
    completeness = metrics.get("completeness", 0.0)
    syntax_conf = metrics.get("sv_compile_confidence", 0.0)
    sv_errors = metrics.get("sv_errors", 0)
    reg_cov = metrics.get("register_coverage", 0.0)

    syntax_score = max(0.0, syntax_conf - 0.05 * sv_errors)
    ral_readiness = float(num_regs > 0) if reg_cov >= 1.0 else reg_cov
    coverage_readiness = 1.0 if num_regs == 0 else min(1.0, reg_cov + 0.2)

    spec_cov = spec_coverage.get("register_reference_coverage", 0.0) if spec_coverage else 0.0
    intf_cov = spec_coverage.get("interface_reference_coverage", 0.0) if spec_coverage else 1.0
    spec_coverage_score = spec_cov * intf_cov

    hallucination_penalty = min(0.5, hallucination_count * 0.1)

    sequence_score = extra_metrics.get("sequence_score", 0.85) if extra_metrics else 0.85
    protocol_correctness = extra_metrics.get("protocol_correctness", 0.85) if extra_metrics else 0.85
    test_mapping_score = extra_metrics.get("test_mapping_score", 0.85) if extra_metrics else 0.85

    weights = {
        "syntax": 0.15,
        "completeness": 0.15,
        "ral": 0.10,
        "coverage": 0.10,
        "protocol": 0.20,
        "sequence": 0.10,
        "reg_coverage": 0.10,
        "test_mapping": 0.10,
    }

    raw = (
        weights["syntax"] * syntax_score
        + weights["completeness"] * completeness
        + weights["ral"] * ral_readiness
        + weights["coverage"] * coverage_readiness
        + weights["protocol"] * protocol_correctness
        + weights["sequence"] * sequence_score
        + weights["reg_coverage"] * reg_cov
        + weights["test_mapping"] * test_mapping_score
    )
    overall = max(0.0, raw - hallucination_penalty)

    details: Dict[str, str] = {}
    details["syntax"] = f"confidence {syntax_conf * 100:.0f}% with {int(sv_errors)} error(s)"
    details["completeness"] = f"{completeness * 100:.0f}% files generated"
    details["register_coverage"] = f"{reg_cov * 100:.0f}% reg coverage"
    details["ral_readiness"] = "ready" if ral_readiness > 0.5 else "missing registers"
    details["coverage_readiness"] = "ready" if coverage_readiness > 0.5 else "needs work"
    details["spec_coverage"] = f"{spec_cov * 100:.0f}% reg refs, {intf_cov * 100:.0f}% intf refs"
    details["hallucinations"] = f"{hallucination_count} undefined register reference(s)"
    details["sequence_quality"] = f"{sequence_score * 100:.0f}% (virtual seqs, responses, scoreboard integration)"
    details["protocol_correctness"] = f"{protocol_correctness * 100:.0f}% (signal patterns, protocol compliance)"
    details["test_mapping"] = f"{test_mapping_score * 100:.0f}% (YAML sequences → generated test classes)"
    if hallucination_count > 0:
        details["hallucinations"] += " -- PENALTY APPLIED"

    return QualityScore(
        overall=round(overall, 4),
        completeness_score=round(completeness, 4),
        syntax_score=round(syntax_score, 4),
        register_coverage_score=round(reg_cov, 4),
        ral_readiness=round(ral_readiness, 4),
        coverage_readiness=round(coverage_readiness, 4),
        spec_coverage_score=round(spec_coverage_score, 4),
        sequence_score=round(sequence_score, 4),
        protocol_correctness=round(protocol_correctness, 4),
        test_mapping_score=round(test_mapping_score, 4),
        hallucination_count=hallucination_count,
        details=details,
    )
