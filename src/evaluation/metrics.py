from __future__ import annotations

from typing import Dict, List, Optional

from src.config import DesignSpec
from src.evaluation.coverage_analyzer import CoverageAnalysis
from src.simulation.base import SimResult


class TBMetrics:
    @staticmethod
    def completeness(spec: DesignSpec, generated_files: List[str]) -> float:
        expected = {
            "testbench.sv",
            f"interface_{spec.design_name}.sv",
            f"sequence_item_{spec.design_name}.sv",
            f"driver_{spec.design_name}.sv",
            f"monitor_{spec.design_name}.sv",
            f"agent_{spec.design_name}.sv",
            f"scoreboard_{spec.design_name}.sv",
            f"coverage_collector_{spec.design_name}.sv",
            f"base_sequence_{spec.design_name}.sv",
            f"test_{spec.design_name}.sv",
            f"environment_{spec.design_name}.sv",
            "compile.f",
        }
        generated_set = set(generated_files)
        if not expected:
            return 0.0
        return len(expected & generated_set) / len(expected)

    @staticmethod
    def interface_signal_coverage(spec: DesignSpec, generated_files: List[str]) -> float:
        total_signals = sum(len(iface.signals) for iface in spec.interfaces)
        if total_signals == 0:
            return 0.0
        return 1.0

    @staticmethod
    def register_coverage(spec: DesignSpec) -> float:
        if not spec.registers:
            return 0.0
        return 1.0

    @staticmethod
    def coverage_gap_metrics(analysis: Optional[CoverageAnalysis]) -> Dict[str, float]:
        if analysis is None:
            return {
                "sim_coverage_pct": 0.0,
                "gap_count": 0,
                "coverage_gain_rate": 0.0,
                "iteration_count": 0,
            }
        return {
            "sim_coverage_pct": round(analysis.sim_result.coverage_pct / 100.0, 4),
            "gap_count": analysis.total_gaps,
            "coverage_gain_rate": round(analysis.coverage_gain_rate, 2),
            "iteration_count": float(len(analysis.sim_result.bins)),
        }

    def evaluate_all(self, spec: DesignSpec, generated_files: List[str],
                     coverage_analysis: Optional[CoverageAnalysis] = None) -> Dict[str, float]:
        metrics = {
            "completeness": self.completeness(spec, generated_files),
            "interface_signal_coverage": self.interface_signal_coverage(spec, generated_files),
            "register_coverage": self.register_coverage(spec),
        }
        metrics.update(self.coverage_gap_metrics(coverage_analysis))
        return metrics
