from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class QualityScore:
    overall: float
    completeness_score: float
    syntax_score: float
    register_coverage_score: float
    ral_readiness: float
    coverage_readiness: float
    details: Dict[str, str]  # key -> verdict


def compute_quality_score(metrics: Dict[str, float], num_regs: int) -> QualityScore:
    """Compute a composite AI quality score from pipeline metrics.

    Weighs completeness, SV syntax health, register coverage, RAL readiness,
    and coverage readiness into a 0.0–1.0 overall score.
    """
    completeness = metrics.get("completeness", 0.0)
    syntax_conf = metrics.get("sv_compile_confidence", 0.0)
    sv_errors = metrics.get("sv_errors", 0)
    reg_cov = metrics.get("register_coverage", 0.0)

    # Completeness: file generation coverage (0.0-1.0)
    # Already 0.0-1.0 from TBMetrics

    # Syntax: clamp confidence, penalize for errors
    syntax_score = max(0.0, syntax_conf - 0.05 * sv_errors)

    # RAL readiness: if registers exist, full score if RAL model generated
    ral_readiness = float(num_regs > 0) if reg_cov >= 1.0 else reg_cov

    # Coverage readiness: if registers exist, did coverage_collector handle them?
    coverage_readiness = 1.0 if num_regs == 0 else min(1.0, reg_cov + 0.2)

    # Composite: weighted average
    weights = {
        "completeness": 0.25,
        "syntax": 0.25,
        "register": 0.20,
        "ral": 0.15,
        "coverage_ready": 0.15,
    }

    overall = (
        weights["completeness"] * completeness
        + weights["syntax"] * syntax_score
        + weights["register"] * reg_cov
        + weights["ral"] * ral_readiness
        + weights["coverage_ready"] * coverage_readiness
    )

    details: Dict[str, str] = {}
    details["completeness"] = f"{completeness * 100:.0f}% files generated"
    details["syntax"] = f"confidence {syntax_conf * 100:.0f}% with {int(sv_errors)} error(s)"
    details["register_coverage"] = f"{reg_cov * 100:.0f}% reg coverage"
    details["ral_readiness"] = "ready" if ral_readiness > 0.5 else "missing registers"
    details["coverage_readiness"] = "ready" if coverage_readiness > 0.5 else "needs work"

    return QualityScore(
        overall=round(overall, 4),
        completeness_score=round(completeness, 4),
        syntax_score=round(syntax_score, 4),
        register_coverage_score=round(reg_cov, 4),
        ral_readiness=round(ral_readiness, 4),
        coverage_readiness=round(coverage_readiness, 4),
        details=details,
    )
