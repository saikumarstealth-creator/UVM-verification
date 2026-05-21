# src/tracking/experiments.py — Experiment tracking (lightweight MLflow-style)

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExperimentRun:
    """A single experiment run — analogous to an MLflow run."""

    def __init__(self, run_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.params = params or {}
        self.metrics: Dict[str, float] = {}
        self.artifacts: List[str] = []
        self.start_time = datetime.now(timezone.utc).isoformat()
        self.end_time: Optional[str] = None
        self.status = "RUNNING"

    def log_metric(self, key: str, value: float) -> None:
        self.metrics[key] = value

    def log_artifact(self, path: str) -> None:
        self.artifacts.append(path)

    def finish(self) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = "FINISHED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "params": self.params,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
        }


class ExperimentTracker:
    """Lightweight experiment tracker (drop-in for MLflow in constrained envs)."""

    def __init__(self, experiment_name: str = "uvm_tb_generator", tracking_dir: str = "logs/experiments"):
        self.experiment_name = experiment_name
        self.tracking_dir = Path(tracking_dir) / experiment_name
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.current_run: Optional[ExperimentRun] = None

    def start_run(self, params: Optional[Dict[str, Any]] = None) -> str:
        run = ExperimentRun(params=params)
        self.current_run = run
        self._save_run(run)
        return run.run_id

    def log_metric(self, key: str, value: float) -> None:
        if self.current_run:
            self.current_run.log_metric(key, value)
            self._save_run(self.current_run)

    def log_artifact(self, path: str) -> None:
        if self.current_run:
            self.current_run.log_artifact(path)
            self._save_run(self.current_run)

    def finish_run(self) -> None:
        if self.current_run:
            self.current_run.finish()
            self._save_run(self.current_run)
            self.current_run = None

    def _save_run(self, run: ExperimentRun) -> None:
        run_path = self.tracking_dir / f"run_{run.run_id}.json"
        run_path.write_text(json.dumps(run.to_dict(), indent=2))
