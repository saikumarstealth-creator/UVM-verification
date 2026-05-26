import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
import os
from datetime import datetime

logger = logging.getLogger("uvmgen.ml.learning")


@dataclass
class ValidationFeedback:
    design_name: str
    file_name: str
    file_type: str
    passed: bool
    errors: List[str]
    warnings: List[str]
    score: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_name": self.design_name,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "score": self.score,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationFeedback":
        return cls(
            design_name=d.get("design_name", "unknown"),
            file_name=d.get("file_name", "unknown"),
            file_type=d.get("file_type", "unknown"),
            passed=d.get("passed", False),
            errors=d.get("errors", []),
            warnings=d.get("warnings", []),
            score=d.get("score", 0.0),
            timestamp=d.get("timestamp", datetime.now().isoformat()),
            metadata=d.get("metadata", {}),
        )


@dataclass
class GenerationHistory:
    design_name: str
    generation_source: str
    spec_hash: str
    feedback_list: List[ValidationFeedback]
    success_rate: float = 0.0
    avg_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_name": self.design_name,
            "generation_source": self.generation_source,
            "spec_hash": self.spec_hash,
            "feedback_list": [f.to_dict() for f in self.feedback_list],
            "success_rate": self.success_rate,
            "avg_score": self.avg_score,
            "timestamp": self.timestamp,
        }


class PatternLearner:
    def __init__(self):
        self._error_patterns: Dict[str, int] = defaultdict(int)
        self._success_patterns: Dict[str, int] = defaultdict(int)
        self._file_type_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"success": 0, "total": 0, "errors": defaultdict(int)}
        )
        self._protocol_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"success": 0, "total": 0}
        )

    def record_error(self, error_msg: str, file_type: str = "unknown"):
        patterns = self._extract_patterns(error_msg)
        for p in patterns:
            self._error_patterns[p] += 1
        self._file_type_stats[file_type]["errors"][error_msg[:100]] += 1

    def record_success(self, file_type: str = "unknown", protocol: str = "unknown"):
        self._file_type_stats[file_type]["success"] += 1
        self._file_type_stats[file_type]["total"] += 1
        self._protocol_stats[protocol]["success"] += 1
        self._protocol_stats[protocol]["total"] += 1

    def record_attempt(self, file_type: str = "unknown", protocol: str = "unknown"):
        self._file_type_stats[file_type]["total"] += 1
        self._protocol_stats[protocol]["total"] += 1

    def _extract_patterns(self, text: str) -> List[str]:
        import re

        patterns = []

        uvm_patterns = [
            (r"uvm_fatal", "uvm_fatal"),
            (r"uvm_error", "uvm_error"),
            (r"uvm_component_utils", "missing_uvm_macro"),
            (r"uvm_object_utils", "missing_uvm_macro"),
            (r"build_phase", "phase_issue"),
            (r"connect_phase", "phase_issue"),
            (r"run_phase", "phase_issue"),
        ]

        for pattern, name in uvm_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                patterns.append(name)

        syntax_patterns = [
            (r"missing.*semicolon", "missing_semicolon"),
            (r"unbalanced.*parenthes", "unbalanced_parentheses"),
            (r"unbalanced.*brace", "unbalanced_braces"),
            (r"unbalanced.*bracket", "unbalanced_brackets"),
            (r"mismatch.*begin", "mismatched_blocks"),
            (r"syntax error", "syntax_error"),
        ]

        for pattern, name in syntax_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                patterns.append(name)

        if not patterns:
            patterns.append("unknown_error")

        return patterns

    def get_common_errors(self, top_n: int = 10) -> List[Tuple[str, int]]:
        sorted_errors = sorted(
            self._error_patterns.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_errors[:top_n]

    def get_file_type_success_rate(self, file_type: str) -> float:
        stats = self._file_type_stats.get(file_type, {})
        total = stats.get("total", 0)
        if total == 0:
            return 0.5
        return stats.get("success", 0) / total

    def get_protocol_success_rate(self, protocol: str) -> float:
        stats = self._protocol_stats.get(protocol, {})
        total = stats.get("total", 0)
        if total == 0:
            return 0.5
        return stats.get("success", 0) / total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_patterns": dict(self._error_patterns),
            "file_type_stats": {
                ft: {
                    "success": s["success"],
                    "total": s["total"],
                    "errors": dict(s["errors"]),
                }
                for ft, s in self._file_type_stats.items()
            },
            "protocol_stats": dict(self._protocol_stats),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PatternLearner":
        learner = cls()
        learner._error_patterns = defaultdict(int, d.get("error_patterns", {}))

        for ft, s in d.get("file_type_stats", {}).items():
            learner._file_type_stats[ft] = {
                "success": s.get("success", 0),
                "total": s.get("total", 0),
                "errors": defaultdict(int, s.get("errors", {})),
            }

        for proto, s in d.get("protocol_stats", {}).items():
            learner._protocol_stats[proto] = {
                "success": s.get("success", 0),
                "total": s.get("total", 0),
            }

        return learner


class ReinforcementLearner:
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.9):
        self._learning_rate = learning_rate
        self._discount_factor = discount_factor
        self._q_values: Dict[str, float] = defaultdict(lambda: 0.5)
        self._visit_counts: Dict[str, int] = defaultdict(int)

    def _get_state_key(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
    ) -> str:
        return f"{protocol}:{file_type}:{generation_source}"

    def get_action_value(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
    ) -> float:
        key = self._get_state_key(protocol, file_type, generation_source)
        return self._q_values[key]

    def update(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
        reward: float,
    ):
        key = self._get_state_key(protocol, file_type, generation_source)
        old_value = self._q_values[key]
        self._visit_counts[key] += 1
        self._q_values[key] = (
            old_value + self._learning_rate * (reward - old_value)
        )

    def select_best_action(
        self,
        protocol: str,
        file_type: str,
        available_sources: List[str],
        epsilon: float = 0.1,
    ) -> Tuple[str, float]:
        import random

        if random.random() < epsilon and len(available_sources) > 1:
            chosen = random.choice(available_sources)
            return chosen, self.get_action_value(protocol, file_type, chosen)

        best_source = available_sources[0]
        best_value = -1.0

        for source in available_sources:
            value = self.get_action_value(protocol, file_type, source)
            if value > best_value:
                best_value = value
                best_source = source

        return best_source, best_value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "learning_rate": self._learning_rate,
            "discount_factor": self._discount_factor,
            "q_values": dict(self._q_values),
            "visit_counts": dict(self._visit_counts),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReinforcementLearner":
        learner = cls(
            learning_rate=d.get("learning_rate", 0.1),
            discount_factor=d.get("discount_factor", 0.9),
        )
        learner._q_values = defaultdict(lambda: 0.5)
        learner._q_values.update(d.get("q_values", {}))
        learner._visit_counts = defaultdict(int)
        learner._visit_counts.update(d.get("visit_counts", {}))
        return learner


class LearningModule:
    def __init__(self, storage_path: Optional[str] = None):
        self._storage_path = storage_path
        self._pattern_learner = PatternLearner()
        self._rl_learner = ReinforcementLearner()
        self._history: List[GenerationHistory] = []
        self._total_generations = 0
        self._successful_generations = 0

        if storage_path:
            self._load_from_storage()

    def record_feedback(
        self,
        design_name: str,
        generation_source: str,
        spec_dict: Dict[str, Any],
        validation_results: Dict[str, Any],
    ):
        import hashlib
        import json

        spec_str = json.dumps(spec_dict, sort_keys=True)
        spec_hash = hashlib.md5(spec_str.encode()).hexdigest()[:12]

        protocol = spec_dict.get("protocol", "unknown")

        feedback_list = []

        files_data = validation_results.get("files", [])

        if isinstance(files_data, dict):
            for file_name, file_info in files_data.items():
                file_type = file_info.get("type", "unknown")
                passed = file_info.get("passed", True)
                errors = file_info.get("errors", [])
                warnings = file_info.get("warnings", [])
                score = file_info.get("score", 0.5)

                feedback = ValidationFeedback(
                    design_name=design_name,
                    file_name=file_name,
                    file_type=file_type,
                    passed=passed,
                    errors=errors,
                    warnings=warnings,
                    score=score,
                )
                feedback_list.append(feedback)

                if passed:
                    self._pattern_learner.record_success(file_type, protocol)
                    reward = 1.0
                else:
                    for err in errors:
                        self._pattern_learner.record_error(err, file_type)
                    reward = -0.5

                self._pattern_learner.record_attempt(file_type, protocol)
                self._rl_learner.update(protocol, file_type, generation_source, reward)

        elif isinstance(files_data, list):
            for file_info in files_data:
                file_name = file_info.get("filename", "unknown")
                file_type = file_info.get("file_type", "unknown")
                passed = file_info.get("passed", True)

                issues = file_info.get("issues", [])
                errors = []
                warnings = []
                for issue in issues:
                    severity = issue.get("severity", "warning")
                    message = issue.get("message", "")
                    if severity == "error":
                        errors.append(message)
                    else:
                        warnings.append(message)

                error_count = file_info.get("error_count", 0)
                warning_count = file_info.get("warning_count", 0)

                if error_count > 0:
                    passed = False

                score = 1.0 if passed else 0.3
                if passed and warning_count == 0:
                    score = 1.0
                elif passed and warning_count > 0:
                    score = 0.7

                feedback = ValidationFeedback(
                    design_name=design_name,
                    file_name=file_name,
                    file_type=file_type,
                    passed=passed,
                    errors=errors,
                    warnings=warnings,
                    score=score,
                )
                feedback_list.append(feedback)

                if passed:
                    self._pattern_learner.record_success(file_type, protocol)
                    reward = 1.0
                else:
                    for err in errors:
                        self._pattern_learner.record_error(err, file_type)
                    reward = -0.5

                self._pattern_learner.record_attempt(file_type, protocol)
                self._rl_learner.update(protocol, file_type, generation_source, reward)

        all_passed = all(f.passed for f in feedback_list)
        avg_score = sum(f.score for f in feedback_list) / len(feedback_list) if feedback_list else 0.0

        history = GenerationHistory(
            design_name=design_name,
            generation_source=generation_source,
            spec_hash=spec_hash,
            feedback_list=feedback_list,
            success_rate=1.0 if all_passed else 0.0,
            avg_score=avg_score,
        )
        self._history.append(history)

        self._total_generations += 1
        if all_passed:
            self._successful_generations += 1

        if self._storage_path:
            self._save_to_storage()

    def select_best_generation_strategy(
        self,
        spec_dict: Dict[str, Any],
        file_type: str,
        available_sources: List[str],
    ) -> Tuple[str, float]:
        protocol = spec_dict.get("protocol", "unknown")

        best_source, best_value = self._rl_learner.select_best_action(
            protocol=protocol,
            file_type=file_type,
            available_sources=available_sources,
            epsilon=0.05,
        )

        return best_source, best_value

    def get_generation_hints(
        self,
        spec_dict: Dict[str, Any],
        file_type: str,
    ) -> Dict[str, Any]:
        protocol = spec_dict.get("protocol", "unknown")

        common_errors = self._pattern_learner.get_common_errors(5)
        file_success_rate = self._pattern_learner.get_file_type_success_rate(file_type)
        protocol_success_rate = self._pattern_learner.get_protocol_success_rate(protocol)

        return {
            "common_errors": common_errors,
            "file_type_success_rate": file_success_rate,
            "protocol_success_rate": protocol_success_rate,
            "recommendations": self._generate_recommendations(
                common_errors,
                file_success_rate,
                protocol_success_rate,
            ),
        }

    def _generate_recommendations(
        self,
        common_errors: List[Tuple[str, int]],
        file_success_rate: float,
        protocol_success_rate: float,
    ) -> List[str]:
        recommendations = []

        for error_pattern, count in common_errors[:3]:
            if count > 0:
                if "semicolon" in error_pattern:
                    recommendations.append(
                        "Ensure all statements end with semicolons"
                    )
                elif "parenthes" in error_pattern:
                    recommendations.append(
                        "Check for balanced parentheses"
                    )
                elif "brace" in error_pattern:
                    recommendations.append(
                        "Check for balanced begin/end blocks"
                    )
                elif "uvm_macro" in error_pattern:
                    recommendations.append(
                        "Add UVM factory registration macros (uvm_component_utils/uvm_object_utils)"
                    )
                elif "phase" in error_pattern:
                    recommendations.append(
                        "Ensure proper UVM phase implementation"
                    )

        if file_success_rate < 0.7:
            recommendations.append(
                "Consider using retrieval-based generation for this file type"
            )

        if protocol_success_rate < 0.7:
            recommendations.append(
                "Add protocol-specific templates may improve quality"
            )

        if not recommendations:
            recommendations.append(
                "No specific recommendations - generation should work well"
            )

        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_generations": self._total_generations,
            "successful_generations": self._successful_generations,
            "success_rate": (
                self._successful_generations / self._total_generations
                if self._total_generations > 0
                else 0.0
            ),
            "history_count": len(self._history),
            "pattern_stats": self._pattern_learner.to_dict(),
        }

    def _save_to_storage(self):
        if not self._storage_path:
            return

        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)

            data = {
                "pattern_learner": self._pattern_learner.to_dict(),
                "rl_learner": self._rl_learner.to_dict(),
                "history": [h.to_dict() for h in self._history[-100:]],
                "total_generations": self._total_generations,
                "successful_generations": self._successful_generations,
                "saved_at": datetime.now().isoformat(),
            }

            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug("Learning module saved to: %s", self._storage_path)

        except Exception as e:
            logger.warning("Could not save learning module: %s", e)

    def _load_from_storage(self):
        if not self._storage_path or not os.path.exists(self._storage_path):
            return

        try:
            with open(self._storage_path, "r") as f:
                data = json.load(f)

            self._pattern_learner = PatternLearner.from_dict(
                data.get("pattern_learner", {})
            )
            self._rl_learner = ReinforcementLearner.from_dict(
                data.get("rl_learner", {})
            )

            history_list = data.get("history", [])
            for h_dict in history_list:
                feedback_list = [
                    ValidationFeedback.from_dict(f)
                    for f in h_dict.get("feedback_list", [])
                ]
                history = GenerationHistory(
                    design_name=h_dict.get("design_name", "unknown"),
                    generation_source=h_dict.get("generation_source", "unknown"),
                    spec_hash=h_dict.get("spec_hash", ""),
                    feedback_list=feedback_list,
                    success_rate=h_dict.get("success_rate", 0.0),
                    avg_score=h_dict.get("avg_score", 0.0),
                    timestamp=h_dict.get("timestamp", datetime.now().isoformat()),
                )
                self._history.append(history)

            self._total_generations = data.get("total_generations", 0)
            self._successful_generations = data.get("successful_generations", 0)

            logger.info("Learning module loaded from: %s", self._storage_path)

        except Exception as e:
            logger.warning("Could not load learning module: %s", e)
