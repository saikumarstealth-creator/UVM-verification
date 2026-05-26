"""
Advanced Reinforcement Learner for UVM Testbench Generation Strategy Selection.

Key improvements for promotion:
1. Experience replay buffer for more stable learning
2. Eligibility traces for better credit assignment
3. Upper Confidence Bound (UCB) for exploration-exploitation balance
4. Multi-armed bandit strategies (epsilon-greedy, softmax, UCB)
5. Contextual bandits considering spec features
6. Learning rate scheduling
7. Value function approximation with state aggregation
8. Performance tracking and strategy comparison
"""

from __future__ import annotations

import logging
import math
import random
import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Deque
from enum import Enum
from datetime import datetime

logger = logging.getLogger("uvmgen.ml.rl")


class ExplorationStrategy(Enum):
    EPSILON_GREEDY = "epsilon_greedy"
    SOFTMAX = "softmax"
    UCB = "ucb"
    THOMPSON_SAMPLING = "thompson_sampling"


@dataclass
class Experience:
    """Single experience for replay buffer."""
    state: str
    action: str
    reward: float
    next_state: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionStats:
    """Statistics for an action."""
    q_value: float = 0.5
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "q_value": self.q_value,
            "visit_count": self.visit_count,
            "total_reward": self.total_reward,
            "squared_reward": self.squared_reward,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "mean_reward": self.mean_reward,
            "variance": self.variance,
            "std_dev": self.std_dev,
            "success_rate": self.success_rate,
        }


class ExperienceReplayBuffer:
    """Buffer for storing and sampling experiences."""

    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.buffer: Deque[Experience] = deque(maxlen=capacity)
        self._episode_rewards: List[float] = []

    def add(self, experience: Experience) -> None:
        """Add an experience to the buffer."""
        self.buffer.append(experience)

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample a batch of experiences randomly."""
        if len(self.buffer) < batch_size:
            return list(self.buffer)
        return random.sample(list(self.buffer), batch_size)

    def sample_recent(self, batch_size: int, recency_weight: float = 0.8) -> List[Experience]:
        """Sample with preference to recent experiences."""
        if len(self.buffer) < batch_size:
            return list(self.buffer)

        recent_count = int(batch_size * recency_weight)
        random_count = batch_size - recent_count

        recent = list(self.buffer)[-recent_count:] if recent_count > 0 else []
        random_part = random.sample(
            list(self.buffer)[:-recent_count] if recent_count > 0 else list(self.buffer),
            min(random_count, len(self.buffer) - recent_count)
        ) if random_count > 0 else []

        return recent + random_part

    def get_all_by_state(self, state: str) -> List[Experience]:
        """Get all experiences for a specific state."""
        return [e for e in self.buffer if e.state == state]

    def record_episode_reward(self, reward: float) -> None:
        """Record episode-level reward for tracking."""
        self._episode_rewards.append(reward)
        if len(self._episode_rewards) > 1000:
            self._episode_rewards = self._episode_rewards[-1000:]

    def get_recent_performance(self, window: int = 100) -> Dict[str, float]:
        """Get recent performance statistics."""
        if not self._episode_rewards:
            return {"mean": 0.5, "std": 0.0, "trend": 0.0}

        recent = self._episode_rewards[-window:]
        mean = sum(recent) / len(recent)

        variance = sum((r - mean) ** 2 for r in recent) / len(recent)
        std = math.sqrt(max(0.0, variance))

        if len(recent) >= 20:
            first_half = recent[:len(recent)//2]
            second_half = recent[len(recent)//2:]
            trend = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
        else:
            trend = 0.0

        return {
            "mean": mean,
            "std": std,
            "trend": trend,
            "count": len(recent),
        }

    def __len__(self) -> int:
        return len(self.buffer)


class EligibilityTraces:
    """Eligibility traces for better credit assignment."""

    def __init__(self, lambda_: float = 0.9, discount: float = 0.95):
        self.lambda_ = lambda_
        self.discount = discount
        self._traces: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def update(self, state: str, action: str) -> None:
        """Update trace for visited state-action pair."""
        for s in list(self._traces.keys()):
            for a in list(self._traces[s].keys()):
                self._traces[s][a] *= self.lambda_ * self.discount

        self._traces[state][action] = 1.0

    def get_trace(self, state: str, action: str) -> float:
        """Get the eligibility trace value."""
        return self._traces.get(state, {}).get(action, 0.0)

    def decay_all(self) -> None:
        """Decay all traces."""
        for s in self._traces:
            for a in self._traces[s]:
                self._traces[s][a] *= self.lambda_ * self.discount

    def reset(self) -> None:
        """Reset all traces."""
        self._traces.clear()


class ContextualBanditFeatures:
    """Feature extraction for contextual bandits."""

    @staticmethod
    def extract_features(
        spec_dict: Dict[str, Any],
        file_type: str,
    ) -> Dict[str, Any]:
        """Extract features from spec and context."""
        features = {}

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
            "testbench": 0.3,
            "interface": 0.25,
            "test": 0.2,
            "sequence": 0.15,
            "driver": 0.1,
            "monitor": 0.1,
            "agent": 0.1,
            "scoreboard": 0.15,
            "ral_model": 0.2,
            "env": 0.15,
        }
        features["file_type_weight"] = file_type_weights.get(file_type, 0.1)

        return features

    @staticmethod
    def get_state_key(
        protocol: str,
        file_type: str,
        complexity_bucket: str,
    ) -> str:
        """Generate a state key for RL."""
        return f"{protocol}:{file_type}:{complexity_bucket}"

    @staticmethod
    def bucket_complexity(complexity: float) -> str:
        """Bucket complexity into discrete levels."""
        if complexity < 0.3:
            return "low"
        elif complexity < 0.6:
            return "medium"
        else:
            return "high"


class AdvancedReinforcementLearner:
    """
    Advanced RL learner with multiple strategies and improvements.

    Key features:
    - Experience replay buffer
    - Eligibility traces
    - Multiple exploration strategies
    - Contextual bandit support
    - Learning rate scheduling
    - Performance tracking
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
        use_eligibility_traces: bool = True,
        lambda_: float = 0.9,
        replay_buffer_capacity: int = 10000,
    ):
        self._learning_rate = learning_rate
        self._initial_learning_rate = learning_rate
        self._discount_factor = discount_factor

        self._exploration_strategy = exploration_strategy
        self._epsilon = epsilon
        self._epsilon_decay = epsilon_decay
        self._min_epsilon = min_epsilon
        self._ucb_c = ucb_c
        self._temperature = temperature

        self._q_values: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: 0.5))
        self._action_stats: Dict[str, Dict[str, ActionStats]] = defaultdict(dict)
        self._total_updates: int = 0

        self._use_eligibility_traces = use_eligibility_traces
        if use_eligibility_traces:
            self._eligibility_traces = EligibilityTraces(lambda_=lambda_, discount=discount_factor)

        self._replay_buffer = ExperienceReplayBuffer(capacity=replay_buffer_capacity)

        self._episode_count: int = 0
        self._best_actions: Dict[str, str] = {}

    def _get_state_key(
        self,
        protocol: str,
        file_type: str,
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate state key with optional context."""
        if spec_dict:
            features = ContextualBanditFeatures.extract_features(spec_dict, file_type)
            complexity_bucket = ContextualBanditFeatures.bucket_complexity(features["complexity"])
            return ContextualBanditFeatures.get_state_key(protocol, file_type, complexity_bucket)
        return f"{protocol}:{file_type}"

    def _ensure_stats(self, state: str, action: str) -> None:
        """Ensure action stats exist for state-action pair."""
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
        """Get the Q-value for a state-action pair."""
        state = self._get_state_key(protocol, file_type, spec_dict)
        return self._q_values[state][generation_source]

    def get_action_stats(
        self,
        protocol: str,
        file_type: str,
        generation_source: str,
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> Optional[ActionStats]:
        """Get statistics for an action."""
        state = self._get_state_key(protocol, file_type, spec_dict)
        return self._action_stats.get(state, {}).get(generation_source)

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
        """Update Q-values with reward, using eligibility traces if enabled."""
        state = self._get_state_key(protocol, file_type, spec_dict)

        self._ensure_stats(state, generation_source)
        stats = self._action_stats[state][generation_source]

        old_value = self._q_values[state][generation_source]

        if next_state and self._q_values.get(next_state):
            next_max = max(self._q_values[next_state].values()) if self._q_values[next_state] else 0.5
            target = reward + self._discount_factor * next_max
        else:
            target = reward

        td_error = target - old_value

        if self._use_eligibility_traces and self._eligibility_traces:
            self._eligibility_traces.update(state, generation_source)

            for s in list(self._q_values.keys()):
                for a in list(self._q_values[s].keys()):
                    trace = self._eligibility_traces.get_trace(s, a)
                    if trace > 0:
                        self._q_values[s][a] += self._learning_rate * td_error * trace
        else:
            self._q_values[state][generation_source] = old_value + self._learning_rate * td_error

        stats.visit_count += 1
        stats.total_reward += reward
        stats.squared_reward += reward * reward
        stats.q_value = self._q_values[state][generation_source]

        if reward >= 0.5:
            stats.success_count += 1
        else:
            stats.failure_count += 1

        self._total_updates += 1

        experience = Experience(
            state=state,
            action=generation_source,
            reward=reward,
            next_state=next_state,
            metadata=metadata or {},
        )
        self._replay_buffer.add(experience)
        self._replay_buffer.record_episode_reward(reward)

        actions = self._q_values[state]
        if actions:
            self._best_actions[state] = max(actions.keys(), key=lambda a: actions[a])

    def _select_epsilon_greedy(
        self,
        state: str,
        available_sources: List[str],
    ) -> Tuple[str, float]:
        """Select action using epsilon-greedy strategy."""
        if random.random() < self._epsilon and len(available_sources) > 1:
            chosen = random.choice(available_sources)
            return chosen, self._q_values[state][chosen]

        best_source = available_sources[0]
        best_value = -1.0

        for source in available_sources:
            value = self._q_values[state][source]
            if value > best_value:
                best_value = value
                best_source = source

        return best_source, best_value

    def _select_softmax(
        self,
        state: str,
        available_sources: List[str],
    ) -> Tuple[str, float]:
        """Select action using softmax (Boltzmann) exploration."""
        values = [self._q_values[state][s] for s in available_sources]

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
        self,
        state: str,
        available_sources: List[str],
    ) -> Tuple[str, float]:
        """Select action using Upper Confidence Bound (UCB1)."""
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
            q_value = self._q_values[state][source]

            if stats.visit_count == 0:
                ucb = float('inf')
            else:
                exploration = self._ucb_c * math.sqrt(
                    math.log(total_visits) / stats.visit_count
                )
                ucb = q_value + exploration

            if ucb > best_ucb:
                best_ucb = ucb
                best_source = source

        return best_source, self._q_values[state][best_source]

    def _select_thompson(
        self,
        state: str,
        available_sources: List[str],
    ) -> Tuple[str, float]:
        """Select action using Thompson sampling (Beta distribution)."""
        samples = []

        for source in available_sources:
            stats = self._action_stats.get(state, {}).get(source, ActionStats())

            alpha = 1 + stats.success_count
            beta_val = 1 + stats.failure_count

            try:
                import random as rnd
                sample = rnd.betavariate(alpha, beta_val)
            except (ImportError, AttributeError):
                sample = stats.success_rate + random.gauss(0, 0.1)
                sample = max(0.0, min(1.0, sample))

            samples.append((source, sample, self._q_values[state][source]))

        samples.sort(key=lambda x: x[1], reverse=True)
        return samples[0][0], samples[0][2]

    def select_best_action(
        self,
        protocol: str,
        file_type: str,
        available_sources: List[str],
        spec_dict: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, float]:
        """
        Select the best action using configured exploration strategy.

        Returns:
            Tuple of (chosen_source, expected_value)
        """
        state = self._get_state_key(protocol, file_type, spec_dict)

        if len(available_sources) == 0:
            return "template", 0.5

        if len(available_sources) == 1:
            return available_sources[0], self._q_values[state][available_sources[0]]

        for source in available_sources:
            if source not in self._q_values[state]:
                self._q_values[state][source] = 0.5

        if self._exploration_strategy == ExplorationStrategy.EPSILON_GREEDY:
            result = self._select_epsilon_greedy(state, available_sources)
        elif self._exploration_strategy == ExplorationStrategy.SOFTMAX:
            result = self._select_softmax(state, available_sources)
        elif self._exploration_strategy == ExplorationStrategy.UCB:
            result = self._select_ucb(state, available_sources)
        elif self._exploration_strategy == ExplorationStrategy.THOMPSON_SAMPLING:
            result = self._select_thompson(state, available_sources)
        else:
            result = self._select_ucb(state, available_sources)

        if self._exploration_strategy == ExplorationStrategy.EPSILON_GREEDY:
            self._epsilon = max(self._min_epsilon, self._epsilon * self._epsilon_decay)

        self._episode_count += 1

        decay = max(0.001, 1.0 / math.sqrt(self._total_updates + 1))
        self._learning_rate = self._initial_learning_rate * decay

        return result

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
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

            state_stats[state] = {
                "best_action": best_action,
                "best_q_value": best_value,
                "num_actions": len(actions),
                "actions": {
                    a: {
                        "q_value": self._q_values[state][a],
                        "stats": self._action_stats.get(state, {}).get(a, ActionStats()).to_dict()
                    }
                    for a in actions
                },
            }

        return {
            "episode_count": self._episode_count,
            "total_updates": self._total_updates,
            "learning_rate": self._learning_rate,
            "epsilon": self._epsilon,
            "exploration_strategy": self._exploration_strategy.value,
            "replay_buffer_size": len(self._replay_buffer),
            "buffer_performance": buffer_stats,
            "num_states": len(all_states),
            "total_actions_tracked": total_actions,
            "state_stats": state_stats,
            "best_actions": self._best_actions.copy(),
        }

    def replay_experiences(self, batch_size: int = 32, use_recency: bool = True) -> int:
        """
        Replay experiences from buffer for additional learning.

        Returns:
            Number of experiences replayed
        """
        if use_recency:
            batch = self._replay_buffer.sample_recent(batch_size)
        else:
            batch = self._replay_buffer.sample(batch_size)

        if not batch:
            return 0

        for exp in batch:
            state = exp.state
            action = exp.action
            reward = exp.reward

            old_value = self._q_values[state][action]
            self._q_values[state][action] = (
                old_value + self._learning_rate * (reward - old_value)
            )

            self._ensure_stats(state, action)
            stats = self._action_stats[state][action]
            stats.total_reward += reward * 0.1
            stats.squared_reward += (reward * reward) * 0.1

        return len(batch)

    def reset_episode(self) -> None:
        """Reset for a new episode (clears eligibility traces)."""
        if self._use_eligibility_traces and self._eligibility_traces:
            self._eligibility_traces.reset()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "learning_rate": self._learning_rate,
            "initial_learning_rate": self._initial_learning_rate,
            "discount_factor": self._discount_factor,
            "exploration_strategy": self._exploration_strategy.value,
            "epsilon": self._epsilon,
            "epsilon_decay": self._epsilon_decay,
            "min_epsilon": self._min_epsilon,
            "ucb_c": self._ucb_c,
            "temperature": self._temperature,
            "use_eligibility_traces": self._use_eligibility_traces,
            "episode_count": self._episode_count,
            "total_updates": self._total_updates,
            "q_values": {k: dict(v) for k, v in self._q_values.items()},
            "action_stats": {
                state: {action: stats.to_dict() for action, stats in actions.items()}
                for state, actions in self._action_stats.items()
            },
            "best_actions": self._best_actions.copy(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdvancedReinforcementLearner":
        strategy_map = {e.value: e for e in ExplorationStrategy}
        strategy = strategy_map.get(
            d.get("exploration_strategy", "ucb"),
            ExplorationStrategy.UCB
        )

        learner = cls(
            learning_rate=d.get("initial_learning_rate", 0.1),
            discount_factor=d.get("discount_factor", 0.95),
            exploration_strategy=strategy,
            epsilon=d.get("epsilon", 0.1),
            epsilon_decay=d.get("epsilon_decay", 0.995),
            min_epsilon=d.get("min_epsilon", 0.01),
            ucb_c=d.get("ucb_c", 2.0),
            temperature=d.get("temperature", 1.0),
            use_eligibility_traces=d.get("use_eligibility_traces", True),
        )

        learner._learning_rate = d.get("learning_rate", 0.1)
        learner._episode_count = d.get("episode_count", 0)
        learner._total_updates = d.get("total_updates", 0)

        for state, actions in d.get("q_values", {}).items():
            for action, value in actions.items():
                learner._q_values[state][action] = value

        for state, actions in d.get("action_stats", {}).items():
            if state not in learner._action_stats:
                learner._action_stats[state] = {}
            for action, stats_dict in actions.items():
                stats = ActionStats()
                stats.q_value = stats_dict.get("q_value", 0.5)
                stats.visit_count = stats_dict.get("visit_count", 0)
                stats.total_reward = stats_dict.get("total_reward", 0.0)
                stats.squared_reward = stats_dict.get("squared_reward", 0.0)
                stats.success_count = stats_dict.get("success_count", 0)
                stats.failure_count = stats_dict.get("failure_count", 0)
                learner._action_stats[state][action] = stats

        learner._best_actions = d.get("best_actions", {}).copy()

        return learner
