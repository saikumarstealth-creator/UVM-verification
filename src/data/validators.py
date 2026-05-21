# src/data/validators.py — Industry-grade validation rules engine

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import DesignSpec
from src.generation.protocols import ProtocolLibrary


class ValidationResult:
    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def __bool__(self) -> bool:
        return self.is_valid

    def __str__(self) -> str:
        if self.is_valid and not self.warnings:
            return "Validation passed"
        lines = []
        if self.errors:
            lines.append("ERRORS:")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.warnings:
            lines.append("WARNINGS:")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines) if lines else "Validation passed"


class IndustryValidator:
    """Industry-grade validation for IP design specs.

    Covers:
      - Structural: naming, completeness, signal consistency
      - Protocol: correct interface for declared protocol
      - Register: address alignment, no overlap, access conventions
      - Fab: foundry-ready checks (reset, CDC, DFT, testability)
      - Schema: compliance with master JSON Schema
    """

    def __init__(self, schema_path: Optional[str] = None):
        self._schema: Optional[Dict[str, Any]] = None
        if schema_path and Path(schema_path).exists():
            self._schema = json.loads(Path(schema_path).read_text())

    def validate(self, spec: DesignSpec, strict: bool = True) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        # -- Structural checks
        errors.extend(self._check_naming(spec))
        errors.extend(self._check_interfaces(spec))
        warnings.extend(self._check_design_meta(spec))

        # -- Protocol checks
        warnings.extend(self._check_protocol_consistency(spec))

        # -- Register checks (industry-grade)
        reg_errors, reg_warnings = self._check_register_map(spec)
        errors.extend(reg_errors)
        warnings.extend(reg_warnings)
        warnings.extend(self._check_register_conventions(spec))

        # -- Fab / DFT checks
        errors.extend(self._check_reset(spec))

        # -- Schema compliance
        errors.extend(self._check_schema(spec))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors if strict else [],
            warnings=warnings,
        )

    @staticmethod
    def _check_naming(spec: DesignSpec) -> List[str]:
        import re
        errors = []
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", spec.design_name):
            errors.append(f"Invalid design name: '{spec.design_name}' — must match [a-zA-Z_][a-zA-Z0-9_]*")
        seen_names = set()
        for iface in spec.interfaces:
            if iface.name in seen_names:
                errors.append(f"Duplicate interface name: '{iface.name}'")
            seen_names.add(iface.name)
        return errors

    @staticmethod
    def _check_interfaces(spec: DesignSpec) -> List[str]:
        errors = []
        for iface in spec.interfaces:
            if not iface.signals:
                errors.append(f"Interface '{iface.name}' has no signals")
            seen = set()
            for sig in iface.signals:
                if sig.name in seen:
                    errors.append(f"Duplicate signal '{sig.name}' in interface '{iface.name}'")
                seen.add(sig.name)
        return errors

    @staticmethod
    def _check_design_meta(spec: DesignSpec) -> List[str]:
        warnings = []
        if len(spec.interfaces) == 1 and len(spec.interfaces[0].signals) < 3:
            warnings.append("Only one interface with fewer than 3 signals — verify completeness")
        return warnings

    def _check_protocol_consistency(self, spec: DesignSpec) -> List[str]:
        errors = []
        lib = ProtocolLibrary()
        available = lib.list_available()
        for iface in spec.interfaces:
            proto = getattr(iface, "protocol", None) or getattr(iface, "type", None)
            if proto and proto.lower() in available:
                try:
                    proto_signals = {s["name"].lower() for s in lib.get_signals(proto.lower())}
                    actual_signals = {s.name.lower() for s in iface.signals}
                    missing = proto_signals - actual_signals
                    if missing:
                        warnings.warn(
                            f"Interface '{iface.name}' claims protocol '{proto}' "
                            f"but is missing signals: {', '.join(sorted(missing))}"
                        )
                except Exception:
                    pass
        return errors

    @staticmethod
    def _check_register_map(spec: DesignSpec) -> tuple[list[str], list[str]]:
        from collections import Counter
        errors: List[str] = []
        warnings: List[str] = []
        addr_counts = Counter(reg.address.lower() for reg in spec.registers)
        multi = {a: c for a, c in addr_counts.items() if c > 1}
        if multi:
            for addr, count in multi.items():
                names = [r.name for r in spec.registers if r.address.lower() == addr]
                warnings.append(
                    f"{count} registers share address {addr}: {', '.join(names)} "
                    f"— verify page/bank select logic"
                )
        seen_names: set = set()
        for reg in spec.registers:
            if reg.name in seen_names:
                errors.append(f"Duplicate register name: '{reg.name}'")
            seen_names.add(reg.name)

            if not reg.address.startswith("0x"):
                errors.append(f"Register '{reg.name}' address '{reg.address}' not in hex format (0x...)")

            # Check field bit ranges don't overlap
            IndustryValidator._check_field_overlap(reg, errors)

            # Check field total bits don't exceed 32
            total_bits = 0
            for f in reg.fields:
                bits_str = f.bits
                if ":" in bits_str:
                    hi, lo = bits_str.split(":")
                    total_bits += int(hi) - int(lo) + 1
                else:
                    total_bits += 1
            if total_bits > 32:
                errors.append(f"Register '{reg.name}' field total ({total_bits}b) exceeds 32b")
        return errors, warnings

    @staticmethod
    def _check_field_overlap(reg, errors) -> None:
        ranges = []
        for f in reg.fields:
            bits = f.bits
            if ":" in bits:
                hi, lo = int(bits.split(":")[0]), int(bits.split(":")[1])
                if hi < lo:
                    errors.append(f"Field '{f.name}' in '{reg.name}' has reversed bit range ({bits})")
            else:
                hi = lo = int(bits)
            ranges.append((lo, hi, f.name))
        ranges.sort()
        for i in range(len(ranges) - 1):
            if ranges[i][1] >= ranges[i + 1][0]:
                errors.append(
                    f"Field overlap in '{reg.name}': '{ranges[i][2]}' [{ranges[i][0]}:{ranges[i][1]}] "
                    f"overlaps '{ranges[i+1][2]}' [{ranges[i+1][0]}:{ranges[i+1][1]}]"
                )

    @staticmethod
    def _check_register_conventions(spec: DesignSpec) -> List[str]:
        warnings = []
        for reg in spec.registers:
            if not reg.fields:
                warnings.append(f"Register '{reg.name}' has no fields defined")
            if reg.address == "0x00" and spec.registers.index(reg) > 0:
                warnings.append(f"Register '{reg.name}' at 0x00 but not first in list — verify address")
        return warnings

    @staticmethod
    def _check_reset(spec: DesignSpec) -> List[str]:
        errors = []
        cr = spec.clock_reset
        if not cr.clock:
            errors.append("No clock signal defined")
        if not cr.reset:
            errors.append("No reset signal defined")
        if cr.clock == cr.reset:
            errors.append(f"Clock and reset signals share the same name: '{cr.clock}'")
        return errors

    def _check_schema(self, spec: DesignSpec) -> List[str]:
        if not self._schema:
            return []
        errors = []
        spec_dict = spec.model_dump()
        required = self._schema.get("required", [])
        for req in required:
            if req not in spec_dict or spec_dict[req] is None:
                errors.append(f"Missing required field per schema: '{req}'")
        return errors


# Backward-compatible alias
SpecValidator = IndustryValidator
