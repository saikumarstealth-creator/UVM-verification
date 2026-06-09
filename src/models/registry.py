from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ModelRegistry:
    STAGES = ["development", "staging", "production", "archived"]

    def __init__(self, registry_dir: str = "model_registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._versions_file = self.registry_dir / "versions.jsonl"
        self._versions_file.touch(exist_ok=True)
        self._stage_file = self.registry_dir / "stages.json"
        self._stage_data: Dict[str, str] = self._load_stages()

    def _load_versions(self) -> List[Dict[str, Any]]:
        versions = []
        if self._versions_file.exists():
            content = self._versions_file.read_text().strip()
            if content:
                for line in content.split("\n"):
                    if line.strip():
                        try:
                            versions.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return versions

    def _load_stages(self) -> Dict[str, str]:
        if self._stage_file.exists():
            try:
                return json.loads(self._stage_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_stages(self) -> None:
        self._stage_file.write_text(json.dumps(self._stage_data, indent=2))

    def _save_version(self, entry: Dict[str, Any]) -> None:
        with open(self._versions_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _next_version(self) -> str:
        versions = self._load_versions()
        if not versions:
            return "v0.1.0"
        existing = []
        for v in versions:
            m = re.match(r"v(\d+)\.(\d+)\.(\d+)", v.get("version", "v0.0.0"))
            if m:
                existing.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        if existing:
            latest = max(existing)
            return f"v{latest[0]}.{latest[1] + 1}.0"
        return "v0.1.0"

    def promote(self, version: str, stage: str) -> bool:
        if stage not in self.STAGES:
            return False
        if not self.get_version(version):
            return False
        self._stage_data[version] = stage
        self._save_stages()
        return True

    def get_stage(self, stage: str) -> Optional[Dict[str, Any]]:
        for ver, s in self._stage_data.items():
            if s == stage:
                return self.get_version(ver)
        return None

    def list_by_stage(self) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {s: [] for s in self.STAGES}
        for ver, stage in self._stage_data.items():
            vdata = self.get_version(ver)
            if vdata:
                result[stage].append(vdata)
        return result

    def register(
        self, model: Any, metrics: Optional[Dict[str, float]] = None,
        artifacts: Optional[Dict[str, str]] = None,
        spec_name: str = "", sim_coverage: Optional[float] = None,
        iteration: int = 0, tags: Optional[Dict[str, str]] = None,
        stage: str = "development",
    ) -> str:
        version = self._next_version()
        entry: Dict[str, Any] = {
            "version": version,
            "model_name": getattr(model, "name", "unknown"),
            "spec_name": spec_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics or {},
            "artifacts": list(artifacts.keys()) if artifacts else [],
            "artifact_count": len(artifacts) if artifacts else 0,
            "sim_coverage_pct": sim_coverage,
            "iteration": iteration,
            "tags": tags or {},
        }
        artifact_dir = self.registry_dir / version
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if artifacts:
            for name, content in artifacts.items():
                dst = artifact_dir / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, str) and Path(content).exists():
                    dst.write_text(Path(content).read_text())
                elif isinstance(content, str):
                    dst.write_text(content)
                elif isinstance(content, dict):
                    dst.write_text(json.dumps(content, indent=2))
                else:
                    dst.write_text(str(content))

        meta_path = artifact_dir / "version_meta.json"
        meta_path.write_text(json.dumps(entry, indent=2))
        self._save_version(entry)

        if stage in self.STAGES:
            self._stage_data[version] = stage
            self._save_stages()

        return version

    def get_version(self, version: str) -> Optional[Dict[str, Any]]:
        versions = self._load_versions()
        for v in versions:
            if v["version"] == version:
                v["stage"] = self._stage_data.get(version, "development")
                return v
        return None

    def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        versions = self._load_versions()
        versions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        for v in versions:
            v["stage"] = self._stage_data.get(v["version"], "development")
        return versions[:limit]

    def compare_versions(self, v1: str, v2: str) -> Dict[str, Any]:
        v1_data = self.get_version(v1)
        v2_data = self.get_version(v2)
        result: Dict[str, Any] = {
            "version_a": v1, "version_b": v2,
            "stage_a": self._stage_data.get(v1, "development"),
            "stage_b": self._stage_data.get(v2, "development"),
        }
        if v1_data and v2_data:
            m1 = v1_data.get("metrics", {})
            m2 = v2_data.get("metrics", {})
            diffs = {}
            for key in set(list(m1.keys()) + list(m2.keys())):
                a = m1.get(key, 0)
                b = m2.get(key, 0)
                pct_change = ((b - a) / max(abs(a), 0.001)) * 100 if a != 0 else 0
                diffs[key] = {
                    "from": a, "to": b, "delta": round(b - a, 2),
                    "pct_change": round(pct_change, 1),
                }
            result["metric_deltas"] = diffs
            result["version_a_coverage"] = v1_data.get("sim_coverage_pct")
            result["version_b_coverage"] = v2_data.get("sim_coverage_pct")
            result["artifact_count_a"] = v1_data.get("artifact_count", 0)
            result["artifact_count_b"] = v2_data.get("artifact_count", 0)
            result["iteration_a"] = v1_data.get("iteration", 0)
            result["iteration_b"] = v2_data.get("iteration", 0)
            result["timestamp_a"] = v1_data.get("timestamp")
            result["timestamp_b"] = v2_data.get("timestamp")
        return result

    def coverage_trend(self) -> List[Dict[str, Any]]:
        versions = self._load_versions()
        trend = []
        for v in versions:
            cov = v.get("sim_coverage_pct")
            if cov is not None:
                trend.append({
                    "version": v["version"],
                    "coverage": cov,
                    "timestamp": v.get("timestamp"),
                    "iteration": v.get("iteration", 0),
                    "spec": v.get("spec_name", ""),
                    "stage": self._stage_data.get(v["version"], "development"),
                })
        return trend

    def latest_version(self, stage: Optional[str] = None) -> Optional[str]:
        if stage:
            staged_versions = {v: s for v, s in self._stage_data.items() if s == stage}
            if not staged_versions:
                return None
            versions = self._load_versions()
            for v in reversed(versions):
                if v["version"] in staged_versions:
                    return v["version"]
            return None
        versions = self._load_versions()
        return versions[-1]["version"] if versions else None

    def delete_version(self, version: str) -> bool:
        versions = self._load_versions()
        filtered = [v for v in versions if v["version"] != version]
        if len(filtered) == len(versions):
            return False
        self._versions_file.write_text(
            "\n".join(json.dumps(v) for v in filtered) + "\n"
        )
        artifact_dir = self.registry_dir / version
        if artifact_dir.exists():
            import shutil
            shutil.rmtree(artifact_dir)
        self._stage_data.pop(version, None)
        self._save_stages()
        return True

    def get_summary(self) -> Dict[str, Any]:
        versions = self._load_versions()
        stages = self.list_by_stage()
        return {
            "total_versions": len(versions),
            "total_staged": len(self._stage_data),
            "stages": {s: len(items) for s, items in stages.items()},
            "latest": versions[-1]["version"] if versions else None,
            "latest_production": self.latest_version("production"),
            "coverage_trend_count": len(self.coverage_trend()),
        }
