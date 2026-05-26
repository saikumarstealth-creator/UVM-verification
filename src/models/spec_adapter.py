"""
Industry-level spec adapter for UVM testbench generation.

Provides precise mapping between:
- Signals (with fuzzy matching, direction/width awareness)
- Registers (address, access, field mapping)
- Interfaces
- Module and class name normalization

Includes:
- Fuzzy string matching with protocol-aware heuristics
- Signal signature matching (direction + width + position)
- Register mapping by address and name
- Confidence scoring for all mappings
- Mapping audit trail for debugging
"""

from __future__ import annotations

import difflib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("uvmgen")


class MappingConfidence(Enum):
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class SignalMapping:
    """Single signal mapping from source to target."""
    source_name: str
    target_name: str
    source_direction: str
    target_direction: str
    source_width: int
    target_width: int
    confidence: MappingConfidence
    confidence_score: float
    match_reason: str
    is_renamed: bool = False
    is_width_mismatch: bool = False
    is_direction_mismatch: bool = False


@dataclass
class RegisterMapping:
    """Single register mapping from source to target."""
    source_name: str
    target_name: str
    source_address: str
    target_address: str
    source_access: str
    target_access: str
    source_fields: List[str]
    target_fields: List[str]
    confidence: MappingConfidence
    confidence_score: float
    field_mappings: Dict[str, Tuple[str, float]] = field(default_factory=dict)


@dataclass
class InterfaceMapping:
    """Interface mapping between specs."""
    source_name: str
    target_name: str
    signal_mappings: List[SignalMapping]
    confidence: MappingConfidence
    confidence_score: float


@dataclass
class AdaptationPlan:
    """Complete plan for adapting a source spec to target."""
    source_design_name: str
    target_design_name: str
    interface_mappings: List[InterfaceMapping]
    register_mappings: List[RegisterMapping]
    overall_confidence: MappingConfidence
    overall_score: float
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unmapped_source_signals: List[str] = field(default_factory=list)
    unmapped_target_signals: List[str] = field(default_factory=list)
    unmapped_source_registers: List[str] = field(default_factory=list)
    unmapped_target_registers: List[str] = field(default_factory=list)

    def is_safe(self) -> bool:
        """Check if adaptation is safe (no critical errors)."""
        if self.errors:
            return False
        if self.unmapped_target_signals:
            return False
        if self.overall_score < 0.5:
            return False
        return True


PROTOCOL_SIGNAL_ALIASES: Dict[str, Dict[str, List[str]]] = {
    "uart": {
        "tx": ["tx", "uart_tx", "serial_tx", "txd", "so", "sout"],
        "rx": ["rx", "uart_rx", "serial_rx", "rxd", "si", "sin"],
        "baud": ["baud", "baud_tick", "baud_en", "tx_baud", "rx_baud", "tick"],
        "cts": ["cts", "cts_n", "ncts", "clear_to_send"],
        "rts": ["rts", "rts_n", "nrts", "request_to_send"],
        "intr": ["intr", "interrupt", "irq", "uart_int", "tx_int", "rx_int"],
    },
    "spi": {
        "sclk": ["sclk", "sck", "spi_clk", "serial_clk"],
        "mosi": ["mosi", "sdo", "sout", "tx", "spi_out"],
        "miso": ["miso", "sdi", "sin", "rx", "spi_in"],
        "ss": ["ss", "ss_n", "cs", "cs_n", "nss", "ncs", "slave_select"],
    },
    "i2c": {
        "scl": ["scl", "i2c_scl", "serial_clk"],
        "sda": ["sda", "i2c_sda", "serial_data"],
    },
    "wishbone": {
        "cyc": ["cyc", "wb_cyc", "cycle"],
        "stb": ["stb", "wb_stb", "strobe"],
        "we": ["we", "wb_we", "wr_en", "write_en"],
        "ack": ["ack", "wb_ack", "acknowledge"],
        "adr": ["adr", "addr", "wb_adr", "wb_addr", "address"],
        "dat_w": ["dat_w", "wb_dat_w", "wdata", "wr_data", "data_out"],
        "dat_r": ["dat_r", "wb_dat_r", "rdata", "rd_data", "data_in"],
    },
    "apb": {
        "psel": ["psel", "sel", "chip_sel"],
        "penable": ["penable", "enable", "stb"],
        "pwrite": ["pwrite", "wr_en", "we", "write"],
        "paddr": ["paddr", "addr", "address"],
        "pwdata": ["pwdata", "wdata", "data_w"],
        "prdata": ["prdata", "rdata", "data_r"],
        "pready": ["pready", "ready", "ack"],
    },
    "axi4lite": {
        "awvalid": ["awvalid", "aw_valid"],
        "awready": ["awready", "aw_ready"],
        "awaddr": ["awaddr", "aw_addr"],
        "wvalid": ["wvalid", "w_valid"],
        "wready": ["wready", "w_ready"],
        "wdata": ["wdata", "w_data"],
        "bvalid": ["bvalid", "b_valid"],
        "bready": ["bready", "b_ready"],
        "arvalid": ["arvalid", "ar_valid"],
        "arready": ["arready", "ar_ready"],
        "araddr": ["araddr", "ar_addr"],
        "rvalid": ["rvalid", "r_valid"],
        "rready": ["rready", "r_ready"],
        "rdata": ["rdata", "r_data"],
    },
}


class SignalCanonicalizer:
    """Canonicalizes signal names using protocol-aware aliases."""

    @staticmethod
    def canonicalize(name: str, protocol: Optional[str] = None) -> Tuple[str, str]:
        """
        Convert signal name to canonical form.

        Returns: (canonical_name, match_strength)
        - canonical_name: standardized name if recognized, else original.lower()
        - match_strength: "exact", "alias", "base", or "none"
        """
        name_lower = name.lower().strip()

        prefixes = ["wb_", "apb_", "axi_", "spi_", "uart_", "i2c_", "reg_", "sig_"]
        suffixes = ["_i", "_o", "_io", "_n", "_p", "_in", "_out"]

        base = name_lower
        for prefix in prefixes:
            if base.startswith(prefix):
                base = base[len(prefix):]
                break

        for suffix in suffixes:
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break

        if protocol and protocol in PROTOCOL_SIGNAL_ALIASES:
            aliases = PROTOCOL_SIGNAL_ALIASES[protocol]
            for canonical, variants in aliases.items():
                if name_lower in variants:
                    return canonical, "exact"
                if base in variants:
                    return canonical, "alias"

                for variant in variants:
                    if variant in name_lower or name_lower in variant:
                        if len(name_lower) >= 3 and len(variant) >= 3:
                            ratio = difflib.SequenceMatcher(None, name_lower, variant).ratio()
                            if ratio > 0.8:
                                return canonical, "base"

        return base if base else name_lower, "none"

    @staticmethod
    def signature(
        name: str,
        direction: str,
        width: int,
        protocol: Optional[str] = None,
    ) -> str:
        """Generate a unique signature for signal matching."""
        canonical, _ = SignalCanonicalizer.canonicalize(name, protocol)
        return f"{canonical}:{direction}:{width}"


class FuzzyMatcher:
    """Fuzzy string matching with multiple strategies."""

    @staticmethod
    def ratio(a: str, b: str) -> float:
        """Simple ratio between two strings."""
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def partial_ratio(a: str, b: str) -> float:
        """Best partial match ratio."""
        a_lower = a.lower()
        b_lower = b.lower()

        if len(a_lower) <= len(b_lower):
            shorter, longer = a_lower, b_lower
        else:
            shorter, longer = b_lower, a_lower

        best = 0.0
        for i in range(len(longer) - len(shorter) + 1):
            ratio = difflib.SequenceMatcher(None, shorter, longer[i:i+len(shorter)]).ratio()
            if ratio > best:
                best = ratio
            if best == 1.0:
                break
        return best

    @staticmethod
    def token_sort_ratio(a: str, b: str) -> float:
        """Match after sorting tokens."""
        def tokenize(s: str) -> List[str]:
            tokens = re.split(r'[_\s]+', s.lower().strip())
            return sorted([t for t in tokens if t])

        a_tokens = tokenize(a)
        b_tokens = tokenize(b)

        return difflib.SequenceMatcher(None, " ".join(a_tokens), " ".join(b_tokens)).ratio()

    @classmethod
    def best_match(
        cls,
        query: str,
        candidates: List[str],
        min_score: float = 0.6,
    ) -> Optional[Tuple[str, float]]:
        """Find best match for query in candidates."""
        if not candidates:
            return None

        scores: List[Tuple[str, float]] = []
        for cand in candidates:
            r = cls.ratio(query, cand)
            pr = cls.partial_ratio(query, cand)
            tsr = cls.token_sort_ratio(query, cand)
            score = max(r, pr, tsr)
            scores.append((cand, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        if scores[0][1] >= min_score:
            return scores[0]
        return None


class SpecAdapter:
    """
    Industry-level spec adapter for UVM testbench generation.

    Adapts a source spec (and its generated testbench) to a target spec.
    Provides complete mapping with confidence scoring and validation.
    """

    def __init__(
        self,
        source_protocol: Optional[str] = None,
        target_protocol: Optional[str] = None,
        strict_mode: bool = False,
    ):
        self.source_protocol = source_protocol
        self.target_protocol = target_protocol
        self.strict_mode = strict_mode
        self._logger = logging.getLogger("uvmgen.adapter")

    def create_adaptation_plan(
        self,
        source_spec_dict: Dict[str, Any],
        target_spec_dict: Dict[str, Any],
    ) -> AdaptationPlan:
        """
        Create a complete adaptation plan from source to target spec.

        Args:
            source_spec_dict: Source design spec (serialized DesignSpec)
            target_spec_dict: Target design spec

        Returns:
            AdaptationPlan with complete mappings and confidence scores
        """
        source_name = source_spec_dict.get("design_name", "unknown")
        target_name = target_spec_dict.get("design_name", "unknown")

        self._logger.info("Creating adaptation plan: %s -> %s", source_name, target_name)

        source_interfaces = source_spec_dict.get("interfaces", [])
        target_interfaces = target_spec_dict.get("interfaces", [])

        source_registers = source_spec_dict.get("registers", [])
        target_registers = target_spec_dict.get("registers", [])

        if_map = self._map_interfaces(source_interfaces, target_interfaces)

        reg_map = self._map_registers(source_registers, target_registers)

        overall_score, overall_conf = self._compute_overall_confidence(if_map, reg_map)

        warnings: List[str] = []
        errors: List[str] = []

        unmapped_src_sigs = self._find_unmapped_source_signals(source_interfaces, if_map)
        unmapped_tgt_sigs = self._find_unmapped_target_signals(target_interfaces, if_map)

        unmapped_src_regs = self._find_unmapped_source_registers(source_registers, reg_map)
        unmapped_tgt_regs = self._find_unmapped_target_registers(target_registers, reg_map)

        if unmapped_tgt_sigs:
            errors.append(f"Target has unmapped signals: {unmapped_tgt_sigs}")

        for ifm in if_map:
            for sm in ifm.signal_mappings:
                if sm.is_width_mismatch:
                    warnings.append(
                        f"Signal width mismatch: {sm.source_name}({sm.source_width}) -> "
                        f"{sm.target_name}({sm.target_width})"
                    )
                if sm.is_direction_mismatch:
                    warnings.append(
                        f"Signal direction mismatch: {sm.source_name}({sm.source_direction}) -> "
                        f"{sm.target_name}({sm.target_direction})"
                    )

        if overall_score < 0.5:
            errors.append(f"Overall confidence too low: {overall_score:.2f}")

        plan = AdaptationPlan(
            source_design_name=source_name,
            target_design_name=target_name,
            interface_mappings=if_map,
            register_mappings=reg_map,
            overall_confidence=overall_conf,
            overall_score=overall_score,
            warnings=warnings,
            errors=errors,
            unmapped_source_signals=unmapped_src_sigs,
            unmapped_target_signals=unmapped_tgt_sigs,
            unmapped_source_registers=unmapped_src_regs,
            unmapped_target_registers=unmapped_tgt_regs,
        )

        self._logger.info(
            "Adaptation plan created: score=%.2f, conf=%s, errors=%d, warnings=%d",
            plan.overall_score, plan.overall_confidence.value,
            len(plan.errors), len(plan.warnings)
        )

        return plan

    def _map_interfaces(
        self,
        source_ifaces: List[Dict[str, Any]],
        target_ifaces: List[Dict[str, Any]],
    ) -> List[InterfaceMapping]:
        """Map interfaces between source and target."""
        mappings: List[InterfaceMapping] = []

        source_by_name = {iface["name"]: iface for iface in source_ifaces}
        target_by_name = {iface["name"]: iface for iface in target_ifaces}

        matched_source: Set[str] = set()
        matched_target: Set[str] = set()

        for src_name, src_iface in source_by_name.items():
            best_match: Optional[Tuple[str, float]] = None

            if src_name in target_by_name:
                best_match = (src_name, 1.0)
            else:
                candidates = [n for n in target_by_name if n not in matched_target]
                if candidates:
                    result = FuzzyMatcher.best_match(src_name, candidates, min_score=0.7)
                    if result:
                        best_match = result

            if best_match:
                tgt_name, score = best_match
                if tgt_name in matched_target:
                    continue

                sig_mappings = self._map_signals(
                    src_iface.get("signals", []),
                    target_by_name[tgt_name].get("signals", []),
                )

                avg_sig_conf = self._average_signal_confidence(sig_mappings)
                if score >= 0.9 and avg_sig_conf >= 0.8:
                    conf = MappingConfidence.EXACT
                elif avg_sig_conf >= 0.6:
                    conf = MappingConfidence.HIGH
                elif avg_sig_conf >= 0.4:
                    conf = MappingConfidence.MEDIUM
                else:
                    conf = MappingConfidence.LOW

                combined_score = (score * 0.3) + (avg_sig_conf * 0.7)

                mappings.append(InterfaceMapping(
                    source_name=src_name,
                    target_name=tgt_name,
                    signal_mappings=sig_mappings,
                    confidence=conf,
                    confidence_score=combined_score,
                ))

                matched_source.add(src_name)
                matched_target.add(tgt_name)

        return mappings

    def _map_signals(
        self,
        source_signals: List[Dict[str, Any]],
        target_signals: List[Dict[str, Any]],
    ) -> List[SignalMapping]:
        """Map individual signals with protocol-aware matching."""
        mappings: List[SignalMapping] = []

        src_sigs = {s["name"]: s for s in source_signals}
        tgt_sigs = {s["name"]: s for s in target_signals}

        matched_src: Set[str] = set()
        matched_tgt: Set[str] = set()

        for src_name, src_sig in src_sigs.items():
            src_dir = src_sig.get("direction", "input")
            src_width = src_sig.get("width", 1)

            src_canon, _ = SignalCanonicalizer.canonicalize(
                src_name, self.source_protocol
            )

            candidates: List[Tuple[str, float, str, str, int]] = []

            for tgt_name, tgt_sig in tgt_sigs.items():
                if tgt_name in matched_tgt:
                    continue

                tgt_dir = tgt_sig.get("direction", "input")
                tgt_width = tgt_sig.get("width", 1)

                tgt_canon, _ = SignalCanonicalizer.canonicalize(
                    tgt_name, self.target_protocol
                )

                score = 0.0
                reason = ""

                if src_name == tgt_name:
                    score = 1.0
                    reason = "exact_name_match"
                elif src_canon == tgt_canon and src_canon:
                    score = 0.95
                    reason = f"canonical_match:{src_canon}"
                else:
                    name_ratio = FuzzyMatcher.ratio(src_name, tgt_name)
                    canon_ratio = FuzzyMatcher.ratio(src_canon, tgt_canon) if src_canon and tgt_canon else 0.0
                    score = max(name_ratio, canon_ratio)
                    reason = "fuzzy_match" if score > 0.7 else "weak_match"

                dir_match = 1.0 if src_dir == tgt_dir else 0.3
                width_match = 1.0 if src_width == tgt_width else 0.5

                final_score = score * 0.6 + dir_match * 0.25 + width_match * 0.15

                candidates.append((tgt_name, final_score, reason, tgt_dir, tgt_width))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                best_name, best_score, best_reason, best_dir, best_width = candidates[0]

                if best_score >= 0.3:
                    is_renamed = src_name != best_name
                    is_width_mismatch = src_width != best_width
                    is_dir_mismatch = src_dir != best_dir

                    if best_score >= 0.95:
                        conf = MappingConfidence.EXACT
                    elif best_score >= 0.75:
                        conf = MappingConfidence.HIGH
                    elif best_score >= 0.5:
                        conf = MappingConfidence.MEDIUM
                    else:
                        conf = MappingConfidence.LOW

                    mappings.append(SignalMapping(
                        source_name=src_name,
                        target_name=best_name,
                        source_direction=src_dir,
                        target_direction=best_dir,
                        source_width=src_width,
                        target_width=best_width,
                        confidence=conf,
                        confidence_score=best_score,
                        match_reason=best_reason,
                        is_renamed=is_renamed,
                        is_width_mismatch=is_width_mismatch,
                        is_direction_mismatch=is_dir_mismatch,
                    ))

                    matched_src.add(src_name)
                    matched_tgt.add(best_name)

        return mappings

    def _map_registers(
        self,
        source_regs: List[Dict[str, Any]],
        target_regs: List[Dict[str, Any]],
    ) -> List[RegisterMapping]:
        """Map registers by address and name."""
        mappings: List[RegisterMapping] = []

        src_by_addr = {r.get("address", ""): r for r in source_regs if r.get("address")}
        src_by_name = {r["name"]: r for r in source_regs}

        tgt_by_addr = {r.get("address", ""): r for r in target_regs if r.get("address")}
        tgt_by_name = {r["name"]: r for r in target_regs}

        matched_src: Set[str] = set()
        matched_tgt: Set[str] = set()

        for src_addr, src_reg in src_by_addr.items():
            if src_addr in tgt_by_addr and src_addr:
                tgt_reg = tgt_by_addr[src_addr]
                tgt_name = tgt_reg["name"]

                if tgt_name in matched_tgt:
                    continue

                score = 1.0 if src_reg["name"] == tgt_name else 0.8
                conf = MappingConfidence.EXACT if score == 1.0 else MappingConfidence.HIGH

                src_fields = [f["name"] for f in src_reg.get("fields", [])]
                tgt_fields = [f["name"] for f in tgt_reg.get("fields", [])]

                field_mappings = self._map_fields(src_fields, tgt_fields)

                mappings.append(RegisterMapping(
                    source_name=src_reg["name"],
                    target_name=tgt_name,
                    source_address=src_addr,
                    target_address=src_addr,
                    source_access=src_reg.get("access", "rw"),
                    target_access=tgt_reg.get("access", "rw"),
                    source_fields=src_fields,
                    target_fields=tgt_fields,
                    confidence=conf,
                    confidence_score=score,
                    field_mappings=field_mappings,
                ))

                matched_src.add(src_reg["name"])
                matched_tgt.add(tgt_name)

        for src_name, src_reg in src_by_name.items():
            if src_name in matched_src:
                continue

            src_addr = src_reg.get("address", "")

            if src_name in tgt_by_name:
                tgt_reg = tgt_by_name[src_name]
                tgt_addr = tgt_reg.get("address", "")

                score = 0.7
                if src_addr and tgt_addr and src_addr != tgt_addr:
                    score = 0.5

                src_fields = [f["name"] for f in src_reg.get("fields", [])]
                tgt_fields = [f["name"] for f in tgt_reg.get("fields", [])]
                field_mappings = self._map_fields(src_fields, tgt_fields)

                mappings.append(RegisterMapping(
                    source_name=src_name,
                    target_name=src_name,
                    source_address=src_addr,
                    target_address=tgt_addr,
                    source_access=src_reg.get("access", "rw"),
                    target_access=tgt_reg.get("access", "rw"),
                    source_fields=src_fields,
                    target_fields=tgt_fields,
                    confidence=MappingConfidence.MEDIUM,
                    confidence_score=score,
                    field_mappings=field_mappings,
                ))

                matched_src.add(src_name)

        return mappings

    def _map_fields(
        self,
        src_fields: List[str],
        tgt_fields: List[str],
    ) -> Dict[str, Tuple[str, float]]:
        """Map register fields."""
        mappings: Dict[str, Tuple[str, float]] = {}

        for sf in src_fields:
            if sf in tgt_fields:
                mappings[sf] = (sf, 1.0)
            else:
                result = FuzzyMatcher.best_match(sf, tgt_fields, min_score=0.6)
                if result:
                    mappings[sf] = result

        return mappings

    @staticmethod
    def _average_signal_confidence(sigs: List[SignalMapping]) -> float:
        if not sigs:
            return 0.0
        return sum(s.confidence_score for s in sigs) / len(sigs)

    def _compute_overall_confidence(
        self,
        if_maps: List[InterfaceMapping],
        reg_maps: List[RegisterMapping],
    ) -> Tuple[float, MappingConfidence]:
        """Compute overall confidence from mappings."""
        if not if_maps:
            return 0.0, MappingConfidence.NONE

        if_scores = [m.confidence_score for m in if_maps]
        reg_scores = [m.confidence_score for m in reg_maps] if reg_maps else []

        avg_if = sum(if_scores) / len(if_scores)
        avg_reg = sum(reg_scores) / len(reg_scores) if reg_scores else 0.5

        if_weight = 0.7 if reg_scores else 1.0
        reg_weight = 0.3 if reg_scores else 0.0

        overall = avg_if * if_weight + avg_reg * reg_weight

        if overall >= 0.9:
            conf = MappingConfidence.EXACT
        elif overall >= 0.7:
            conf = MappingConfidence.HIGH
        elif overall >= 0.5:
            conf = MappingConfidence.MEDIUM
        else:
            conf = MappingConfidence.LOW

        return overall, conf

    def _find_unmapped_source_signals(
        self,
        source_ifaces: List[Dict[str, Any]],
        if_maps: List[InterfaceMapping],
    ) -> List[str]:
        """Find source signals that weren't mapped."""
        all_src_signals: Set[str] = set()
        for iface in source_ifaces:
            for sig in iface.get("signals", []):
                all_src_signals.add(sig["name"])

        mapped_src: Set[str] = set()
        for ifm in if_maps:
            for sm in ifm.signal_mappings:
                mapped_src.add(sm.source_name)

        return sorted(all_src_signals - mapped_src)

    def _find_unmapped_target_signals(
        self,
        target_ifaces: List[Dict[str, Any]],
        if_maps: List[InterfaceMapping],
    ) -> List[str]:
        """Find target signals that weren't mapped."""
        all_tgt_signals: Set[str] = set()
        for iface in target_ifaces:
            for sig in iface.get("signals", []):
                all_tgt_signals.add(sig["name"])

        mapped_tgt: Set[str] = set()
        for ifm in if_maps:
            for sm in ifm.signal_mappings:
                mapped_tgt.add(sm.target_name)

        return sorted(all_tgt_signals - mapped_tgt)

    def _find_unmapped_source_registers(
        self,
        source_regs: List[Dict[str, Any]],
        reg_maps: List[RegisterMapping],
    ) -> List[str]:
        all_src = {r["name"] for r in source_regs}
        mapped = {rm.source_name for rm in reg_maps}
        return sorted(all_src - mapped)

    def _find_unmapped_target_registers(
        self,
        target_regs: List[Dict[str, Any]],
        reg_maps: List[RegisterMapping],
    ) -> List[str]:
        all_tgt = {r["name"] for r in target_regs}
        mapped = {rm.target_name for rm in reg_maps}
        return sorted(all_tgt - mapped)

    def apply_adaptation(
        self,
        plan: AdaptationPlan,
        source_content: str,
    ) -> Tuple[str, List[str], List[str]]:
        """
        Apply adaptation plan to source content.

        Args:
            plan: The adaptation plan
            source_content: Original SystemVerilog content

        Returns:
            (adapted_content, changes_applied, warnings)
        """
        content = source_content
        changes: List[str] = []
        warnings: List[str] = []

        old_name = plan.source_design_name
        new_name = plan.target_design_name

        if old_name != new_name:
            patterns = [
                (rf'\bmodule\s+{re.escape(old_name)}_tb\b', f'module {new_name}_tb'),
                (rf'\bmodule\s+{re.escape(old_name)}\b', f'module {new_name}'),
                (rf'\binterface\s+{re.escape(old_name)}_if\b', f'interface {new_name}_if'),
                (rf'\bclass\s+{re.escape(old_name)}_', f'class {new_name}_'),
                (rf'\b{re.escape(old_name)}_tb\b', f'{new_name}_tb'),
                (rf'\b{re.escape(old_name.upper())}_', f'{new_name.upper()}_'),
            ]

            for pattern, replacement in patterns:
                new_content, count = re.subn(pattern, replacement, content)
                if count > 0:
                    changes.append(f"Renamed {old_name} -> {new_name} ({count} occurrences)")
                    content = new_content

        for ifm in plan.interface_mappings:
            for sm in ifm.signal_mappings:
                if sm.is_renamed and sm.confidence_score >= 0.7:
                    old_sig = sm.source_name
                    new_sig = sm.target_name

                    word_pattern = rf'\b{re.escape(old_sig)}\b'
                    new_content, count = re.subn(word_pattern, new_sig, content)

                    if count > 0:
                        changes.append(
                            f"Signal: {old_sig} -> {new_sig} "
                            f"(conf={sm.confidence_score:.2f}, {count} occurrences)"
                        )
                        content = new_content

                    if sm.is_width_mismatch:
                        warnings.append(
                            f"Signal width mismatch: {old_sig}({sm.source_width}) "
                            f"-> {new_sig}({sm.target_width})"
                        )

                    if sm.is_direction_mismatch:
                        warnings.append(
                            f"Signal direction mismatch: {old_sig}({sm.source_direction}) "
                            f"-> {new_sig}({sm.target_direction})"
                        )

        for rm in plan.register_mappings:
            if rm.source_name != rm.target_name and rm.confidence_score >= 0.6:
                old_reg = rm.source_name
                new_reg = rm.target_name

                word_pattern = rf'\b{re.escape(old_reg)}\b'
                new_content, count = re.subn(word_pattern, new_reg, content)

                if count > 0:
                    changes.append(
                        f"Register: {old_reg} -> {new_reg} "
                        f"(conf={rm.confidence_score:.2f}, {count} occurrences)"
                    )
                    content = new_content

        return content, changes, warnings
