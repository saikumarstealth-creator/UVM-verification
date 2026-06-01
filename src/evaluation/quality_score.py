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
    spec_coverage_score: float  # new: cross-file reference validation
    hallucination_count: int    # new: number of undefined register refs
    details: Dict[str, str]


def compute_quality_score(
    metrics: Dict[str, float],
    num_regs: int,
    spec_coverage: Optional[Dict[str, float]] = None,
    hallucination_count: int = 0,
) -> QualityScore:
    completeness = metrics.get("completeness", 0.0)
    syntax_conf = metrics.get("sv_compile_confidence", 0.0)
    sv_errors = metrics.get("sv_errors", 0)
    reg_cov = metrics.get("register_coverage", 0.0)

    syntax_score = max(0.0, syntax_conf - 0.05 * sv_errors)
    ral_readiness = float(num_regs > 0) if reg_cov >= 1.0 else reg_cov
    coverage_readiness = 1.0 if num_regs == 0 else min(1.0, reg_cov + 0.2)

    # Spec coverage from cross-file validator
    spec_cov = spec_coverage.get("register_reference_coverage", 0.0) if spec_coverage else 0.0
    intf_cov = spec_coverage.get("interface_reference_coverage", 0.0) if spec_coverage else 1.0
    spec_coverage_score = spec_cov * intf_cov

    # Hallucination penalty: -0.1 per hallucination, clamped
    hallucination_penalty = min(0.5, hallucination_count * 0.1)

    weights = {
        "completeness": 0.15,
        "syntax": 0.15,
        "register": 0.15,
        "ral": 0.10,
        "coverage_ready": 0.10,
        "spec_coverage": 0.35,
    }

    raw = (
        weights["completeness"] * completeness
        + weights["syntax"] * syntax_score
        + weights["register"] * reg_cov
        + weights["ral"] * ral_readiness
        + weights["coverage_ready"] * coverage_readiness
        + weights["spec_coverage"] * spec_coverage_score
    )
    overall = max(0.0, raw - hallucination_penalty)

    details: Dict[str, str] = {}
    details["completeness"] = f"{completeness * 100:.0f}% files generated"
    details["syntax"] = f"confidence {syntax_conf * 100:.0f}% with {int(sv_errors)} error(s)"
    details["register_coverage"] = f"{reg_cov * 100:.0f}% reg coverage"
    details["ral_readiness"] = "ready" if ral_readiness > 0.5 else "missing registers"
    details["coverage_readiness"] = "ready" if coverage_readiness > 0.5 else "needs work"
    details["spec_coverage"] = f"{spec_cov * 100:.0f}% reg refs, {intf_cov * 100:.0f}% intf refs"
    details["hallucinations"] = f"{hallucination_count} undefined register reference(s)"
    if hallucination_count > 0:
        details["hallucinations"] += " — PENALTY APPLIED"

    return QualityScore(
        overall=round(overall, 4),
        completeness_score=round(completeness, 4),
        syntax_score=round(syntax_score, 4),
        register_coverage_score=round(reg_cov, 4),
        ral_readiness=round(ral_readiness, 4),
        coverage_readiness=round(coverage_readiness, 4),
        spec_coverage_score=round(spec_coverage_score, 4),
        hallucination_count=hallucination_count,
        details=details,
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
