# src/tracking/mlflow_tracker.py — MLflow integration (optional)

from __future__ import annotations

from typing import Any, Dict, Optional

from src.tracking.experiments import ExperimentTracker


class MLflowTracker(ExperimentTracker):
    """MLflow-backed tracker (stub — enable when mlflow is available)."""

    def __init__(self, experiment_name: str = "uvm_tb_generator", tracking_uri: Optional[str] = None):
        super().__init__(experiment_name)
        self.tracking_uri = tracking_uri
        self._mlflow_available = self._check_mlflow()

    @staticmethod
    def _check_mlflow() -> bool:
        try:
            import mlflow  # noqa: F401
            return True
        except ImportError:
            return False

    def start_run(self, params: Optional[Dict[str, Any]] = None) -> str:
        if self._mlflow_available:
            import mlflow
            mlflow.set_experiment(self.experiment_name)
            if self.tracking_uri:
                mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.start_run()
            if params:
                mlflow.log_params(params)
            return mlflow.active_run().info.run_id
        return super().start_run(params)

    def log_metric(self, key: str, value: float) -> None:
        if self._mlflow_available:
            import mlflow
            mlflow.log_metric(key, value)
        else:
            super().log_metric(key, value)

    def log_artifact(self, path: str) -> None:
        if self._mlflow_available:
            import mlflow
            mlflow.log_artifact(path)
        else:
            super().log_artifact(path)

    def finish_run(self) -> None:
        if self._mlflow_available:
            import mlflow
            mlflow.end_run()
        else:
            super().finish_run()
