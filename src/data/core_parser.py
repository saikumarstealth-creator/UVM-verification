# src/data/core_parser.py — FuseSoC .core file parser

from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml

from src.data.preprocessor import SpecPreprocessor


class CoreParser:
    """Parses FuseSoC .core files into the internal DesignSpec-compatible dict.

    The .core format (YAML) describes IP cores with:
      - name / version / description
      - parameters
      - interfaces (each with signals, type, bus standard)
      - registers (address, access, fields with bit positions)
      - clock_reset
      - filesets, targets
    """

    ACCESS_MAP = {
        "ro": "read-only",
        "wo": "write-only",
        "rw": "read-write",
        "rc": "read-clear",
        "rs": "read-set",
        "w1c": "write-1-to-clear",
    }

    def parse(self, content: str) -> Dict[str, Any]:
        raw = yaml.safe_load(content)
        spec: Dict[str, Any] = {}

        spec["design_name"] = self._extract_name(raw)
        spec["clock_reset"] = self._extract_clock_reset(raw)
        spec["interfaces"] = self._extract_interfaces(raw)
        spec["registers"] = self._extract_registers(raw)
        spec["parameters"] = self._extract_parameters(raw)

        return SpecPreprocessor().preprocess(spec)

    @staticmethod
    def _extract_name(raw: Dict[str, Any]) -> str:
        name = raw.get("name", "unknown")
        if isinstance(name, str):
            return name.strip().lower()
        return "unknown"

    @staticmethod
    def _extract_clock_reset(raw: Dict[str, Any]) -> Dict[str, Any]:
        cr = raw.get("clock_reset")
        if cr:
            return {
                "clock": cr.get("clock", "clk"),
                "reset": cr.get("reset", "rst_n"),
                "reset_active": cr.get("reset_active", 0),
            }
        return {"clock": "clk", "reset": "rst_n", "reset_active": 0}

    @staticmethod
    def _extract_interfaces(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        interfaces = raw.get("interfaces", [])
        result: List[Dict[str, Any]] = []
        for iface in interfaces:
            entry: Dict[str, Any] = {
                "name": iface.get("name", "bus"),
                "signals": [],
            }
            for sig in iface.get("signals", []):
                entry["signals"].append({
                    "name": sig.get("name", "sig"),
                    "direction": sig.get("direction", "input"),
                    "width": sig.get("width", 1),
                })
            result.append(entry)
        return result

    @staticmethod
    def _extract_registers(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        registers = raw.get("registers", [])
        result: List[Dict[str, Any]] = []
        seen = set()
        for reg in registers:
            name = reg.get("name", f"reg_{len(result)}")
            if name in seen:
                name = f"{name}_{len(result)}"
            seen.add(name)

            entry: Dict[str, Any] = {
                "name": name,
                "address": reg.get("address", "0x00"),
                "description": reg.get("description", ""),
                "access": reg.get("access", "rw"),
                "fields": [],
            }
            for fld in reg.get("fields", []):
                entry["fields"].append({
                    "name": fld.get("name", "field"),
                    "bits": fld.get("bits", "0"),
                    "description": fld.get("description", ""),
                })
            result.append(entry)
        return result

    @staticmethod
    def _extract_parameters(raw: Dict[str, Any]) -> Dict[str, Any]:
        params = raw.get("parameters", {})
        return {k: v.get("default") if isinstance(v, dict) else v for k, v in params.items()}


def parse_core_file(path: str) -> Dict[str, Any]:
    """Convenience: read .core file and return DesignSpec-compatible dict."""
    with open(path, "r") as f:
        return CoreParser().parse(f.read())
