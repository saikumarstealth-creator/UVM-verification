# src/generation/protocols/__init__.py — Protocol library loader

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ProtocolLibrary:
    """Loads and serves protocol definitions from YAML files.

    Each protocol file defines:
      - interface_template (signals)
      - register_template (registers + fields)
      - sequence_template (UVM sequence body)
      - coverage_template (covergroup definition)
      - config_parameters
    """

    _PROTOCOL_DIR = Path(__file__).parent.parent.parent.parent / "protocols"

    def __init__(self, protocol_dir: Optional[str] = None):
        self._protocol_dir = Path(protocol_dir) if protocol_dir else self._PROTOCOL_DIR
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load(self, protocol_name: str) -> Dict[str, Any]:
        name = protocol_name.lower()
        if name in self._cache:
            return self._cache[name]

        for ext in [".yaml", ".yml"]:
            path = self._protocol_dir / f"{name}{ext}"
            if path.exists():
                with open(path, "r") as f:
                    data: Dict[str, Any] = yaml.safe_load(f)
                self._cache[name] = data
                return data

        raise FileNotFoundError(f"Protocol definition not found: {protocol_name} (looked in {self._protocol_dir})")

    def list_available(self) -> list[str]:
        return sorted(
            p.stem for p in self._protocol_dir.glob("*.yaml") if p.stem != "template"
        )

    def get_signals(self, protocol_name: str) -> list[Dict[str, Any]]:
        data = self.load(protocol_name)
        return data.get("interface_template", {}).get("signals", [])

    def get_registers(self, protocol_name: str) -> list[Dict[str, Any]]:
        data = self.load(protocol_name)
        return data.get("register_template", [])

    def get_sequence_body(self, protocol_name: str) -> str:
        data = self.load(protocol_name)
        return data.get("sequence_template", {}).get("body", "")

    def get_coverage(self, protocol_name: str) -> list[Dict[str, Any]]:
        data = self.load(protocol_name)
        return data.get("coverage_template", [])

    def get_config_parameters(self, protocol_name: str) -> list[Dict[str, Any]]:
        data = self.load(protocol_name)
        return data.get("config_parameters", [])
