# src/features/extractors.py — Feature extraction from design specs

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.config import DesignSpec
from src.models.ml_utils import RichFeatureVector


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


class RichSpecFeatureExtractor:
    """Extracts rich features from DesignSpec for ML similarity matching."""

    PROTOCOL_SIGNATURES = {
        "uart": {"tx", "rx", "baud"},
        "i2c": {"scl", "sda"},
        "spi": {"mosi", "miso", "sclk", "ss_n", "cs_n"},
        "axi": {"awvalid", "awready", "arvalid", "arready", "wvalid", "wready", "rvalid", "rready", "bvalid", "bready"},
        "apb": {"psel", "penable", "paddr", "pwrite", "prdata", "pwdata"},
        "wishbone": {"wb_cyc", "wb_stb", "wb_ack", "wb_we", "wb_adr", "wb_dat"},
    }

    def extract(self, spec: DesignSpec) -> RichFeatureVector:
        """Extract rich feature vector from a DesignSpec."""
        signals = [s for iface in spec.interfaces for s in iface.signals]
        signal_names = {s.name.lower() for s in signals}

        signal_directions: Dict[str, str] = {}
        signal_widths: Dict[str, int] = {}
        all_signal_names: List[str] = []

        for s in signals:
            all_signal_names.append(s.name)
            signal_directions[s.name] = s.direction
            signal_widths[s.name] = s.width if s.width else 1

        register_names: List[str] = []
        register_addresses: Dict[str, str] = {}
        register_fields: Dict[str, List[str]] = {}
        register_access: Dict[str, str] = {}

        for r in spec.registers:
            register_names.append(r.name)
            register_addresses[r.name] = r.address
            register_fields[r.name] = [f.name for f in r.fields]
            register_access[r.name] = r.access or "rw"

        interface_names = [iface.name for iface in spec.interfaces]

        complexity = self._compute_complexity(spec)
        protocol = self._detect_protocol(signal_names, spec.protocol)

        return RichFeatureVector(
            interface_count=len(spec.interfaces),
            total_signals=len(signals),
            register_count=len(spec.registers),
            total_fields=sum(len(r.fields) for r in spec.registers),
            complexity_score=complexity,
            protocol_type=protocol,
            signal_names=all_signal_names,
            signal_directions=signal_directions,
            signal_widths=signal_widths,
            register_names=register_names,
            register_addresses=register_addresses,
            register_fields=register_fields,
            register_access=register_access,
            interface_names=interface_names,
            design_name=spec.design_name,
        )

    def _detect_protocol(self, signal_names: set, explicit_protocol: Optional[str]) -> Optional[str]:
        """Detect protocol with explicit override."""
        if explicit_protocol:
            return explicit_protocol

        for proto, sigs in self.PROTOCOL_SIGNATURES.items():
            match_count = sum(1 for keyword in sigs if any(keyword in s for s in signal_names))
            if match_count >= len(sigs) * 0.5:
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


