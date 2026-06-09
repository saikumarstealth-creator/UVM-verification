from __future__ import annotations

import json
import logging
import math
import random
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("uvmgen.ml.coverage_predictor")

HAS_SKLEARN = False
HAS_XGBOOST = False
HAS_LIGHTGBM = False
HAS_OPTUNA = False

try:
    from sklearn.ensemble import (
        RandomForestRegressor,
        GradientBoostingRegressor,
    )
    from sklearn.linear_model import Ridge, LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score, KFold
    from sklearn.neural_network import MLPRegressor
    HAS_SKLEARN = True
except ImportError:
    pass

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    pass

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    pass

try:
    import optuna
    HAS_OPTUNA = True
except ImportError:
    pass


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
        protocols = ["uart", "spi", "i2c", "axi4lite", "wishbone", "apb", "ahb"]
        proto = np.zeros(len(protocols))
        if self.protocol_type in protocols:
            proto[protocols.index(self.protocol_type)] = 1.0
        else:
            proto[-1] = 1.0
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
    def from_spec(spec: Any) -> SpecFeatures:
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


BOX_MULLER_CACHE: Optional[float] = None


def _box_muller() -> Tuple[float, float]:
    global BOX_MULLER_CACHE
    if BOX_MULLER_CACHE is not None:
        z = BOX_MULLER_CACHE
        BOX_MULLER_CACHE = None
        return z, 0.0
    u1 = random.random()
    u2 = random.random()
    r = math.sqrt(-2.0 * math.log(u1))
    theta = 2.0 * math.pi * u2
    z1 = r * math.cos(theta)
    z2 = r * math.sin(theta)
    BOX_MULLER_CACHE = z2
    return z1, 1.0


class ConformalPredictor:
    def __init__(self, coverage: float = 0.90):
        self.coverage = coverage
        self.calibration_scores: List[float] = []
        self.q_hat: float = 0.0
        self.calibrated: bool = False

    def calibrate(self, residuals: List[float]) -> None:
        if not residuals:
            return
        n = len(residuals)
        alpha = 1.0 - self.coverage
        q_level = min(1.0, (n + 1) * (1 - alpha) / n)
        sorted_res = sorted(residuals)
        idx = int(np.ceil(q_level * n)) - 1
        idx = max(0, min(idx, n - 1))
        self.q_hat = sorted_res[idx]
        self.calibrated = True
        logger.debug("Conformal calibrated: q_hat=%.4f (n=%d, coverage=%.2f)", self.q_hat, n, self.coverage)

    def predict_interval(self, point_prediction: float) -> Tuple[float, float]:
        if not self.calibrated:
            return point_prediction * 0.85, point_prediction * 1.15
        return point_prediction - self.q_hat, point_prediction + self.q_hat


class CoveragePredictor:
    FEATURE_NAMES = [
        "interface_count", "total_signals", "register_count", "total_fields",
        "has_output", "has_input",
        "proto_uart", "proto_spi", "proto_i2c", "proto_axi4lite",
        "proto_wishbone", "proto_apb", "proto_ahb",
        "complexity", "log_complexity",
    ]

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self._fitted = False
        self._rng = random.Random(random_state)
        self._models: Dict[str, Any] = {}
        self._scaler: Any = None
        self._meta: Any = None
        self._calibrator: Any = None
        self._conformal = ConformalPredictor(coverage=0.90)
        self._training_data: List[Tuple[np.ndarray, float]] = []
        self._feature_importances: Optional[Dict[str, float]] = None
        self._version: int = 1
        self._train_timestamp: Optional[str] = None
        self._best_score: float = 0.0
        self._best_params: Dict[str, Any] = {}

    def train_synthetic(self, n_samples: int = 100000) -> CoveragePredictor:
        if not HAS_SKLEARN:
            logger.warning("sklearn not available -- using heuristic fallback")
            self._fitted = True
            return self
        X, y = self._generate_synthetic_data(n_samples)
        self._fit_ensemble(X, y)
        logger.info(
            "CoveragePredictor v%d trained on %d synthetic samples (%d features, %d models)",
            self._version, n_samples, X.shape[1], len(self._models),
        )
        return self

    def train_real(
        self, features: List[np.ndarray], targets: List[float], auto_tune: bool = False
    ) -> CoveragePredictor:
        if not HAS_SKLEARN:
            return self
        if not features:
            logger.warning("No real training data provided")
            return self
        X = np.array(features)
        y = np.array(targets)
        self._training_data.extend(zip(features, targets))
        if len(self._training_data) > 100000:
            self._training_data = self._training_data[-100000:]
        self._fit_ensemble(X, y)

        if auto_tune and len(X) >= 50 and HAS_OPTUNA:
            try:
                best = self._auto_tune_hyperparams(X, y)
                self._best_params = best
                logger.info("Auto-tuned hyperparams: %s", best)
            except Exception as e:
                logger.warning("Auto-tuning failed: %s", e)

        self._version += 1
        self._train_timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(
            "CoveragePredictor v%d trained on %d real samples", self._version, len(features)
        )
        return self

    def update_online(self, feature: np.ndarray, actual_coverage: float) -> None:
        self._training_data.append((feature, actual_coverage))
        if len(self._training_data) > 100000:
            self._training_data = self._training_data[-100000:]

        decay_factor = max(0.5, 1.0 - (len(self._training_data) / 100000))
        for model_name, model in self._models.items():
            if hasattr(model, 'warm_start') and model.warm_start:
                try:
                    X_batch = feature.reshape(1, -1)
                    X_batch_scaled = self._scaler.transform(X_batch)
                    model.fit(X_batch_scaled, np.array([actual_coverage]))
                except Exception:
                    pass

        if len(self._training_data) % 25 == 0:
            X = np.array([d[0] for d in self._training_data])
            y = np.array([d[1] for d in self._training_data])
            self._fit_ensemble(X, y)
            self._version += 1
            logger.debug("Online update: CoveragePredictor v%d (buffer=%d)", self._version, len(self._training_data))

    def _auto_tune_hyperparams(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        X_s = self._scaler.transform(X)

        def objective(trial):
            params = {
                "rf_n_estimators": trial.suggest_int("rf_n_estimators", 50, 300),
                "rf_max_depth": trial.suggest_int("rf_max_depth", 3, 20),
                "rf_min_samples_leaf": trial.suggest_int("rf_min_samples_leaf", 2, 8),
                "gbr_n_estimators": trial.suggest_int("gbr_n_estimators", 50, 200),
                "gbr_max_depth": trial.suggest_int("gbr_max_depth", 3, 10),
                "gbr_learning_rate": trial.suggest_float("gbr_learning_rate", 0.01, 0.3, log=True),
            }
            rf = RandomForestRegressor(
                n_estimators=params["rf_n_estimators"],
                max_depth=params["rf_max_depth"],
                min_samples_leaf=params["rf_min_samples_leaf"],
                random_state=self.random_state, n_jobs=-1,
            )
            gbr = GradientBoostingRegressor(
                n_estimators=params["gbr_n_estimators"],
                max_depth=params["gbr_max_depth"],
                learning_rate=params["gbr_learning_rate"],
                subsample=0.85, random_state=self.random_state,
            )
            kf = KFold(n_splits=3, shuffle=True, random_state=self.random_state)
            scores = []
            for train_idx, val_idx in kf.split(X_s):
                rf_c = RandomForestRegressor(**rf.get_params())
                gbr_c = GradientBoostingRegressor(**gbr.get_params())
                rf_c.fit(X_s[train_idx], y[train_idx])
                gbr_c.fit(X_s[train_idx], y[train_idx])
                lr_c = LinearRegression()
                lr_c.fit(X_s[train_idx], y[train_idx])
                preds = np.column_stack([
                    rf_c.predict(X_s[val_idx]),
                    gbr_c.predict(X_s[val_idx]),
                    lr_c.predict(X_s[val_idx]),
                ])
                meta = Ridge(alpha=1.0)
                meta.fit(preds, y[val_idx])
                scores.append(meta.score(preds, y[val_idx]))
            return np.mean(scores)

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=self.random_state))
        study.optimize(objective, n_trials=20, timeout=120)
        return study.best_params

    def _fit_ensemble(self, X: np.ndarray, y: np.ndarray) -> None:
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        n_feat = X_scaled.shape[1]
        n_samp = X_scaled.shape[0]

        rf = RandomForestRegressor(
            n_estimators=min(300, max(50, n_feat * 12)),
            max_depth=min(20, max(3, n_feat * 2)),
            min_samples_leaf=max(2, min(8, n_samp // 100)),
            random_state=self.random_state,
            n_jobs=-1,
            warm_start=False,
        )
        gbr = GradientBoostingRegressor(
            n_estimators=min(200, max(50, n_feat * 10)),
            max_depth=min(10, max(3, n_feat)),
            learning_rate=0.06,
            subsample=0.8,
            random_state=self.random_state,
        )
        lr = LinearRegression()

        mlp = MLPRegressor(
            hidden_layer_sizes=(max(16, n_feat * 2), max(8, n_feat)),
            activation='relu',
            solver='adam',
            alpha=0.001,
            max_iter=500,
            early_stopping=True,
            random_state=self.random_state,
        )

        try:
            rf_cv = cross_val_score(rf, X_scaled, y, cv=min(3, n_samp // 20))
            gbr_cv = cross_val_score(gbr, X_scaled, y, cv=min(3, n_samp // 20))
            logger.debug("RF CV: %.3f +/- %.3f, GBR CV: %.3f +/- %.3f",
                         rf_cv.mean(), rf_cv.std(), gbr_cv.mean(), gbr_cv.std())
        except Exception:
            pass

        rf.fit(X_scaled, y)
        gbr.fit(X_scaled, y)
        lr.fit(X_scaled, y)
        mlp.fit(X_scaled, y)

        base_preds = np.column_stack([
            rf.predict(X_scaled),
            gbr.predict(X_scaled),
            lr.predict(X_scaled),
            mlp.predict(X_scaled),
        ])
        meta = Ridge(alpha=1.0)
        meta.fit(base_preds, y)

        self._models = {"rf": rf, "gbr": gbr, "lr": lr, "mlp": mlp}

        if HAS_XGBOOST:
            try:
                xgb_model = xgb.XGBRegressor(
                    n_estimators=min(200, n_feat * 10),
                    max_depth=min(8, n_feat),
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=self.random_state,
                )
                xgb_model.fit(X_scaled, y)
                self._models["xgb"] = xgb_model
            except Exception as e:
                logger.debug("XGBoost training skipped: %s", e)

        if HAS_LIGHTGBM:
            try:
                lgb_model = lgb.LGBMRegressor(
                    n_estimators=min(200, n_feat * 10),
                    max_depth=min(8, n_feat),
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=self.random_state,
                    verbose=-1,
                )
                lgb_model.fit(X_scaled, y)
                self._models["lgb"] = lgb_model
            except Exception as e:
                logger.debug("LightGBM training skipped: %s", e)

        self._meta = meta
        self._fitted = True
        self._compute_feature_importance(X_scaled, y, rf, gbr, lr)
        self._train_timestamp = datetime.now(timezone.utc).isoformat()

        try:
            residuals = np.abs(y - meta.predict(base_preds))
            self._conformal.calibrate(residuals.tolist())
        except Exception as e:
            logger.debug("Conformal calibration skipped: %s", e)

        train_score = meta.score(base_preds, y)
        if train_score > self._best_score:
            self._best_score = train_score
            logger.debug("New best ensemble score: %.4f", train_score)

    def _compute_feature_importance(
        self, X: np.ndarray, y: np.ndarray,
        rf: Any, gbr: Any, lr: Any
    ) -> None:
        try:
            rf_imp = rf.feature_importances_
            gbr_imp = gbr.feature_importances_
            lr_imp = np.abs(lr.coef_) if hasattr(lr, 'coef_') else np.ones(len(self.FEATURE_NAMES))
            combined = {
                name: (rf_imp[i] * 0.35 + gbr_imp[i] * 0.35 + lr_imp[i] * 0.3)
                for i, name in enumerate(self.FEATURE_NAMES[:len(rf_imp)])
            }
            total = sum(combined.values()) or 1.0
            self._feature_importances = {k: v / total for k, v in combined.items()}
        except Exception as e:
            logger.debug("Feature importance computation failed: %s", e)
            self._feature_importances = {name: 1.0 / len(self.FEATURE_NAMES) for name in self.FEATURE_NAMES}

    def _generate_synthetic_data(self, n: int) -> Tuple[np.ndarray, np.ndarray]:
        rows = []
        targets = []
        protocols = ["uart", "spi", "i2c", "axi4lite", "wishbone", "apb", "ahb"]
        for _ in range(n):
            n_iface = self._rng.randint(1, 6)
            n_sig = self._rng.randint(2, 32) * n_iface
            n_reg = self._rng.randint(0, 40)
            n_fld = self._rng.randint(0, 5) * max(1, n_reg)
            has_out = self._rng.random() > 0.25
            has_in = True
            proto_idx = self._rng.randint(0, 6)
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
            rows.append(feat.to_array())

            base = 45.0
            base += n_iface * 3.0
            base += min(n_sig, 50) * 0.4
            base += min(n_reg, 20) * 1.5
            base += min(n_fld, 40) * 0.25
            base += 8.0 if has_out else 0.0
            base -= max(0, n_iface - 2) * 2.0

            proto_boost = {
                "uart": 8, "spi": 5, "i2c": 6, "axi4lite": 3,
                "wishbone": 4, "apb": 6, "ahb": 3
            }.get(proto, 0)
            base += proto_boost

            if n_reg > 0:
                base += random.gauss(2, 1)
            if n_fld > 20:
                base += random.gauss(-3, 1.5)

            z1, _ = _box_muller()
            noise = z1 * 5
            cov = max(10.0, min(99.0, base + noise))

            targets.append(cov / 100.0)
        return np.array(rows), np.array(targets)

    def predict_coverage(
        self, spec: Any, _generated_files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        if not self._fitted and HAS_SKLEARN:
            try:
                self.train_synthetic(n_samples=2000)
            except Exception:
                pass

        feat = SpecFeatures.from_spec(spec)
        if not self._fitted or not HAS_SKLEARN:
            return self._heuristic_prediction(feat)

        X = feat.to_array().reshape(1, -1)
        X_scaled = self._scaler.transform(X)

        model_preds = {}
        for name, model in self._models.items():
            try:
                model_preds[name] = float(model.predict(X_scaled)[0])
            except Exception:
                continue

        if not model_preds:
            return self._heuristic_prediction(feat)

        if len(model_preds) >= 3:
            pred_array = np.array([model_preds[n] for n in ["rf", "gbr", "lr"] if n in model_preds]).reshape(1, -1)
            if pred_array.shape[1] >= 2:
                blended = float(self._meta.predict(pred_array)[0])
            else:
                blended = np.mean(list(model_preds.values()))
        else:
            blended = np.mean(list(model_preds.values()))

        blended = max(0.1, min(0.99, blended))
        coverage_pct = blended * 100.0

        values = list(model_preds.values())
        ensemble_std = float(np.std(values)) * 100.0
        lower_ci, upper_ci = self._conformal.predict_interval(coverage_pct / 100.0)
        lower_ci = max(0.0, lower_ci * 100.0)
        upper_ci = min(100.0, upper_ci * 100.0)

        confidence = max(0.1, min(0.99, 1.0 - ensemble_std / 60.0))

        gaps = self._predict_gaps(feat, coverage_pct)
        recommended = self._recommend_sequences(feat, gaps)
        ood_score = self._detect_ood(feat)

        per_model = {k: round(v * 100.0, 1) for k, v in sorted(model_preds.items())}

        return {
            "coverage": {
                "expected": round(coverage_pct, 1),
                "lower_90ci": round(lower_ci, 1),
                "upper_90ci": round(upper_ci, 1),
                "per_model": per_model,
                "ensemble_size": len(model_preds),
                "gaps": gaps,
                "confidence": round(confidence, 2),
                "ensemble_std": round(ensemble_std, 2),
                "ood_score": round(ood_score, 3),
                "conformal_calibrated": self._conformal.calibrated,
            },
            "recommended_sequences": recommended,
            "feature_importances": self._feature_importances,
            "model_version": self._version,
            "train_timestamp": self._train_timestamp,
            "best_score": round(self._best_score, 4),
        }

    def _detect_ood(self, feat: SpecFeatures) -> float:
        if not self._training_data:
            return 0.0
        try:
            X_train = np.array([d[0] for d in self._training_data])
            mean = np.mean(X_train, axis=0)
            cov = np.cov(X_train.T)
            cov += np.eye(cov.shape[0]) * 1e-6
            inv_cov = np.linalg.inv(cov)
            x = feat.to_array()
            diff = x - mean
            mahalanobis = np.sqrt(float(diff @ inv_cov @ diff.T))
            return min(1.0, mahalanobis / 12.0)
        except Exception:
            return 0.0

    def predict_optimal_params(self, spec: Any) -> Dict[str, Any]:
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
            return {"model_type": "v2", "max_iterations": 10, "rl_strategy": "softmax", "use_llm": True}

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
                "lower_90ci": round(max(0.0, base - 10), 1),
                "upper_90ci": round(min(100.0, base + 10), 1),
                "gaps": gaps,
                "confidence": 0.5,
                "ensemble_std": 5.0,
                "ood_score": 0.0,
                "per_model": {"heuristic": round(base / 100.0, 3)},
                "ensemble_size": 1,
                "conformal_calibrated": False,
            },
            "recommended_sequences": self._recommend_sequences(feat, gaps),
            "feature_importances": None,
            "model_version": 0,
            "best_score": 0.0,
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
        seqs = [f"{feat.protocol_type}_base_seq"]
        if "critical_low_coverage" in gaps:
            seqs.append(f"{feat.protocol_type}_coverage_seq")
        if "high_register_count" in gaps:
            seqs.append(f"{feat.protocol_type}_random_regs_seq")
        if feat.total_signals > 0:
            seqs.append(f"{feat.protocol_type}_loopback_seq")
        if "multi_interface_coordination" in gaps:
            seqs.append(f"{feat.protocol_type}_interrupt_seq")
        return seqs

    def get_feature_importance(self) -> Dict[str, float]:
        return self._feature_importances or {}

    def get_model_summary(self) -> Dict[str, Any]:
        return {
            "version": self._version,
            "fitted": self._fitted,
            "models": list(self._models.keys()),
            "training_data_size": len(self._training_data),
            "best_score": self._best_score,
            "train_timestamp": self._train_timestamp,
            "conformal_calibrated": self._conformal.calibrated,
            "feature_importances": self._feature_importances,
        }

    def save(self, path: str) -> None:
        state = {
            "version": self._version,
            "fitted": self._fitted,
            "random_state": self.random_state,
            "feature_importances": self._feature_importances,
            "train_timestamp": self._train_timestamp,
            "best_score": self._best_score,
            "best_params": self._best_params,
            "scaler": pickle.dumps(self._scaler) if self._scaler else None,
            "models": {k: pickle.dumps(v) for k, v in self._models.items()},
            "meta": pickle.dumps(self._meta) if self._meta else None,
            "conformal": {
                "coverage": self._conformal.coverage,
                "q_hat": self._conformal.q_hat,
                "calibrated": self._conformal.calibrated,
                "calibration_scores": self._conformal.calibration_scores,
            },
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(state, f)
        logger.info("CoveragePredictor v%d saved to %s", self._version, path)

    @classmethod
    def load(cls, path: str) -> CoveragePredictor:
        with open(path, "rb") as f:
            state = pickle.load(f)
        predictor = cls(random_state=state.get("random_state", 42))
        predictor._version = state.get("version", 1)
        predictor._fitted = state.get("fitted", False)
        predictor._feature_importances = state.get("feature_importances")
        predictor._train_timestamp = state.get("train_timestamp")
        predictor._best_score = state.get("best_score", 0.0)
        predictor._best_params = state.get("best_params", {})
        if state.get("scaler"):
            predictor._scaler = pickle.loads(state["scaler"])
        for k, v in state.get("models", {}).items():
            predictor._models[k] = pickle.loads(v)
        if state.get("meta"):
            predictor._meta = pickle.loads(state["meta"])
        conformal_data = state.get("conformal", {})
        predictor._conformal.coverage = conformal_data.get("coverage", 0.90)
        predictor._conformal.q_hat = conformal_data.get("q_hat", 0.0)
        predictor._conformal.calibrated = conformal_data.get("calibrated", False)
        predictor._conformal.calibration_scores = conformal_data.get("calibration_scores", [])
        return predictor


coverage_predictor = CoveragePredictor()
