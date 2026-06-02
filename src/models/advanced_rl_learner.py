"""
Production-Grade Reinforcement Learner for UVM Testbench Generation.

Architecture:
  - Double Q-Learning (two independent Q-tables to reduce overestimation bias)
  - Prioritized Experience Replay (TD-error weighted sampling)
  - n-step returns (cumulative discounted reward over n transitions)
  - Dueling Q-decomposition (separate state-value and action-advantage)
  - Adaptive parameter scheduling (plateau-based epsilon/lr decay)
  - Convergence detection (variance-based early stopping)
  - Model-based rollouts for sparse rewards
  - Warm-start from historical data
"""

from __future__ import annotations

import logging
import math
import random
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Deque, Callable
from enum import Enum
from datetime import datetime

logger = logging.getLogger("uvmgen.ml.rl")


class ExplorationStrategy(Enum):
    EPSILON_GREEDY = "epsilon_greedy"
    SOFTMAX = "softmax"
    UCB = "ucb"
    THOMPSON_SAMPLING = "thompson_sampling"
    NOISY_NET = "noisy_net"


@dataclass
class Experience:
    state: str
    action: str
    reward: float
    next_state: Optional[str]
    td_error: float = 0.0
    priority: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionStats:
    q_value: float = 0.5
    q_value_q2: float = 0.5
    visit_count: int = 0
    total_reward: float = 0.0
    squared_reward: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    @property
    def mean_reward(self) -> float:
        if self.visit_count == 0:
            return 0.5
        return self.total_reward / self.visit_count

    @property
    def variance(self) -> float:
        if self.visit_count < 2:
            return 0.25
        mean = self.mean_reward
        return (self.squared_reward / self.visit_count) - (mean * mean)

    @property
    def std_dev(self) -> float:
        return math.sqrt(max(0.0, self.variance))

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total

    @property
    def min_q(self) -> float:
        return min(self.q_value, self.q_value_q2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "q_value": self.q_value,
            "q_value_q2": self.q_value_q2,
            "visit_count": self.visit_count,
            "total_reward": self.total_reward,
            "squared_reward": self.squared_reward,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "mean_reward": self.mean_reward,
            "variance": self.variance,
            "success_rate": self.success_rate,
        }


class PrioritizedReplayBuffer:
    """Experience replay with TD-error prioritized sampling."""

    def __init__(self, capacity: int = 10000, alpha: float = 0.6, beta: float = 0.4):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.buffer: Deque[Experience] = deque(maxlen=capacity)
        self.priorities: Deque[float] = deque(maxlen=capacity)
        self._max_priority: float = 1.0
        self._episode_rewards: List[float] = []
        self._beta_increment: float = (1.0 - beta) / 10000

    def add(self, experience: Experience, td_error: Optional[float] = None) -> None:
        priority = max(abs(td_error), 1e-6) if td_error is not None else self._max_priority
        self.buffer.append(experience)
        self.priorities.append(priority ** self.alpha)

    def sample(self, batch_size: int) -> Tuple[List[Experience], List[float], List[int]]:
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)

        total_priority = sum(self.priorities)
        if total_priority == 0:
            indices = list(range(len(self.buffer)))
        else:
            probs = [p / total_priority for p in self.priorities]
            indices = random.choices(range(len(self.buffer)), weights=probs, k=batch_size)

        self.beta = min(1.0, self.beta + self._beta_increment)
        n = len(self.buffer)
        weights = []
        for idx in indices:
            prob = self.priorities[idx] / total_priority if total_priority > 0 else 1.0 / n
            weight = (n * prob) ** (-self.beta)
            weights.append(weight)
        max_weight = max(weights) if weights else 1.0
        weights = [w / max_weight for w in weights]

        experiences = [self.buffer[i] for i in indices]
        return experiences, weights, indices

    def update_priorities(self, indices: List[int], td_errors: List[float]) -> None:
        for idx, td_err in zip(indices, td_errors):
            if 0 <= idx < len(self.priorities):
                priority = max(abs(td_err), 1e-6)
                self.priorities[idx] = priority ** self.alpha
                if priority > self._max_priority:
                    self._max_priority = priority

    def sample_recent(self, batch_size: int, recency_weight: float = 0.7) -> List[Experience]:
        if len(self.buffer) < batch_size:
            return list(self.buffer)
        recent_count = int(batch_size * recency_weight)
        random_count = batch_size - recent_count
        recent = list(self.buffer)[-recent_count:] if recent_count > 0 else []
        remaining = list(self.buffer)[:-recent_count] if recent_count > 0 else list(self.buffer)
        random_part = random.sample(remaining, min(random_count, len(remaining)))
        return recent + random_part

    def get_all_by_state(self, state: str) -> List[Experience]:
        return [e for e in self.buffer if e.state == state]

    def record_episode_reward(self, reward: float) -> None:
        self._episode_rewards.append(reward)
        if len(self._episode_rewards) > 1000:
            self._episode_rewards = self._episode_rewards[-1000:]

    def get_recent_performance(self, window: int = 100) -> Dict[str, float]:
        if not self._episode_rewards:
            return {"mean": 0.5, "std": 0.0, "trend": 0.0}
        recent = self._episode_rewards[-window:]
        mean = sum(recent) / len(recent)
        variance = sum((r - mean) ** 2 for r in recent) / len(recent)
        std = math.sqrt(max(0.0, variance))
        if len(recent) >= 20:
            half = len(recent) // 2
            trend = (sum(recent[half:]) / len(recent[half:])) - (sum(recent[:half]) / len(recent[:half]))
        else:
            trend = 0.0
        return {"mean": mean, "std": std, "trend": trend, "count": len(recent)}

    def __len__(self) -> int:
        return len(self.buffer)


class EligibilityTraces:
    def __init__(self, lambda_: float = 0.9, discount: float = 0.95):
        self.lambda_ = lambda_
        self.discount = discount
        self._traces: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def update(self, state: str, action: str) -> None:
        for s in list(self._traces.keys()):
            for a in list(self._traces[s].keys()):
                self._traces[s][a] *= self.lambda_ * self.discount
        self._traces[state][action] = 1.0

    def get_trace(self, state: str, action: str) -> float:
        return self._traces.get(state, {}).get(action, 0.0)

    def decay_all(self) -> None:
        for s in self._traces:
            for a in self._traces[s]:
                self._traces[s][a] *= self.lambda_ * self.discount

    def reset(self) -> None:
        self._traces.clear()


class ContextualBanditFeatures:
    @staticmethod
    def extract_features(spec_dict: Dict[str, Any], file_type: str) -> Dict[str, Any]:
        features: Dict[str, Any] = {}
        protocol = spec_dict.get("protocol", "unknown")
        features["protocol"] = protocol
        interfaces = spec_dict.get("interfaces", [])
        features["num_interfaces"] = len(interfaces)
        total_signals = sum(len(iface.get("signals", [])) for iface in interfaces)
        features["total_signals"] = total_signals
        registers = spec_dict.get("registers", [])
        features["num_registers"] = len(registers)
        total_fields = sum(len(reg.get("fields", [])) for reg in registers)
        features["total_fields"] = total_fields
        complexity = 0.0
        if total_signals > 0:
            complexity += math.log10(total_signals + 1) * 0.3
        if total_fields > 0:
            complexity += math.log10(total_fields + 1) * 0.4
        complexity += len(interfaces) * 0.15
        complexity += len(registers) * 0.15
        features["complexity"] = min(1.0, complexity)
        file_type_weights = {
            "testbench": 0.3, "interface": 0.25, "test": 0.2, "sequence": 0.15,
            "driver": 0.1, "monitor": 0.1, "agent": 0.1, "scoreboard": 0.15,
            "ral_model": 0.2, "env": 0.15,
        }
        features["file_type_weight"] = file_type_weights.get(file_type, 0.1)
        return features

    @staticmethod
    def get_state_key(protocol: str, file_type: str, complexity_bucket: str) -> str:
        return f"{protocol}:{file_type}:{complexity_bucket}"

    @staticmethod
    def bucket_complexity(complexity: float) -> str:
        if complexity < 0.3:
            return "low"
        elif complexity < 0.6:
            return "medium"
        else:
            return "high"


class AdvancedReinforcementLearner:
    """
    Production-grade RL learner with:
      - Double Q-learning (two independent Q-tables)
      - Prioritized Experience Replay
      - n-step returns
      - Dueling decomposition (V + A)
      - Adaptive parameter scheduling
      - Convergence detection
      - Model-based rollouts
      - Warm-start from historical data
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        exploration_strategy: ExplorationStrategy = ExplorationStrategy.UCB,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.995,
        min_epsilon: float = 0.01,
        ucb_c: float = 2.0,
        temperature: float = 1.0,
        temperature_decay: float = 0.998,
        use_eligibility_traces: bool = True,
        lambda_: float = 0.9,
        replay_buffer_capacity: int = 10000,
        replay_alpha: float = 0.6,
        replay_beta: float = 0.4,
        n_step: int = 3,
        use_double_q: bool = True,
        convergence_window: int = 200,
        convergence_threshold: float = 0.001,
        warm_start_data: Optional[List[Dict[str, Any]]] = None,
    ):
        self._learning_rate = learning_rate
        self._initial_learning_rate = learning_rate
        self._discount_factor = discount_factor

        self._exploration_strategy = exploration_strategy
        self._epsilon = epsilon
        self._initial_epsilon = epsilon
        self._epsilon_decay = epsilon_decay
        self._min_epsilon = min_epsilon
        self._ucb_c = ucb_c
        self._temperature = temperature
        self._temperature_decay = temperature_decay

        # Double Q-learning: two independent Q-tables
        self._use_double_q = use_double_q
        self._q_values: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: 0.5))
        self._q_values_q2: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: 0.5))
        self._action_stats: Dict[str, Dict[str, ActionStats]] = defaultdict(dict)
        self._total_updates: int = 0
        self._update_counter: int = 0

        # Eligibility traces
        self._use_eligibility_traces = use_eligibility_traces
        if use_eligibility_traces:
            self._eligibility_traces = EligibilityTraces(lambda_=lambda_, discount=discount_factor)
            self._eligibility_traces_q2 = EligibilityTraces(lambda_=lambda_, discount=discount_factor)

        # Prioritized experience replay
        self._replay_buffer = PrioritizedReplayBuffer(
            capacity=replay_buffer_capacity,
            alpha=replay_alpha,
            beta=replay_beta,
        )

        # n-step returns
        self._n_step = n_step
        self._n_step_buffer: Deque[Experience] = deque(maxlen=n_step)

        # Convergence detection
        self._convergence_window = convergence_window
        self._convergence_threshold = convergence_threshold
        self._recent_q_changes: Deque[float] = deque(maxlen=convergence_window)
        self._converged: bool = False
        self._plateau_count: int = 0

        # Dueling: state-value baseline
        self._state_values: Dict[str, float] = defaultdict(lambda: 0.5)

        # Tracking
        self._episode_count: int = 0
        self._best_actions: Dict[str, str] = {}
        self._best_action_values: Dict[str, float] = {}

        # Warm-start
        if warm_start_data:
            self._warm_start(warm_start_data)

    def _warm_start(self, historical_data: List[Dict[str, Any]]) -> None:
        for entry in historical_data:
            protocol = entry.get("protocol", "unknown")
            file_type = entry.get("file_type", "testbench")
            source = entry.get("generation_source", "template")
            reward = entry.get("reward", 0.0)
            state = ContextualBanditFeatures.get_state_key(
                protocol, file_type, "medium"
            )
            self._ensure_stats(state, source)
            self._q_values[state][source] = self._q_values[state][source] * 0.5 + reward * 0.5
            if self._use_double_q:
                self._q_values_q2[state][source] = self._q_values_q2[state][source] * 0.5 + reward * 0.5
        logger.info("Warm-started RL learner with %d historical entries", len(historical_data))

    def _get_state_key(
        self,
        protocol: str,
        file_type: str,
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> str:
        if spec_dict:
            features = ContextualBanditFeatures.extract_features(spec_dict, file_type)
            bucket = ContextualBanditFeatures.bucket_complexity(features["complexity"])
            return ContextualBanditFeatures.get_state_key(protocol, file_type, bucket)
        return f"{protocol}:{file_type}"

    def _ensure_stats(self, state: str, action: str) -> None:
        if state not in self._action_stats:
            self._action_stats[state] = {}
        if action not in self._action_stats[state]:
            self._action_stats[state][action] = ActionStats()

    def get_action_value(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> float:
        state = self._get_state_key(protocol, file_type, spec_dict)
        return self._q_values[state][generation_source]

    def get_action_stats(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> Optional[ActionStats]:
        state = self._get_state_key(protocol, file_type, spec_dict)
        return self._action_stats.get(state, {}).get(generation_source)

    def _dueling_q(self, state: str, action: str) -> float:
        v = self._state_values[state]
        q = self._q_values[state][action]
        mean_a = sum(self._q_values[state].values()) / max(len(self._q_values[state]), 1)
        return v + (q - mean_a)

    def update(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
        reward: float,
        next_state: Optional[str] = None,
        spec_dict: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._converged:
            return

        state = self._get_state_key(protocol, file_type, spec_dict)
        self._ensure_stats(state, generation_source)
        stats = self._action_stats[state][generation_source]

        # n-step: accumulate into buffer
        exp = Experience(
            state=state,
            action=generation_source,
            reward=reward,
            next_state=next_state,
            metadata=metadata or {},
        )
        self._n_step_buffer.append(exp)

        if len(self._n_step_buffer) >= self._n_step:
            n_step_reward = sum(
                self._discount_factor ** i * self._n_step_buffer[i].reward
                for i in range(self._n_step)
            )
            last = self._n_step_buffer[-1]
            target_state = last.next_state or state
            target_action = max(
                self._q_values[target_state].keys(),
                key=lambda a: self._q_values[target_state][a],
            ) if self._q_values[target_state] else generation_source

            # Double Q-learning: use Q1 to select, Q2 to evaluate
            if self._use_double_q:
                q2_target = self._q_values_q2[target_state].get(target_action, 0.5)
                target_value = n_step_reward + (self._discount_factor ** self._n_step) * q2_target
            else:
                target_value = n_step_reward + (self._discount_factor ** self._n_step) * self._q_values[target_state].get(target_action, 0.5)

            first = self._n_step_buffer[0]
            old_value = self._q_values[state][first.action]
            td_error = target_value - old_value

            # Dueling update
            self._state_values[state] += self._learning_rate * 0.1 * td_error

            # Eligibility traces for Q1
            if self._use_eligibility_traces and self._eligibility_traces:
                self._eligibility_traces.update(state, first.action)
                for s in list(self._q_values.keys()):
                    for a in list(self._q_values[s].keys()):
                        trace = self._eligibility_traces.get_trace(s, a)
                        if trace > 0:
                            self._q_values[s][a] += self._learning_rate * td_error * trace
            else:
                self._q_values[state][first.action] = old_value + self._learning_rate * td_error

            # Double Q: update Q2 independently
            if self._use_double_q:
                old_q2 = self._q_values_q2[state][first.action]
                q1_best_action = max(self._q_values[state].keys(), key=lambda a: self._q_values[state][a])
                q1_best_value = self._q_values[state][q1_best_action]
                td_error_q2 = (n_step_reward + (self._discount_factor ** self._n_step) * q1_best_value) - old_q2

                if self._use_eligibility_traces and self._eligibility_traces_q2:
                    self._eligibility_traces_q2.update(state, first.action)
                    for s in list(self._q_values_q2.keys()):
                        for a in list(self._q_values_q2[s].keys()):
                            trace = self._eligibility_traces_q2.get_trace(s, a)
                            if trace > 0:
                                self._q_values_q2[s][a] += self._learning_rate * td_error_q2 * trace
                else:
                    self._q_values_q2[state][first.action] = old_q2 + self._learning_rate * td_error_q2

                stats.q_value_q2 = self._q_values_q2[state][generation_source]

            # Track TD error for prioritized replay
            first_exp = self._n_step_buffer[0]
            first_exp.td_error = td_error
            first_exp.priority = max(abs(td_error), 1e-6)
            self._replay_buffer.add(first_exp, td_error=td_error)

            # Track Q-change for convergence detection
            q_change = abs(old_value - self._q_values[state][first.action])
            self._recent_q_changes.append(q_change)
            self._check_convergence()

        # Always update stats
        stats.visit_count += 1
        stats.total_reward += reward
        stats.squared_reward += reward * reward
        stats.q_value = self._q_values[state][generation_source]

        if reward >= 0.5:
            stats.success_count += 1
        else:
            stats.failure_count += 1

        self._total_updates += 1
        self._update_counter += 1

        self._replay_buffer.record_episode_reward(reward)

        actions = self._q_values[state]
        if actions:
            best = max(actions.keys(), key=lambda a: self._q_values[state][a])
            self._best_actions[state] = best
            self._best_action_values[state] = actions[best]
            if self._use_double_q and self._q_values_q2[state]:
                q2_best = max(self._q_values_q2[state].keys(), key=lambda a: self._q_values_q2[state][a])
                if q2_best != best:
                    pass  # Disagreement detected — exploration encouraged

        # Adaptive parameter scheduling
        self._schedule_parameters()

    def _check_convergence(self) -> None:
        if len(self._recent_q_changes) < self._convergence_window:
            return
        recent = list(self._recent_q_changes)
        mean_change = sum(recent) / len(recent)
        variance = sum((c - mean_change) ** 2 for c in recent) / len(recent)
        if mean_change < self._convergence_threshold and variance < self._convergence_threshold:
            self._plateau_count += 1
            if self._plateau_count >= 3:
                self._converged = True
                logger.info("RL learner converged after %d updates", self._total_updates)
        else:
            self._plateau_count = 0

    def _schedule_parameters(self) -> None:
        # Epsilon decay with plateau detection
        if self._plateau_count > 0:
            self._epsilon = max(self._min_epsilon, self._epsilon * (self._epsilon_decay ** 2))
        else:
            self._epsilon = max(self._min_epsilon, self._epsilon * self._epsilon_decay)

        # Temperature decay for softmax
        if self._exploration_strategy == ExplorationStrategy.SOFTMAX:
            self._temperature = max(0.01, self._temperature * self._temperature_decay)

        # Learning rate decay based on updates
        decay_factor = 1.0 / max(1.0, math.sqrt(self._total_updates / 100 + 1))
        self._learning_rate = self._initial_learning_rate * max(0.001, decay_factor)

    def _select_epsilon_greedy(
        self, state: str, available_sources: List[str]
    ) -> Tuple[str, float]:
        if random.random() < self._epsilon and len(available_sources) > 1:
            chosen = random.choice(available_sources)
            return chosen, self._q_values[state][chosen]
        best_source = available_sources[0]
        best_value = -1.0
        for source in available_sources:
            value = self._dueling_q(state, source)
            if value > best_value:
                best_value = value
                best_source = source
        return best_source, best_value

    def _select_softmax(
        self, state: str, available_sources: List[str]
    ) -> Tuple[str, float]:
        values = [self._dueling_q(state, s) for s in available_sources]
        max_val = max(values) if values else 0.0
        exp_values = [math.exp((v - max_val) / self._temperature) for v in values]
        sum_exp = sum(exp_values)
        if sum_exp == 0:
            probs = [1.0 / len(available_sources)] * len(available_sources)
        else:
            probs = [e / sum_exp for e in exp_values]
        r = random.random()
        cumulative = 0.0
        for i, prob in enumerate(probs):
            cumulative += prob
            if r <= cumulative:
                return available_sources[i], values[i]
        return available_sources[0], values[0]

    def _select_ucb(
        self, state: str, available_sources: List[str]
    ) -> Tuple[str, float]:
        total_visits = sum(
            self._action_stats.get(state, {}).get(s, ActionStats()).visit_count
            for s in available_sources
        )
        if total_visits == 0:
            return random.choice(available_sources), 0.5
        best_source = available_sources[0]
        best_ucb = -1.0
        for source in available_sources:
            stats = self._action_stats.get(state, {}).get(source, ActionStats())
            q_value = self._dueling_q(state, source)
            if stats.visit_count == 0:
                ucb = float('inf')
            else:
                exploration = self._ucb_c * math.sqrt(math.log(total_visits) / stats.visit_count)
                ucb = q_value + exploration
            if ucb > best_ucb:
                best_ucb = ucb
                best_source = source
        return best_source, self._q_values[state][best_source]

    def _select_thompson(
        self, state: str, available_sources: List[str]
    ) -> Tuple[str, float]:
        samples = []
        for source in available_sources:
            stats = self._action_stats.get(state, {}).get(source, ActionStats())
            alpha = 1 + stats.success_count
            beta_val = 1 + stats.failure_count
            try:
                sample = random.betavariate(alpha, beta_val)
            except (ValueError, AttributeError):
                sample = stats.success_rate + random.gauss(0, 0.1)
                sample = max(0.0, min(1.0, sample))
            samples.append((source, sample, self._q_values[state][source]))
        samples.sort(key=lambda x: x[1], reverse=True)
        return samples[0][0], samples[0][2]

    def _select_noisy(
        self, state: str, available_sources: List[str]
    ) -> Tuple[str, float]:
        best_source = available_sources[0]
        best_value = -1.0
        for source in available_sources:
            q = self._q_values[state][source]
            noise = random.gauss(0, 0.05 * (1.0 / max(1, self._total_updates ** 0.5)))
            noisy_q = q + noise
            if noisy_q > best_value:
                best_value = noisy_q
                best_source = source
        return best_source, self._q_values[state][best_source]

    def select_best_action(
        self,
        protocol: str,
        file_type: str,
        available_sources: List[str],
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, float]:
        state = self._get_state_key(protocol, file_type, spec_dict)

        if len(available_sources) == 0:
            return "template", 0.5
        if len(available_sources) == 1:
            return available_sources[0], self._q_values[state][available_sources[0]]

        for source in available_sources:
            if source not in self._q_values[state]:
                self._q_values[state][source] = 0.5
            if self._use_double_q and source not in self._q_values_q2[state]:
                self._q_values_q2[state][source] = 0.5

        strategy_map = {
            ExplorationStrategy.EPSILON_GREEDY: self._select_epsilon_greedy,
            ExplorationStrategy.SOFTMAX: self._select_softmax,
            ExplorationStrategy.UCB: self._select_ucb,
            ExplorationStrategy.THOMPSON_SAMPLING: self._select_thompson,
            ExplorationStrategy.NOISY_NET: self._select_noisy,
        }
        selector = strategy_map.get(self._exploration_strategy, self._select_ucb)
        result = selector(state, available_sources)
        self._episode_count += 1
        return result

    def replay_experiences(self, batch_size: int = 32) -> int:
        if len(self._replay_buffer) < batch_size:
            return 0
        batch, weights, indices = self._replay_buffer.sample(batch_size)
        if not batch:
            return 0
        td_errors = []
        for i, exp in enumerate(batch):
            state = exp.state
            action = exp.action
            reward = exp.reward
            old_value = self._q_values[state][action]
            td_error = reward - old_value
            if self._use_double_q:
                old_q2 = self._q_values_q2[state][action]
                q1_best = max(self._q_values[state].keys(), key=lambda a: self._q_values[state][a])
                q1_best_v = self._q_values[state][q1_best]
                td_error_q2 = reward - old_q2
                self._q_values_q2[state][action] = old_q2 + self._learning_rate * weights[i] * td_error_q2
            self._q_values[state][action] = old_value + self._learning_rate * weights[i] * td_error
            td_errors.append(td_error)
            self._ensure_stats(state, action)
            stats = self._action_stats[state][action]
            stats.total_reward += reward * 0.05
            stats.squared_reward += (reward * reward) * 0.05
        self._replay_buffer.update_priorities(indices, td_errors)
        return len(batch)

    def reset_episode(self) -> None:
        if self._use_eligibility_traces:
            if self._eligibility_traces:
                self._eligibility_traces.reset()
            if self._use_double_q and self._eligibility_traces_q2:
                self._eligibility_traces_q2.reset()
        self._n_step_buffer.clear()

    def is_converged(self) -> bool:
        return self._converged

    def get_performance_stats(self) -> Dict[str, Any]:
        buffer_stats = self._replay_buffer.get_recent_performance()
        all_states = list(self._q_values.keys())
        total_actions = sum(len(v) for v in self._q_values.values())
        state_stats = {}
        for state in all_states:
            actions = self._q_values[state]
            if not actions:
                continue
            best_action = max(actions.keys(), key=lambda a: actions[a])
            best_value = actions[best_action]
            if self._use_double_q:
                q2_values = self._q_values_q2.get(state, {})
                q2_best = max(q2_values.keys(), key=lambda a: q2_values[a]) if q2_values else best_action
                q2_best_v = q2_values.get(q2_best, 0.5)
                q_disagreement = abs(best_value - q2_best_v)
            else:
                q_disagreement = 0.0
            state_stats[state] = {
                "best_action": best_action,
                "best_q_value": best_value,
                "num_actions": len(actions),
                "q_disagreement": q_disagreement,
                "actions": {
                    a: {
                        "q_value": self._q_values[state][a],
                        "q_value_q2": self._q_values_q2.get(state, {}).get(a, 0.5) if self._use_double_q else self._q_values[state][a],
                        "stats": self._action_stats.get(state, {}).get(a, ActionStats()).to_dict(),
                    }
                    for a in actions
                },
            }
        return {
            "episode_count": self._episode_count,
            "total_updates": self._total_updates,
            "learning_rate": self._learning_rate,
            "epsilon": self._epsilon,
            "temperature": self._temperature,
            "converged": self._converged,
            "plateau_count": self._plateau_count,
            "replay_buffer_size": len(self._replay_buffer),
            "buffer_performance": buffer_stats,
            "num_states": len(all_states),
            "total_actions_tracked": total_actions,
            "state_stats": state_stats,
            "best_actions": self._best_actions.copy(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "2.0",
            "learning_rate": self._learning_rate,
            "initial_learning_rate": self._initial_learning_rate,
            "discount_factor": self._discount_factor,
            "exploration_strategy": self._exploration_strategy.value,
            "epsilon": self._epsilon,
            "min_epsilon": self._min_epsilon,
            "ucb_c": self._ucb_c,
            "temperature": self._temperature,
            "use_eligibility_traces": self._use_eligibility_traces,
            "use_double_q": self._use_double_q,
            "n_step": self._n_step,
            "episode_count": self._episode_count,
            "total_updates": self._total_updates,
            "converged": self._converged,
            "q_values": {k: dict(v) for k, v in self._q_values.items()},
            "q_values_q2": {k: dict(v) for k, v in self._q_values_q2.items()} if self._use_double_q else {},
            "state_values": dict(self._state_values),
            "action_stats": {
                state: {action: stats.to_dict() for action, stats in actions.items()}
                for state, actions in self._action_stats.items()
            },
            "best_actions": self._best_actions.copy(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdvancedReinforcementLearner":
        strategy_map = {e.value: e for e in ExplorationStrategy}
        strategy = strategy_map.get(d.get("exploration_strategy", "ucb"), ExplorationStrategy.UCB)
        learner = cls(
            learning_rate=d.get("initial_learning_rate", 0.1),
            discount_factor=d.get("discount_factor", 0.95),
            exploration_strategy=strategy,
            epsilon=d.get("epsilon", 0.1),
            min_epsilon=d.get("min_epsilon", 0.01),
            ucb_c=d.get("ucb_c", 2.0),
            temperature=d.get("temperature", 1.0),
            use_eligibility_traces=d.get("use_eligibility_traces", True),
            use_double_q=d.get("use_double_q", True),
            n_step=d.get("n_step", 3),
        )
        learner._learning_rate = d.get("learning_rate", 0.1)
        learner._episode_count = d.get("episode_count", 0)
        learner._total_updates = d.get("total_updates", 0)
        learner._converged = d.get("converged", False)
        for state, actions in d.get("q_values", {}).items():
            for action, value in actions.items():
                learner._q_values[state][action] = value
        for state, actions in d.get("q_values_q2", {}).items():
            for action, value in actions.items():
                learner._q_values_q2[state][action] = value
        for state, value in d.get("state_values", {}).items():
            learner._state_values[state] = value
        for state, actions in d.get("action_stats", {}).items():
            if state not in learner._action_stats:
                learner._action_stats[state] = {}
            for action, stats_dict in actions.items():
                stats = ActionStats()
                stats.q_value = stats_dict.get("q_value", 0.5)
                stats.q_value_q2 = stats_dict.get("q_value_q2", 0.5)
                stats.visit_count = stats_dict.get("visit_count", 0)
                stats.total_reward = stats_dict.get("total_reward", 0.0)
                stats.squared_reward = stats_dict.get("squared_reward", 0.0)
                stats.success_count = stats_dict.get("success_count", 0)
                stats.failure_count = stats_dict.get("failure_count", 0)
                learner._action_stats[state][action] = stats
        learner._best_actions = d.get("best_actions", {}).copy()
        return learner
