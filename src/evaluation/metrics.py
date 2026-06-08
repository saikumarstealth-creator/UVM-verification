from __future__ import annotations

import os
from pathlib import Path
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
            f"driver_{spec.design_name}.sv",
            f"monitor_{spec.design_name}.sv",
            f"sequencer_{spec.design_name}.sv",
            f"agent_{spec.design_name}.sv",
            f"env_{spec.design_name}.sv",
            f"scoreboard_{spec.design_name}.sv",
            f"ral_{spec.design_name}.sv",
            f"test_{spec.design_name}.sv",
            f"coverage_collector_{spec.design_name}.sv",
            f"sequence_item_{spec.design_name}.sv",
            f"sequence_{spec.design_name}.sv",
            f"protocol_checker_{spec.design_name}.sv",
            "compile.f",
            "top_tb.sv",
        }
        generated_basenames = {os.path.basename(f) for f in generated_files}
        if not expected:
            return 0.0
        return len(expected & generated_basenames) / len(expected)

    @staticmethod
    def interface_signal_coverage(spec: DesignSpec, generated_files: List[str]) -> float:
        total_signals = sum(len(iface.signals) for iface in spec.interfaces)
        if total_signals == 0:
            return 0.0
        matched = 0
        all_text = ""
        for f in generated_files:
            try:
                all_text += Path(f).read_text(errors="replace")
            except (OSError, IOError):
                pass
        for iface in spec.interfaces:
            for sig in iface.signals:
                if sig.name in all_text:
                    matched += 1
        return matched / max(1, total_signals)

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

    @staticmethod
    def reusability_score(spec: DesignSpec, generated_files: List[str]) -> float:
        all_text = ""
        for f in generated_files:
            try:
                all_text += Path(f).read_text(errors="replace")
            except (OSError, IOError):
                pass
        score = 0.0
        if "parameter" in all_text:
            score += 0.2
        if "uvm_object_utils" in all_text or "uvm_component_utils" in all_text:
            score += 0.2
        if "uvm_config_db" in all_text:
            score += 0.2
        if "virtual" in all_text and "interface" in all_text:
            score += 0.2
        if "uvm_analysis_port" in all_text:
            score += 0.1
        if "callback" in all_text.lower():
            score += 0.1
        return min(1.0, score)

    @staticmethod
    def register_extraction_score(spec: DesignSpec, generated_files: List[str]) -> float:
        if not spec.registers:
            return 0.0
        all_text = ""
        for f in generated_files:
            try:
                all_text += Path(f).read_text(errors="replace")
            except (OSError, IOError):
                pass
        matched = 0
        for reg in spec.registers:
            if reg.name.lower() in all_text.lower():
                matched += 1
        reg_score = matched / max(1, len(spec.registers))
        field_score = 0.0
        total_fields = 0
        matched_fields = 0
        for reg in spec.registers:
            if hasattr(reg, 'fields') and reg.fields:
                for fld in reg.fields:
                    total_fields += 1
                    if fld.name.lower() in all_text.lower():
                        matched_fields += 1
        if total_fields > 0:
            field_score = matched_fields / total_fields
        return (reg_score * 0.6 + field_score * 0.4)

    @staticmethod
    def protocol_check_score(spec: DesignSpec, generated_files: List[str]) -> float:
        all_text = ""
        for f in generated_files:
            try:
                all_text += Path(f).read_text(errors="replace")
            except (OSError, IOError):
                pass
        score = 0.0
        checks = []
        if "assert property" in all_text or "assert_sequence" in all_text:
            score += 0.3
            checks.append("sva_assertions")
        if "protocol_checker" in all_text or "_protocol_checker" in all_text:
            score += 0.2
            checks.append("protocol_checker")
        if "covergroup" in all_text or "coverpoint" in all_text:
            score += 0.15
            checks.append("covergroups")
        if "cross" in all_text and "coverpoint" in all_text:
            score += 0.15
            checks.append("coverage_crosses")
        if "uvm_analysis_port" in all_text and "write(" in all_text:
            score += 0.1
            checks.append("analysis_ports")
        if "SCOREBOARD" in all_text or "scoreboard" in all_text.lower():
            score += 0.1
            checks.append("scoreboard")
        return min(1.0, score)

    def evaluate_all(self, spec: DesignSpec, generated_files: List[str],
                     coverage_analysis: Optional[CoverageAnalysis] = None) -> Dict[str, float]:
        metrics = {
            "completeness": self.completeness(spec, generated_files),
            "interface_signal_coverage": self.interface_signal_coverage(spec, generated_files),
            "register_coverage": self.register_coverage(spec),
            "protocol_check_score": self.protocol_check_score(spec, generated_files),
            "reusability_score": self.reusability_score(spec, generated_files),
            "register_extraction_score": self.register_extraction_score(spec, generated_files),
        }
        metrics.update(self.coverage_gap_metrics(coverage_analysis))
        return metrics
