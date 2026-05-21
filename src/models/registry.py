from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models.base_model import GenerationModel


class ModelRegistry:
    def __init__(self, registry_dir: str = "model_registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._versions_file = self.registry_dir / "versions.jsonl"
        self._versions_file.touch(exist_ok=True)

    def _load_versions(self) -> List[Dict[str, Any]]:
        versions = []
        if self._versions_file.exists():
            for line in self._versions_file.read_text().strip().split("\n"):
                if line.strip():
                    versions.append(json.loads(line))
        return versions

    def _save_version(self, entry: Dict[str, Any]) -> None:
        with open(self._versions_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _next_version(self) -> str:
        versions = self._load_versions()
        if not versions:
            return "v1"
        existing = []
        for v in versions:
            m = re.match(r"v(\d+)", v.get("version", "v0"))
            if m:
                existing.append(int(m.group(1)))
        return f"v{max(existing) + 1}" if existing else "v1"

    def register(self, model: GenerationModel,
                 metrics: Optional[Dict[str, float]] = None,
                 artifacts: Optional[Dict[str, str]] = None,
                 spec_name: str = "",
                 sim_coverage: Optional[float] = None,
                 iteration: int = 0) -> str:
        version = self._next_version()
        entry = {
            "version": version,
            "model_name": model.name,
            "spec_name": spec_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics or {},
            "artifacts": list(artifacts.keys()) if artifacts else [],
            "artifact_count": len(artifacts) if artifacts else 0,
            "sim_coverage_pct": sim_coverage,
            "iteration": iteration,
        }
        artifact_dir = self.registry_dir / version
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if artifacts:
            for name, path in artifacts.items():
                src = Path(path)
                dst = artifact_dir / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.exists():
                    dst.write_text(src.read_text())
                else:
                    dst.write_text(f"// {name} — not available\n")

        meta_path = artifact_dir / "version_meta.json"
        meta_path.write_text(json.dumps(entry, indent=2))
        self._save_version(entry)
        return version

    def get_version(self, version: str) -> Optional[Dict[str, Any]]:
        versions = self._load_versions()
        for v in versions:
            if v["version"] == version:
                return v
        return None

    def list_versions(self) -> List[Dict[str, Any]]:
        return self._load_versions()

    def compare_versions(self, v1: str, v2: str) -> Dict[str, Any]:
        v1_data = self.get_version(v1)
        v2_data = self.get_version(v2)
        result: Dict[str, Any] = {"version_a": v1, "version_b": v2}
        if v1_data and v2_data:
            m1 = v1_data.get("metrics", {})
            m2 = v2_data.get("metrics", {})
            diffs = {}
            for key in set(list(m1.keys()) + list(m2.keys())):
                a = m1.get(key, 0)
                b = m2.get(key, 0)
                diffs[key] = {"from": a, "to": b, "delta": round(b - a, 2)}
            result["metric_deltas"] = diffs
            result["version_a_coverage"] = v1_data.get("sim_coverage_pct")
            result["version_b_coverage"] = v2_data.get("sim_coverage_pct")
            result["artifact_count_a"] = v1_data.get("artifact_count", 0)
            result["artifact_count_b"] = v2_data.get("artifact_count", 0)
        return result

    def coverage_trend(self) -> List[Tuple[str, float]]:
        versions = self._load_versions()
        return [
            (v["version"], v.get("sim_coverage_pct", 0.0))
            for v in versions if v.get("sim_coverage_pct") is not None
        ]

    def latest_version(self) -> Optional[str]:
        versions = self._load_versions()
        return versions[-1]["version"] if versions else None
