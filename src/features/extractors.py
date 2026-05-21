# src/features/extractors.py — Feature extraction from design specs

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.config import DesignSpec


class FeatureVector(BaseModel):
    """Numerical / categorical features extracted from a spec for downstream use."""
    interface_count: int = 0
    total_signals: int = 0
    register_count: int = 0
    total_fields: int = 0
    has_output_signals: bool = False
    has_input_signals: bool = False
    protocol_type: Optional[str] = None
    complexity_score: float = 0.0

    model_config = {"extra": "forbid"}


class SpecFeatureExtractor:
    """Extracts structured features from DesignSpec for analytics / ML."""

    PROTOCOL_SIGNATURES = {
        "uart": {"tx", "rx", "baud"},
        "i2c": {"scl", "sda"},
        "spi": {"mosi", "miso", "sclk", "ss_n"},
        "axi": {"awvalid", "awready", "arvalid", "arready", "wvalid", "wready", "rvalid", "rready", "bvalid", "bready"},
        "apb": {"psel", "penable", "paddr", "pwrite"},
    }

    def extract(self, spec: DesignSpec) -> FeatureVector:
        signals = [s for iface in spec.interfaces for s in iface.signals]
        signal_names = {s.name.lower() for s in signals}

        return FeatureVector(
            interface_count=len(spec.interfaces),
            total_signals=len(signals),
            register_count=len(spec.registers),
            total_fields=sum(len(r.fields) for r in spec.registers),
            has_output_signals=any(s.direction == "output" for s in signals),
            has_input_signals=any(s.direction == "input" for s in signals),
            protocol_type=self._detect_protocol(signal_names),
            complexity_score=self._compute_complexity(spec),
        )

    @staticmethod
    def _detect_protocol(signal_names: set) -> Optional[str]:
        for proto, sigs in SpecFeatureExtractor.PROTOCOL_SIGNATURES.items():
            if all(any(keyword in s for s in signal_names) for keyword in sigs):
                return proto
        return None

    @staticmethod
    def _compute_complexity(spec: DesignSpec) -> float:
        score = 0.0
        score += len(spec.interfaces) * 1.5
        score += sum(len(iface.signals) for iface in spec.interfaces) * 0.8
        score += len(spec.registers) * 2.0
        score += sum(len(r.fields) for r in spec.registers) * 0.5
        return round(score, 2)


