"""
Coverage Predictor — ML ensemble that estimates UVM coverage from spec features.

Uses:
  - RandomForestRegressor   (captures non-linear interactions)
  - GradientBoostingRegressor (sequential refinement)
  - LinearRegression        (baseline trend)
Blended via Ridge meta-regressor.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("uvmgen.ml.coverage_predictor")

try:
    from sklearn.ensemble import (
        RandomForestRegressor,
        GradientBoostingRegressor,
    )
    from sklearn.linear_model import Ridge, LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class SpecFeatures:
    interface_count: int = 0
    total_signals: int = 0
    register_count: int = 0
    total_fields: int = 0
    has_output: bool = False
    has_input: bool = False
    protocol_type: str = "uart"

    def to_array(self) -> np.ndarray:
        base = np.array([
            self.interface_count,
            self.total_signals,
            self.register_count,
            self.total_fields,
            1.0 if self.has_output else 0.0,
            1.0 if self.has_input else 0.0,
        ], dtype=float)

        # protocol one-hot (up to 7 known protocols)
        protocols = ["uart", "spi", "i2c", "axi4lite", "wishbone", "apb", "ahb"]
        proto = np.zeros(len(protocols))
        if self.protocol_type in protocols:
            proto[protocols.index(self.protocol_type)] = 1.0
        else:
            proto[-1] = 1.0  # other

        complexity = (
            self.interface_count * 1.5
            + self.total_signals * 0.8
            + self.register_count * 2.0
            + self.total_fields * 0.5
        )
        complexity_feat = np.array([complexity, math.log1p(complexity)])

        return np.concatenate([base, proto, complexity_feat])

    @property
    def num_features(self) -> int:
        return len(self.to_array())

    @staticmethod
    def from_spec(spec: Any) -> "SpecFeatures":
        interfaces = getattr(spec, "interfaces", getattr(spec, "_interfaces", [])) or []
        registers = getattr(spec, "registers", getattr(spec, "_registers", [])) or []

        iface_count = len(interfaces)
        sig_count = sum(
            len(getattr(iface, "signals", getattr(iface, "_signals", getattr(iface, "ports", []))))
            for iface in interfaces
        )
        reg_count = len(registers)
        field_count = sum(
            len(getattr(r, "fields", getattr(r, "_fields", [])))
            for r in registers
        )
        has_out = any(
            getattr(s, "direction", getattr(s, "_direction", "")).lower() in ("output", "inout")
            for iface in interfaces
            for s in getattr(iface, "signals", getattr(iface, "_signals", getattr(iface, "ports", [])))
        )
        has_in = any(
            getattr(s, "direction", getattr(s, "_direction", "")).lower() == "input"
            for iface in interfaces
            for s in getattr(iface, "signals", getattr(iface, "_signals", getattr(iface, "ports", [])))
        )
        proto = getattr(spec, "protocol", getattr(spec, "_protocol", "uart")) or "uart"

        return SpecFeatures(
            interface_count=iface_count,
            total_signals=sig_count,
            register_count=reg_count,
            total_fields=field_count,
            has_output=has_out,
            has_input=has_in,
            protocol_type=proto.lower(),
        )


class CoveragePredictor:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self._fitted = False
        self._rng = random.Random(random_state)
        self._models: Dict[str, Any] = {}
        self._scaler: Any = None
        self._meta: Any = None

    def train_synthetic(self, n_samples: int = 5000) -> "CoveragePredictor":
        if not HAS_SKLEARN:
            logger.warning("sklearn not available — using heuristic fallback")
            self._fitted = True
            return self

        X, y = self._generate_synthetic_data(n_samples)
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        n_feat = X_scaled.shape[1]

        rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=min(12, max(3, n_feat * 2)),
            min_samples_leaf=3,
            random_state=self.random_state,
            n_jobs=-1,
        )
        gbr = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=min(6, max(2, n_feat)),
            learning_rate=0.08,
            subsample=0.8,
            random_state=self.random_state,
        )
        lr = LinearRegression()

        rf.fit(X_scaled, y)
        gbr.fit(X_scaled, y)
        lr.fit(X_scaled, y)

        preds = np.column_stack([
            rf.predict(X_scaled),
            gbr.predict(X_scaled),
            lr.predict(X_scaled),
        ])

        meta = Ridge(alpha=1.0)
        meta.fit(preds, y)

        self._models = {"rf": rf, "gbr": gbr, "lr": lr}
        self._meta = meta
        self._fitted = True
        logger.info(
            "CoveragePredictor trained on %d synthetic samples — %d features",
            n_samples, n_feat,
        )
        return self

    def _generate_synthetic_data(self, n: int) -> Tuple[np.ndarray, np.ndarray]:
        rows = []
        targets = []

        for _ in range(n):
            n_iface = self._rng.randint(1, 5)
            n_sig = self._rng.randint(2, 20) * n_iface
            n_reg = self._rng.randint(0, 32)
            n_fld = self._rng.randint(0, 4) * n_reg
            has_out = self._rng.random() > 0.3
            has_in = True
            proto_idx = self._rng.randint(0, 6)
            protocols = ["uart", "spi", "i2c", "axi4lite", "wishbone", "apb", "ahb"]
            proto = protocols[proto_idx]

            feat = SpecFeatures(
                interface_count=n_iface,
                total_signals=n_sig,
                register_count=n_reg,
                total_fields=n_fld,
                has_output=has_out,
                has_input=has_in,
                protocol_type=proto,
            )
            arr = feat.to_array()
            rows.append(arr)

            # Coverage ground truth: synthetic formula with noise
            base = 50.0
            base += n_iface * 2.5
            base += min(n_sig, 40) * 0.5
            base += min(n_reg, 16) * 1.2
            base += min(n_fld, 32) * 0.3
            base += 5.0 if has_out else 0.0
            base -= n_iface * 1.0  # complexity penalty
            proto_boost = {"uart": 5, "spi": 3, "i2c": 4, "axi4lite": 2, "wishbone": 3, "apb": 4, "ahb": 2}.get(proto, 0)
            base += proto_boost
            noise = self._rng.gauss(0, 6)
            cov = max(10.0, min(99.0, base + noise))
            targets.append(cov / 100.0)

        return np.array(rows), np.array(targets)

    def predict_coverage(self, spec: Any, _generated_files: Optional[Dict] = None) -> Dict[str, Any]:
        """Predict coverage % and recommend sequences to close gaps."""
        feat = SpecFeatures.from_spec(spec)

        if not self._fitted or not HAS_SKLEARN:
            return self._heuristic_prediction(feat)

        X = feat.to_array().reshape(1, -1)
        X_scaled = self._scaler.transform(X)

        preds = np.column_stack([
            self._models["rf"].predict(X_scaled),
            self._models["gbr"].predict(X_scaled),
            self._models["lr"].predict(X_scaled),
        ])
        blended = float(self._meta.predict(preds)[0])
        blended = max(0.1, min(0.99, blended))

        rf_conf = float(self._models["rf"].predict(X_scaled)[0])
        gbr_conf = float(self._models["gbr"].predict(X_scaled)[0])
        lr_conf = float(self._models["lr"].predict(X_scaled)[0])

        coverage_pct = blended * 100.0
        rf_pct = rf_conf * 100.0
        gbr_pct = gbr_conf * 100.0

        gaps = self._predict_gaps(feat, coverage_pct)
        recommended = self._recommend_sequences(feat, gaps)

        return {
            "coverage": {
                "expected": round(coverage_pct, 1),
                "rf_estimate": round(rf_pct, 1),
                "gbr_estimate": round(gbr_pct, 1),
                "lr_estimate": round(lr_conf * 100.0, 1),
                "gaps": gaps,
                "confidence": round(1.0 - abs(rf_pct - gbr_pct) / 100.0, 2),
            },
            "recommended_sequences": recommended,
        }

    def predict_optimal_params(self, spec: Any) -> Dict[str, Any]:
        """Suggest ML model params to maximize coverage for this spec."""
        feat = SpecFeatures.from_spec(spec)

        complexity = (
            feat.interface_count * 1.5
            + feat.total_signals * 0.8
            + feat.register_count * 2.0
            + feat.total_fields * 0.5
        )

        if complexity < 10:
            return {"model_type": "template", "max_iterations": 1, "rl_strategy": "epsilon_greedy"}
        elif complexity < 30:
            return {"model_type": "v2", "max_iterations": 3, "rl_strategy": "ucb"}
        elif complexity < 60:
            return {"model_type": "v2", "max_iterations": 5, "rl_strategy": "thompson"}
        else:
            return {"model_type": "v2", "max_iterations": 10, "rl_strategy": "softmax"}

    def _heuristic_prediction(self, feat: SpecFeatures) -> Dict[str, Any]:
        complexity = (
            feat.interface_count * 1.5
            + feat.total_signals * 0.8
            + feat.register_count * 2.0
            + feat.total_fields * 0.5
        )
        base = min(95.0, 45.0 + complexity * 0.5 + (5.0 if feat.has_output else 0.0))
        gaps = []
        if feat.register_count > 8:
            gaps.append("high_reg_count")
        if feat.total_signals > 20:
            gaps.append("high_signal_count")
        return {
            "coverage": {
                "expected": round(base, 1),
                "gaps": gaps,
                "confidence": 0.5,
            },
            "recommended_sequences": self._recommend_sequences(feat, gaps),
        }

    def _predict_gaps(self, feat: SpecFeatures, coverage_pct: float) -> List[str]:
        gaps = []
        if coverage_pct < 60:
            gaps.append("critical_low_coverage")
        if feat.register_count > 16:
            gaps.append("high_register_count")
        if feat.total_signals > 30:
            gaps.append("high_signal_count")
        if feat.interface_count > 3:
            gaps.append("multi_interface_coordination")
        return gaps

    def _recommend_sequences(self, feat: SpecFeatures, gaps: List[str]) -> List[str]:
        seqs = ["uart_base_seq"]
        if "critical_low_coverage" in gaps:
            seqs.append("uart_coverage_seq")
        if "high_register_count" in gaps:
            seqs.append("uart_random_regs_seq")
        if feat.total_signals > 0:
            seqs.append("uart_loopback_seq")
        if "multi_interface_coordination" in gaps:
            seqs.append("uart_interrupt_seq")
        return seqs


# Global singleton
coverage_predictor = CoveragePredictor()
