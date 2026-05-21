# src/data/collector.py — Collect specs from multiple sources (YAML, JSON, DB)

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml


class SpecCollector:
    """Collects raw design specifications from various sources."""

    SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}

    def __init__(self, source_paths: Optional[List[str]] = None):
        self.source_paths = source_paths or []

    def collect(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for path in self.source_paths:
            p = Path(path)
            if p.is_file() and p.suffix in self.SUPPORTED_EXTENSIONS:
                specs.append(self._read_file(p))
            elif p.is_dir():
                for f in sorted(p.glob("*.*")):
                    if f.suffix in self.SUPPORTED_EXTENSIONS:
                        specs.append(self._read_file(f))
        return specs

    def collect_from_database(self, connection_string: str, query: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("Database collector — implement for your ORM / DB backend")

    @staticmethod
    def _read_file(path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            if path.suffix in (".yaml", ".yml"):
                return yaml.safe_load(f)
            return json.load(f)
