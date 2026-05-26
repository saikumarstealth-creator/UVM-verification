"""
Advanced Pattern Learner for UVM Testbench Generation.

Key improvements for promotion:
1. Context-aware error pattern extraction with n-grams
2. Success pattern mining from successful generations
3. Association rule learning between spec features and success
4. Protocol-specific pattern libraries
5. Error correlation detection
6. Pattern-based code suggestions
7. Temporal pattern tracking (learning over time)
"""

from __future__ import annotations

import logging
import re
import math
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
from enum import Enum

logger = logging.getLogger("uvmgen.ml.patterns")


class PatternType(Enum):
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    STRUCTURAL = "structural"


@dataclass
class Pattern:
    pattern_str: str
    pattern_type: PatternType
    count: int = 0
    confidence: float = 0.0
    support: float = 0.0
    lift: float = 1.0
    contexts: List[str] = field(default_factory=list)
    file_types: List[str] = field(default_factory=list)
    protocols: List[str] = field(default_factory=list)
    auto_fix: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_str": self.pattern_str,
            "pattern_type": self.pattern_type.value,
            "count": self.count,
            "confidence": self.confidence,
            "support": self.support,
            "lift": self.lift,
            "contexts": self.contexts,
            "file_types": self.file_types,
            "protocols": self.protocols,
            "auto_fix": self.auto_fix,
            "description": self.description,
        }


@dataclass
class AssociationRule:
    antecedent: str
    consequent: str
    confidence: float
    support: float
    lift: float
    count: int = 0


class NgramExtractor:
    """Extract n-grams from code and error messages for pattern learning."""

    def __init__(self, n_min: int = 1, n_max: int = 4):
        self.n_min = n_min
        self.n_max = n_max

    def extract(self, text: str, file_type: str = "unknown") -> List[str]:
        """Extract meaningful n-grams from text."""
        clean_text = self._preprocess(text)
        tokens = self._tokenize(clean_text)

        if not tokens:
            return []

        ngrams = []
        for n in range(self.n_min, self.n_max + 1):
            for i in range(len(tokens) - n + 1):
                ngram = " ".join(tokens[i:i + n])
                if self._is_meaningful(ngram, file_type):
                    ngrams.append(ngram)

        return ngrams

    def _preprocess(self, text: str) -> str:
        """Preprocess text for tokenization."""
        text = re.sub(r'//.*$', ' ', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.DOTALL)
        text = re.sub(r'"[^"]*"', 'STR', text)
        text = text.replace('(', ' ( ').replace(')', ' ) ')
        text = text.replace('[', ' [ ').replace(']', ' ] ')
        text = text.replace('{', ' { ').replace('}', ' } ')
        text = text.replace(';', ' ; ')
        text = text.replace(',', ' , ')
        return text

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize into meaningful units."""
        tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+|==|!=|<=|>=|\+=|-=|\*=|/=|&&|\|\||[+\-*/%=<>!&|~^?:;,\(\)\[\]\{\}]', text)
        return [t.strip() for t in tokens if t.strip()]

    def _is_meaningful(self, ngram: str, file_type: str) -> bool:
        """Filter to keep only meaningful ngrams."""
        if len(ngram) < 3:
            return False

        stop_patterns = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must',
            'shall', 'can', 'need', 'dare', 'ought', 'used',
            'if', 'else', 'then', 'for', 'while', 'until', 'unless',
            'begin', 'end', 'module', 'endmodule', 'class', 'endclass',
            'input', 'output', 'logic', 'reg', 'wire', 'bit', 'int',
            'always', 'initial', 'assign', 'posedge', 'negedge',
        }

        words = ngram.lower().split()
        if all(w in stop_patterns for w in words):
            return False

        uvm_keywords = {'uvm', 'test', 'env', 'agent', 'driver', 'monitor',
                        'sequencer', 'sequence', 'scoreboard', 'register',
                        'reg', 'phase', 'objection', 'config_db'}
        if any(kw in ngram.lower() for kw in uvm_keywords):
            return True

        if file_type in ('sequence', 'test'):
            seq_keywords = {'start_item', 'finish_item', 'raise_objection',
                           'drop_objection', 'randomize', 'body'}
            if any(kw in ngram for kw in seq_keywords):
                return True

        if len(words) >= 2:
            return True

        return len(ngram) > 5


class ContextAwareErrorDetector:
    """Detect errors with context for better pattern learning."""

    ERROR_PATTERNS_WITH_CONTEXT = [
        (
            r'missing\s+.*semicolon',
            'missing_semicolon',
            'Ensure all statements end with semicolons',
            'Check lines ending with expressions or declarations'
        ),
        (
            r'unbalanced\s+.*parenthes',
            'unbalanced_parentheses',
            'Check for balanced parentheses',
            'Count opening and closing parentheses in complex expressions'
        ),
        (
            r'unbalanced\s+.*brace',
            'unbalanced_braces',
            'Check for balanced begin/end blocks',
            'Verify all begin/fork have matching end/join'
        ),
        (
            r'unbalanced\s+.*bracket',
            'unbalanced_brackets',
            'Check array indexing and part-selects',
            'Verify all [ have matching ]'
        ),
        (
            r'mismatch.*begin|begin.*without.*end',
            'mismatched_blocks',
            'Verify block structure',
            'Check begin/end, fork/join pairing'
        ),
        (
            r'uvm_fatal|uvm_error.*not.*found',
            'missing_uvm_import',
            'Import UVM package',
            'Add `include "uvm_macros.svh" and import uvm_pkg::*'
        ),
        (
            r'uvm_component_utils|uvm_object_utils.*missing',
            'missing_factory_macro',
            'Add UVM factory registration',
            'Use `uvm_component_utils for components, `uvm_object_utils for objects'
        ),
        (
            r'build_phase|connect_phase|run_phase.*not.*called',
            'phase_implementation',
            'Check phase method signatures',
            'Ensure phases are declared as virtual functions/tasks with correct signatures'
        ),
        (
            r'raise_objection|drop_objection.*missing',
            'missing_objection',
            'Add objection handling in tests/sequences',
            'Use phase.raise_objection(this) and phase.drop_objection(this) in run_phase'
        ),
        (
            r'config_db.*get.*failed|config_db.*set.*missing',
            'config_db_issue',
            'Check config_db usage',
            'Ensure set/get paths match and config_db is set before build_phase'
        ),
        (
            r'reg_model.*null|reg_model.*not.*initialized',
            'missing_ral_model',
            'Initialize RAL model in test',
            'Create and build reg_model in test::build_phase, set in config_db'
        ),
        (
            r'signal.*not.*declared|signal.*undefined',
            'undefined_signal',
            'Check signal declarations',
            'Ensure all signals used are declared in the interface/module'
        ),
        (
            r'port.*not.*connected|port.*missing',
            'port_connection',
            'Check port connections',
            'Verify all module ports are connected in testbench'
        ),
        (
            r'interface.*not.*set|vif.*null',
            'missing_vif',
            'Set virtual interface in config_db',
            'Call uvm_config_db#(virtual intf)::set in testbench before run_test()'
        ),
        (
            r'sequence.*not.*started|sequencer.*null',
            'sequence_start',
            'Check sequence starting',
            'Ensure seq.start(sequencer) is called with valid sequencer'
        ),
        (
            r'analysis_port.*not.*connected|analysis_export.*null',
            'analysis_connection',
            'Check TLM connections',
            'Connect analysis ports to exports in connect_phase'
        ),
    ]

    @classmethod
    def extract_with_context(
        cls,
        error_msg: str,
        content: Optional[str] = None,
        line_num: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Extract error patterns with contextual information."""
        results = []

        for pattern, error_type, suggestion, context_tip in cls.ERROR_PATTERNS_WITH_CONTEXT:
            if re.search(pattern, error_msg, re.IGNORECASE):
                result = {
                    'error_type': error_type,
                    'pattern': pattern,
                    'message': error_msg[:200] if len(error_msg) > 200 else error_msg,
                    'suggestion': suggestion,
                    'context_tip': context_tip,
                    'line_number': line_num,
                }

                if content and line_num:
                    result['context'] = cls._get_content_context(content, line_num)

                results.append(result)

        if not results:
            results.append({
                'error_type': 'unknown_error',
                'message': error_msg[:200] if len(error_msg) > 200 else error_msg,
                'suggestion': 'Review the error message details',
                'line_number': line_num,
            })

        return results

    @staticmethod
    def _get_content_context(content: str, line_num: int, context_lines: int = 3) -> str:
        """Get surrounding lines of content for context."""
        lines = content.split('\n')
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)

        context_lines = []
        for i in range(start, end):
            marker = '>> ' if i == line_num - 1 else '   '
            context_lines.append(f"{marker}{i+1:4d}: {lines[i]}")

        return '\n'.join(context_lines)


class SuccessPatternMiner:
    """Mine patterns from successful generations for reuse."""

    def __init__(self):
        self._success_patterns: Dict[str, Pattern] = {}
        self._file_type_patterns: Dict[str, Dict[str, int]] = defaultdict(dict)
        self._protocol_patterns: Dict[str, Dict[str, int]] = defaultdict(dict)
        self._total_successes: int = 0

    def mine_from_success(
        self,
        content: str,
        file_type: str,
        protocol: str,
        score: float,
    ) -> List[str]:
        """Mine successful patterns from high-quality generated code."""
        if score < 0.7:
            return []

        extractor = NgramExtractor(n_min=2, n_max=5)
        ngrams = extractor.extract(content, file_type)

        filtered = self._filter_success_patterns(ngrams, file_type)

        for ngram in filtered:
            self._record_success_pattern(ngram, file_type, protocol, score)

        self._total_successes += 1
        return filtered

    def _filter_success_patterns(self, ngrams: List[str], file_type: str) -> List[str]:
        """Filter to keep only meaningful success patterns."""
        filtered = []

        success_indicators = {
            'any': [
                'uvm_component_utils', 'uvm_object_utils',
                'raise_objection', 'drop_objection',
                'build_phase', 'connect_phase', 'run_phase',
                'config_db', 'type_id', 'create',
            ],
            'driver': [
                'seq_item_port', 'get_next_item', 'item_done',
            ],
            'monitor': [
                'analysis_port', 'write',
            ],
            'agent': [
                'get_is_active', 'driver', 'monitor', 'sequencer',
            ],
            'scoreboard': [
                'uvm_analysis_imp', 'write',
            ],
            'sequence': [
                'start_item', 'finish_item', 'body', 'randomize',
            ],
            'test': [
                'uvm_test', 'env', 'reg_model',
            ],
            'ral_model': [
                'uvm_reg', 'uvm_reg_block', 'uvm_reg_field',
                'create_map', 'lock_model',
            ],
        }

        for ngram in ngrams:
            indicators = success_indicators.get(file_type, []) + success_indicators.get('any', [])
            if any(ind in ngram for ind in indicators):
                filtered.append(ngram)

        return list(set(filtered))

    def _record_success_pattern(
        self,
        ngram: str,
        file_type: str,
        protocol: str,
        score: float,
    ) -> None:
        """Record a successful pattern."""
        if ngram not in self._success_patterns:
            self._success_patterns[ngram] = Pattern(
                pattern_str=ngram,
                pattern_type=PatternType.SUCCESS,
                description=f"Successful pattern from {file_type}",
            )

        pattern = self._success_patterns[ngram]
        pattern.count += 1

        if file_type not in pattern.file_types:
            pattern.file_types.append(file_type)
        if protocol not in pattern.protocols:
            pattern.protocols.append(protocol)

        if file_type not in self._file_type_patterns:
            self._file_type_patterns[file_type] = defaultdict(int)
        self._file_type_patterns[file_type][ngram] += 1

        if protocol not in self._protocol_patterns:
            self._protocol_patterns[protocol] = defaultdict(int)
        self._protocol_patterns[protocol][ngram] += 1

        total = float(self._total_successes + 1)
        pattern.support = pattern.count / total
        pattern.confidence = min(1.0, score * pattern.count / total)

    def get_success_patterns(
        self,
        file_type: Optional[str] = None,
        protocol: Optional[str] = None,
        min_count: int = 2,
        top_n: int = 20,
    ) -> List[Pattern]:
        """Get successful patterns filtered by criteria."""
        candidates: List[Pattern] = []

        for pattern in self._success_patterns.values():
            if pattern.count < min_count:
                continue
            if file_type and file_type not in pattern.file_types:
                continue
            if protocol and protocol not in pattern.protocols:
                continue
            candidates.append(pattern)

        candidates.sort(key=lambda p: (p.confidence, p.support), reverse=True)
        return candidates[:top_n]

    def get_recommendations(
        self,
        file_type: str,
        protocol: str,
    ) -> List[Dict[str, Any]]:
        """Get code recommendations based on success patterns."""
        recommendations = []

        patterns = self.get_success_patterns(
            file_type=file_type,
            protocol=protocol,
            min_count=1,
            top_n=10,
        )

        for pattern in patterns:
            recommendations.append({
                'pattern': pattern.pattern_str,
                'confidence': pattern.confidence,
                'support': pattern.support,
                'file_types': pattern.file_types,
                'description': pattern.description,
            })

        return recommendations

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_successes': self._total_successes,
            'success_patterns': {k: v.to_dict() for k, v in self._success_patterns.items()},
            'file_type_patterns': {
                ft: dict(patterns) for ft, patterns in self._file_type_patterns.items()
            },
            'protocol_patterns': {
                proto: dict(patterns) for proto, patterns in self._protocol_patterns.items()
            },
        }


class AssociationRuleMiner:
    """Mine association rules between spec features and generation success."""

    def __init__(self, min_support: float = 0.1, min_confidence: float = 0.5):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self._transactions: List[Set[str]] = []
        self._item_counts: Dict[str, int] = defaultdict(int)
        self._rules: List[AssociationRule] = []

    def add_transaction(self, items: List[str]) -> None:
        """Add a transaction (set of features/outcomes)."""
        item_set = set(items)
        self._transactions.append(item_set)

        for item in item_set:
            self._item_counts[item] += 1

    def mine_rules(self) -> List[AssociationRule]:
        """Mine association rules from transactions."""
        if len(self._transactions) < 5:
            return []

        min_support_count = int(self.min_support * len(self._transactions))

        freq_items = {
            item: count for item, count in self._item_counts.items()
            if count >= min_support_count
        }

        if len(freq_items) < 2:
            return []

        rules = []
        items_list = list(freq_items.keys())

        for i, item1 in enumerate(items_list):
            for item2 in items_list[i+1:]:
                count_both = sum(
                    1 for t in self._transactions
                    if item1 in t and item2 in t
                )

                if count_both < min_support_count:
                    continue

                support = count_both / len(self._transactions)

                confidence_1_2 = count_both / self._item_counts[item1]
                confidence_2_1 = count_both / self._item_counts[item2]

                support_item1 = self._item_counts[item1] / len(self._transactions)
                support_item2 = self._item_counts[item2] / len(self._transactions)

                lift_1_2 = confidence_1_2 / support_item2 if support_item2 > 0 else 1.0
                lift_2_1 = confidence_2_1 / support_item1 if support_item1 > 0 else 1.0

                if confidence_1_2 >= self.min_confidence:
                    rules.append(AssociationRule(
                        antecedent=item1,
                        consequent=item2,
                        confidence=confidence_1_2,
                        support=support,
                        lift=lift_1_2,
                        count=count_both,
                    ))

                if confidence_2_1 >= self.min_confidence:
                    rules.append(AssociationRule(
                        antecedent=item2,
                        consequent=item1,
                        confidence=confidence_2_1,
                        support=support,
                        lift=lift_2_1,
                        count=count_both,
                    ))

        rules.sort(key=lambda r: (r.confidence, r.lift, r.support), reverse=True)
        self._rules = rules
        return rules

    def get_rules_for_antecedent(self, antecedent: str) -> List[AssociationRule]:
        """Get all rules with a specific antecedent."""
        return [r for r in self._rules if r.antecedent == antecedent]

    def get_rules_for_consequent(self, consequent: str) -> List[AssociationRule]:
        """Get all rules with a specific consequent."""
        return [r for r in self._rules if r.consequent == consequent]


class TemporalPatternTracker:
    """Track how patterns evolve over time for continuous learning."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._error_windows: Dict[str, List[bool]] = defaultdict(list)
        self._success_windows: Dict[str, List[bool]] = defaultdict(list)
        self._trends: Dict[str, float] = {}

    def record_error(self, error_type: str, occurred: bool) -> None:
        """Record whether an error occurred."""
        self._error_windows[error_type].append(occurred)
        if len(self._error_windows[error_type]) > self.window_size:
            self._error_windows[error_type].pop(0)
        self._update_trend(error_type, 'error')

    def record_success(self, pattern: str, success: bool) -> None:
        """Record pattern success."""
        self._success_windows[pattern].append(success)
        if len(self._success_windows[pattern]) > self.window_size:
            self._success_windows[pattern].pop(0)
        self._update_trend(pattern, 'success')

    def _update_trend(self, key: str, pattern_type: str) -> None:
        """Update trend direction."""
        if pattern_type == 'error':
            window = self._error_windows.get(key, [])
        else:
            window = self._success_windows.get(key, [])

        if len(window) < 10:
            self._trends[key] = 0.0
            return

        first_half = window[:len(window)//2]
        second_half = window[len(window)//2:]

        rate_first = sum(first_half) / len(first_half)
        rate_second = sum(second_half) / len(second_half)

        self._trends[key] = rate_second - rate_first

    def get_trend(self, key: str) -> float:
        """Get trend: positive = improving, negative = worsening."""
        return self._trends.get(key, 0.0)

    def get_error_rate(self, error_type: str) -> float:
        """Get current error rate."""
        window = self._error_windows.get(error_type, [])
        if not window:
            return 0.0
        return sum(window) / len(window)

    def get_success_rate(self, pattern: str) -> float:
        """Get current success rate."""
        window = self._success_windows.get(pattern, [])
        if not window:
            return 0.0
        return sum(window) / len(window)

    def get_improving_errors(self) -> List[Tuple[str, float]]:
        """Get errors that are decreasing."""
        improving = []
        for key, trend in self._trends.items():
            if key in self._error_windows and trend < -0.1:
                improving.append((key, trend))
        improving.sort(key=lambda x: x[1])
        return improving

    def get_worsening_errors(self) -> List[Tuple[str, float]]:
        """Get errors that are increasing."""
        worsening = []
        for key, trend in self._trends.items():
            if key in self._error_windows and trend > 0.1:
                worsening.append((key, trend))
        worsening.sort(key=lambda x: x[1], reverse=True)
        return worsening


class AdvancedPatternLearner:
    """
    Advanced pattern learner combining all capabilities.

    This is the main interface for:
    1. Error pattern detection and tracking
    2. Success pattern mining
    3. Association rule learning
    4. Temporal trend analysis
    5. Code recommendations
    """

    def __init__(self):
        self._error_detector = ContextAwareErrorDetector()
        self._success_miner = SuccessPatternMiner()
        self._association_miner = AssociationRuleMiner(min_support=0.1, min_confidence=0.5)
        self._temporal_tracker = TemporalPatternTracker(window_size=100)

        self._error_patterns: Dict[str, Pattern] = {}
        self._file_type_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"success": 0, "total": 0, "errors": defaultdict(int)}
        )
        self._protocol_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"success": 0, "total": 0}
        )

        self._ngram_extractor = NgramExtractor(n_min=1, n_max=4)

    def record_error(
        self,
        error_msg: str,
        file_type: str = "unknown",
        content: Optional[str] = None,
        line_num: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Record an error with full context analysis."""
        errors = self._error_detector.extract_with_context(
            error_msg, content, line_num
        )

        for err in errors:
            error_type = err['error_type']

            if error_type not in self._error_patterns:
                self._error_patterns[error_type] = Pattern(
                    pattern_str=error_type,
                    pattern_type=PatternType.ERROR,
                    description=err.get('suggestion', ''),
                )

            self._error_patterns[error_type].count += 1
            self._error_patterns[error_type].contexts.append(
                err.get('context', error_msg[:100])
            )
            if file_type not in self._error_patterns[error_type].file_types:
                self._error_patterns[error_type].file_types.append(file_type)

            self._file_type_stats[file_type]["errors"][error_type] += 1
            self._temporal_tracker.record_error(error_type, True)

        return errors

    def record_success(
        self,
        file_type: str = "unknown",
        protocol: str = "unknown",
        content: Optional[str] = None,
        score: float = 1.0,
    ) -> List[str]:
        """Record a success and mine patterns from it."""
        self._file_type_stats[file_type]["success"] += 1
        self._file_type_stats[file_type]["total"] += 1
        self._protocol_stats[protocol]["success"] += 1
        self._protocol_stats[protocol]["total"] += 1

        mined_patterns = []
        if content and score >= 0.7:
            mined_patterns = self._success_miner.mine_from_success(
                content, file_type, protocol, score
            )

            for pattern in mined_patterns:
                self._temporal_tracker.record_success(pattern, True)

            items = [
                f"file_type:{file_type}",
                f"protocol:{protocol}",
                f"success:yes",
                f"score:{int(score * 10)}",
            ]
            items.extend(mined_patterns[:5])
            self._association_miner.add_transaction(items)

        return mined_patterns

    def record_attempt(
        self,
        file_type: str = "unknown",
        protocol: str = "unknown",
    ) -> None:
        """Record an attempt (for stats tracking)."""
        self._file_type_stats[file_type]["total"] += 1
        self._protocol_stats[protocol]["total"] += 1

    def get_common_errors(self, top_n: int = 10) -> List[Tuple[str, int, Pattern]]:
        """Get the most common errors."""
        sorted_errors = sorted(
            self._error_patterns.items(),
            key=lambda x: x[1].count,
            reverse=True,
        )
        return [(name, p.count, p) for name, p in sorted_errors[:top_n]]

    def get_file_type_success_rate(self, file_type: str) -> float:
        """Get success rate for a file type."""
        stats = self._file_type_stats.get(file_type, {})
        total = stats.get("total", 0)
        if total == 0:
            return 0.5
        return stats.get("success", 0) / total

    def get_protocol_success_rate(self, protocol: str) -> float:
        """Get success rate for a protocol."""
        stats = self._protocol_stats.get(protocol, {})
        total = stats.get("total", 0)
        if total == 0:
            return 0.5
        return stats.get("success", 0) / total

    def get_suggestions(
        self,
        file_type: str,
        protocol: str,
    ) -> Dict[str, Any]:
        """Get comprehensive suggestions for improvement."""
        common_errors = self.get_common_errors(5)
        file_success_rate = self.get_file_type_success_rate(file_type)
        protocol_success_rate = self.get_protocol_success_rate(protocol)

        success_recommendations = self._success_miner.get_recommendations(
            file_type, protocol
        )

        improving = self._temporal_tracker.get_improving_errors()
        worsening = self._temporal_tracker.get_worsening_errors()

        suggestions = {
            "common_errors": [
                {
                    "error_type": name,
                    "count": count,
                    "description": pattern.description,
                    "current_rate": self._temporal_tracker.get_error_rate(name),
                    "trend": self._temporal_tracker.get_trend(name),
                }
                for name, count, pattern in common_errors
            ],
            "file_type_success_rate": file_success_rate,
            "protocol_success_rate": protocol_success_rate,
            "success_patterns": success_recommendations,
            "improving_errors": [{"error": e[0], "trend": e[1]} for e in improving],
            "worsening_errors": [{"error": e[0], "trend": e[1]} for e in worsening],
            "recommendations": self._generate_advanced_recommendations(
                file_type, protocol, file_success_rate, common_errors
            ),
        }

        return suggestions

    def _generate_advanced_recommendations(
        self,
        file_type: str,
        protocol: str,
        success_rate: float,
        common_errors: List[Tuple],
    ) -> List[str]:
        """Generate advanced recommendations based on all data."""
        recommendations = []

        for name, count, pattern in common_errors[:3]:
            if count > 0:
                if pattern.description:
                    recommendations.append(pattern.description)
                elif 'semicolon' in name:
                    recommendations.append("Ensure all statements end with semicolons")
                elif 'parenthes' in name:
                    recommendations.append("Check for balanced parentheses")
                elif 'brace' in name or 'block' in name:
                    recommendations.append("Check for balanced begin/end blocks")
                elif 'uvm_macro' in name or 'factory' in name:
                    recommendations.append(
                        "Add UVM factory registration macros (uvm_component_utils/uvm_object_utils)"
                    )
                elif 'phase' in name:
                    recommendations.append("Ensure proper UVM phase implementation")
                elif 'objection' in name:
                    recommendations.append(
                        "Use phase.raise_objection(this) and phase.drop_objection(this)"
                    )
                elif 'config_db' in name or 'vif' in name:
                    recommendations.append(
                        "Ensure virtual interface is set in config_db before run_test()"
                    )
                elif 'ral' in name or 'reg_model' in name:
                    recommendations.append(
                        "Create and initialize RAL model in test::build_phase"
                    )
                elif 'signal' in name or 'port' in name:
                    recommendations.append(
                        "Ensure all signals/ports used are declared in spec and interface"
                    )

        if success_rate < 0.7:
            recommendations.append(
                f"Consider using retrieval-based generation for {file_type} (success rate: {success_rate:.1%})"
            )

        rules = self._association_miner.get_rules_for_antecedent(f"file_type:{file_type}")
        for rule in rules[:3]:
            if rule.confidence > 0.7 and rule.lift > 1.0:
                recommendations.append(
                    f"Consider: {rule.consequent} (confidence: {rule.confidence:.1%}, lift: {rule.lift:.2f})"
                )

        if not recommendations:
            recommendations.append(
                "No specific recommendations - generation should work well"
            )

        return recommendations

    def mine_association_rules(self) -> List[AssociationRule]:
        """Mine association rules from collected data."""
        return self._association_miner.mine_rules()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_patterns": {k: v.to_dict() for k, v in self._error_patterns.items()},
            "file_type_stats": {
                ft: {
                    "success": s["success"],
                    "total": s["total"],
                    "errors": dict(s["errors"]),
                }
                for ft, s in self._file_type_stats.items()
            },
            "protocol_stats": dict(self._protocol_stats),
            "success_miner": self._success_miner.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdvancedPatternLearner":
        learner = cls()

        for name, pdict in d.get("error_patterns", {}).items():
            pattern = Pattern(
                pattern_str=pdict.get("pattern_str", name),
                pattern_type=PatternType(pdict.get("pattern_type", "error")),
                count=pdict.get("count", 0),
                confidence=pdict.get("confidence", 0.0),
                support=pdict.get("support", 0.0),
                contexts=pdict.get("contexts", []),
                file_types=pdict.get("file_types", []),
                protocols=pdict.get("protocols", []),
                description=pdict.get("description", ""),
            )
            learner._error_patterns[name] = pattern

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
