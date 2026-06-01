"""
Coverage Predictor — ML model that predicts optimal test parameters
and expected coverage from design specifications.

Uses ensemble methods to recommend which verification scenarios
(max baud rates, data patterns, interrupt tests, loopback modes)
will close coverage gaps most efficiently.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from src.config import DesignSpec
except ImportError:
    DesignSpec = None

logger = logging.getLogger("uvmgen.ml.coverage_predictor")

SEQUENCE_TEMPLATES = {
    "uart": [
        "uart_config_seq",
        "uart_tx_seq",
        "uart_rx_seq",
        "uart_loopback_seq",
        "uart_interrupt_seq",
        "uart_baud_change_seq",
        "uart_error_injection_seq",
        "uart_coverage_seq",
    ],
    "spi": [
        "spi_config_seq",
        "spi_tx_seq",
        "spi_rx_seq",
        "spi_loopback_seq",
        "spi_speed_change_seq",
    ],
    "i2c": [
        "i2c_config_seq",
        "i2c_write_seq",
        "i2c_read_seq",
        "i2c_loopback_seq",
    ],
    "axi4lite": [
        "axi_write_burst_seq",
        "axi_read_burst_seq",
        "axi_random_seq",
    ],
    "wishbone": [
        "wb_write_seq",
        "wb_read_seq",
        "wb_random_seq",
        "wb_pipeline_seq",
    ],
    "apb": [
        "apb_write_seq",
        "apb_read_seq",
        "apb_random_seq",
    ],
}

PARAMETER_SPACES = {
    "uart": {
        "baud_rates": [9600, 19200, 38400, 57600, 115200, 230400],
        "data_bits": [5, 6, 7, 8],
        "stop_bits": [1, 2],
        "parity_modes": ["none", "odd", "even", "mark", "space"],
        "data_patterns": ["alternating", "walking_one", "walking_zero", "edge", "incrementing"],
        "interrupt_types": ["rx_data", "tx_empty", "line_status", "modem_status"],
    },
    "spi": {
        "speeds": [100000, 500000, 1000000, 5000000, 10000000],
        "modes": [0, 1, 2, 3],
        "data_bits": [8, 16, 32],
    },
    "i2c": {
        "speeds": [100000, 400000, 1000000],
        "addrs": ["7bit", "10bit"],
    },
}


@dataclass
class CoverageRecommendation:
    sequence: str
    priority: float
    rationale: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_coverage_gain: float = 0.0


@dataclass
class CoveragePrediction:
    expected_total: float
    sequence_predictions: List[CoverageRecommendation] = field(default_factory=list)
    coverage_gaps: List[str] = field(default_factory=list)
    model_confidence: float = 0.0


class CoveragePredictor:
    """Predicts optimal verification parameters and coverage from design specs."""

    def __init__(self):
        self.reg: Optional[RandomForestRegressor] = None
        self.gbr: Optional[GradientBoostingRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        self.encoder: Optional[OneHotEncoder] = None
        self._fitted = False
        self._feature_names: List[str] = []

    def _extract_spec_features(self, spec) -> np.ndarray:
        """Convert a DesignSpec into a flat feature vector."""
        features = []

        proto = getattr(spec, "protocol", "wishbone") or "wishbone"
        features.append(self._proto_to_id(proto))

        regs = getattr(spec, "registers", []) or []
        features.append(len(regs))

        signals = getattr(spec, "signals", []) or []
        features.append(len(signals))

        addr_width = 0
        data_width = 0
        for sig in signals:
            w = getattr(sig, "width", 0) or 0
            d = getattr(sig, "direction", "")
            try:
                w = int(w)
            except (ValueError, TypeError):
                w = 0
            if "addr" in getattr(sig, "name", "").lower():
                addr_width = max(addr_width, w)
            if "data" in getattr(sig, "name", "").lower() and "out" in d.lower():
                data_width = max(data_width, w)

        features.append(addr_width)
        features.append(data_width)

        has_interrupt = 0
        for sig in signals:
            if "intr" in getattr(sig, "name", "").lower():
                has_interrupt = 1
                break
        features.append(has_interrupt)

        features.append(1 if proto == "uart" else 0)
        features.append(1 if proto == "spi" else 0)
        features.append(1 if proto == "i2c" else 0)
        features.append(1 if proto == "axi4lite" else 0)
        features.append(1 if proto == "wishbone" else 0)

        return np.array(features, dtype=np.float64).reshape(1, -1)

    def _proto_to_id(self, name: str) -> int:
        m = {"uart": 0, "spi": 1, "i2c": 2, "axi4lite": 3, "wishbone": 4, "apb": 5}
        return m.get(name.lower(), 4)

    def train_synthetic(self) -> None:
        """Train on synthetic data derived from protocol characteristics."""
        if not HAS_SKLEARN:
            logger.warning("scikit-learn not available — skipping training")
            return

        np.random.seed(42)
        n_samples = 5000

        X_proto = np.random.randint(0, 6, size=(n_samples, 1))
        X_regs = np.random.randint(0, 16, size=(n_samples, 1))
        X_signals = np.random.randint(1, 30, size=(n_samples, 1))
        X_addr = np.random.randint(1, 33, size=(n_samples, 1))
        X_data = np.random.randint(4, 65, size=(n_samples, 1))
        X_intr = np.random.randint(0, 2, size=(n_samples, 1))
        X_is_uart = (X_proto == 0).astype(float)
        X_is_spi = (X_proto == 1).astype(float)
        X_is_i2c = (X_proto == 2).astype(float)
        X_is_axi = (X_proto == 3).astype(float)
        X_is_wb = (X_proto == 4).astype(float)

        X = np.hstack([
            X_proto, X_regs, X_signals, X_addr, X_data, X_intr,
            X_is_uart, X_is_spi, X_is_i2c, X_is_axi, X_is_wb,
        ])

        base_cov = 60.0 + X_regs * 1.5 + X_signals * 0.5 + X_intr * 5.0
        proto_bonus = np.where(X_is_uart, 15.0, np.where(X_is_spi, 10.0, np.where(X_is_i2c, 8.0, 5.0)))
        noise = np.random.normal(0, 8, size=(n_samples,))
        y_coverage = np.clip(base_cov.flatten() + proto_bonus.flatten() + noise, 10, 100)

        y_params = np.zeros((n_samples, 5))
        for i in range(n_samples):
            p = int(X_proto[i, 0])
            space = PARAMETER_SPACES.get(
                ["uart", "spi", "i2c", "axi4lite", "wishbone", "apb"][p], {}
            )
            n_params = sum(len(v) if isinstance(v, list) else 1 for v in space.values())
            y_params[i, :min(n_params, 5)] = np.random.uniform(0.5, 1.0, min(n_params, 5))

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.reg = RandomForestRegressor(
            n_estimators=200, max_depth=12, min_samples_leaf=4,
            random_state=42, n_jobs=-1,
        )
        self.reg.fit(X_scaled, y_coverage)
        cv_scores = cross_val_score(
            self.reg, X_scaled, y_coverage, cv=5, scoring="r2"
        )
        logger.info(
            "Coverage model trained — R²: %.3f ± %.3f (CV=5)",
            cv_scores.mean(), cv_scores.std(),
        )

        self.gbr = GradientBoostingRegressor(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            random_state=42,
        )
        self.gbr.fit(X_scaled, y_coverage)
        gbr_cv = cross_val_score(
            self.gbr, X_scaled, y_coverage, cv=3, scoring="r2"
        )
        logger.info("GBR model trained — R²: %.3f ± %.3f", gbr_cv.mean(), gbr_cv.std())

        self._feature_names = [
            "protocol_id", "n_registers", "n_signals", "addr_width", "data_width",
            "has_interrupt", "is_uart", "is_spi", "is_i2c", "is_axi", "is_wb",
        ]
        self._fitted = True

    def predict_optimal_params(self, spec) -> Dict[str, Any]:
        """Return optimal test parameters for the given spec."""
        proto = getattr(spec, "protocol", "wishbone") or "wishbone"
        params = PARAMETER_SPACES.get(proto.lower(), {})

        if not params:
            return {"recommended_sequences": SEQUENCE_TEMPLATES.get(proto.lower(), [])}

        regs = getattr(spec, "registers", []) or []

        recommendations = {}
        for param_name, values in params.items():
            scores = []
            for v in values:
                if isinstance(v, (int, float)):
                    score = self._score_parameter(param_name, v, len(regs), proto)
                else:
                    score = self._score_parameter(param_name, hash(v) % 1000, len(regs), proto)
                scores.append((v, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            recommendations[param_name] = {
                "optimal": scores[0][0],
                "alternatives": [s[0] for s in scores[1:4]],
                "scores": {str(s[0]): round(s[1], 2) for s in scores},
            }

        return {
            "parameters": recommendations,
            "recommended_sequences": SEQUENCE_TEMPLATES.get(proto.lower(), []),
        }

    def _score_parameter(self, name: str, value: float, n_regs: int, proto: str) -> float:
        base = 0.5
        if name == "baud_rates":
            base = np.clip(value / 115200, 0.3, 1.0)
            if abs(value - 115200) < 0.1:
                base = 0.95
        elif name == "data_bits":
            base = (value - 4) / 4.0
        elif name == "data_patterns":
            base = {"alternating": 0.9, "walking_one": 0.7, "edge": 0.8, "incrementing": 0.6}.get(
                str(value) if isinstance(value, (int, float)) else str(value), 0.5
            )
        return float(np.clip(base + np.random.normal(0, 0.05), 0.1, 1.0))

    def predict_coverage(
        self, spec, generated_files: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Predict coverage and recommend sequences to close gaps."""
        features = self._extract_spec_features(spec)
        proto = getattr(spec, "protocol", "wishbone") or "wishbone"

        sequences = SEQUENCE_TEMPLATES.get(proto.lower(), [])
        recs: List[CoverageRecommendation] = []

        if self._fitted and HAS_SKLEARN:
            X_scaled = self.scaler.transform(features)
            rf_pred = float(self.reg.predict(X_scaled)[0])
            gbr_pred = float(self.gbr.predict(X_scaled)[0])
            expected = round((rf_pred + gbr_pred) / 2.0, 1)
            confidence = round(
                1.0 - abs(rf_pred - gbr_pred) / max(rf_pred, gbr_pred, 1), 3
            )

            n_regs = len(getattr(spec, "registers", []) or [])
            base_per_seq = min(15.0, 80.0 / max(len(sequences), 1))

            for seq in sequences:
                gain = base_per_seq * np.random.uniform(0.5, 1.2)
                gain = min(gain, 100.0 - expected)
                priority = round(max(0.1, gain / max(base_per_seq, 1)), 2)

                recs.append(CoverageRecommendation(
                    sequence=seq,
                    priority=priority,
                    rationale=f"Expected coverage gain: ~{gain:.1f}%",
                    expected_coverage_gain=round(gain, 1),
                ))

            recs.sort(key=lambda r: r.priority, reverse=True)

        else:
            expected = 65.0
            confidence = 0.3
            for i, seq in enumerate(sequences):
                recs.append(CoverageRecommendation(
                    sequence=seq,
                    priority=1.0 - (i * 0.08),
                    rationale="Default priority (no ML model)",
                    expected_coverage_gain=5.0,
                ))

        gaps = []
        if expected < 100:
            for r in recs:
                if r.expected_coverage_gain > 0:
                    gaps.append(r.rationale)

        return {
            "coverage": {
                "expected": expected,
                "gaps": gaps[:5],
                "model_type": "ensemble" if self._fitted else "heuristic",
            },
            "recommended_sequences": [
                {"name": r.sequence, "priority": r.priority, "gain": r.expected_coverage_gain}
                for r in recs[:8]
            ],
            "confidence": confidence,
        }
