"""Dependency-free Deep Q-Learning controller.

This is a compact implementation for research simulation. It is not intended to
replace PyTorch or TensorFlow. The goal is to make the DQL loop in the paper
concrete and reproducible in an environment where external ML packages are not
installed.

The network is:

    observation vector -> hidden ReLU layer -> one Q-value per action

The controller keeps both an online network and a target network. The online
network is updated every step from replay samples. The target network is copied
from the online network periodically to stabilize Bellman targets.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .controllers import Action, BaseController, Decision


OBSERVATION_KEYS = [
    "norm_total_backlog",
    "backlog_growth",
    "norm_vn",
    "norm_vg",
    "connection_utilization",
    "active_pod_pressure",
    "probe_pod_pressure",
    "recent_migration",
    "norm_throughput",
]


@dataclass
class Transition:
    """One replay-buffer item."""

    state: List[float]
    action_index: int
    reward: float
    next_state: List[float]
    done: bool


class TinyQNetwork:
    """Small fully connected neural network with one hidden ReLU layer."""

    def __init__(self, input_size: int, hidden_size: int, output_size: int, rng: random.Random):
        scale_in = 1.0 / math.sqrt(input_size)
        scale_hidden = 1.0 / math.sqrt(hidden_size)

        self.w1 = [
            [rng.uniform(-scale_in, scale_in) for _ in range(input_size)]
            for _ in range(hidden_size)
        ]
        self.b1 = [0.0 for _ in range(hidden_size)]
        self.w2 = [
            [rng.uniform(-scale_hidden, scale_hidden) for _ in range(hidden_size)]
            for _ in range(output_size)
        ]
        self.b2 = [0.0 for _ in range(output_size)]

    def copy_from(self, other: "TinyQNetwork") -> None:
        self.w1 = [row[:] for row in other.w1]
        self.b1 = other.b1[:]
        self.w2 = [row[:] for row in other.w2]
        self.b2 = other.b2[:]

    def forward(self, x: Sequence[float]) -> Tuple[List[float], List[float], List[float]]:
        hidden_raw = []
        hidden = []
        for row, bias in zip(self.w1, self.b1):
            value = bias + sum(weight * feature for weight, feature in zip(row, x))
            hidden_raw.append(value)
            hidden.append(max(0.0, value))

        q_values = []
        for row, bias in zip(self.w2, self.b2):
            q_values.append(bias + sum(weight * h for weight, h in zip(row, hidden)))

        return hidden_raw, hidden, q_values

    def train_one(self, x: Sequence[float], action_index: int, target: float, learning_rate: float) -> float:
        """Run one gradient step for the selected action's squared error."""

        hidden_raw, hidden, q_values = self.forward(x)
        prediction = q_values[action_index]
        error = prediction - target

        # Clip the error to prevent a single extreme transition from exploding
        # the tiny hand-written network.
        error = max(-5.0, min(5.0, error))

        old_w2_action = self.w2[action_index][:]

        # Update output layer only for the selected action. Other Q-values are
        # not directly part of this sample's loss.
        for j, h in enumerate(hidden):
            self.w2[action_index][j] -= learning_rate * error * h
        self.b2[action_index] -= learning_rate * error

        # Backpropagate through ReLU into the hidden layer.
        for j, raw in enumerate(hidden_raw):
            if raw <= 0.0:
                continue
            grad_hidden = error * old_w2_action[j]
            for k, feature in enumerate(x):
                self.w1[j][k] -= learning_rate * grad_hidden * feature
            self.b1[j] -= learning_rate * grad_hidden

        return 0.5 * error * error


class DQLController(BaseController):
    """Deep Q-learning controller with online/target networks and replay."""

    name = "DQL"

    def __init__(
        self,
        seed: int,
        reward_mode: str = "full",
        hidden_size: int = 14,
        gamma: float = 0.92,
        learning_rate: float = 0.018,
        epsilon: float = 0.28,
        epsilon_min: float = 0.04,
        epsilon_decay: float = 0.992,
        replay_capacity: int = 500,
        batch_size: int = 8,
        train_interval: int = 8,
        target_sync_interval: int = 25,
        use_target_network: bool = True,
        use_replay_buffer: bool = True,
    ):
        self.rng = random.Random(seed)
        self.reward_mode = reward_mode
        self.gamma = gamma
        self.learning_rate = learning_rate
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.train_interval = train_interval
        self.target_sync_interval = target_sync_interval
        self.replay_capacity = replay_capacity
        self.use_target_network = use_target_network
        self.use_replay_buffer = use_replay_buffer
        self.steps = 0
        self.last_loss = 0.0

        self.actions = Action.ALL[:]
        self.online = TinyQNetwork(len(OBSERVATION_KEYS), hidden_size, len(self.actions), self.rng)
        self.target = TinyQNetwork(len(OBSERVATION_KEYS), hidden_size, len(self.actions), self.rng)
        self.target.copy_from(self.online)
        self.replay: List[Transition] = []

    def _vectorize(self, observation: Dict[str, float]) -> List[float]:
        return [float(observation.get(key, 0.0)) for key in OBSERVATION_KEYS]

    def select_action(self, observation: Dict[str, float], allowed_actions: Iterable[str]) -> Decision:
        allowed = list(allowed_actions)

        # Deployment guards encode obvious safety reactions before the learned
        # max-Q choice is used. This mirrors the paper's design: DQL selects
        # among bounded templates, but the executor still enforces operational
        # guardrails.
        if (
            self.reward_mode != "no_backlog_term"
            and observation["norm_total_backlog"] > 0.72
            and Action.SCALE_UP in allowed
        ):
            return Decision(Action.SCALE_UP, "DQL guard: severe backlog pressure")
        if (
            self.reward_mode != "no_backlog_term"
            and observation["norm_vg"] > 0.62
            and Action.REBALANCE_BACKLOG in allowed
        ):
            return Decision(Action.REBALANCE_BACKLOG, "DQL guard: severe backlog imbalance")
        if (
            self.reward_mode != "no_subscription_term"
            and observation["norm_vn"] > 0.62
            and Action.REBALANCE_COUNT in allowed
        ):
            return Decision(Action.REBALANCE_COUNT, "DQL guard: severe subscription imbalance")

        if self.rng.random() < self.epsilon:
            return Decision(self.rng.choice(allowed), "DQL epsilon exploration")

        state = self._vectorize(observation)
        _, _, q_values = self.online.forward(state)
        allowed_indices = [self.actions.index(action) for action in allowed]
        best_index = max(allowed_indices, key=lambda idx: q_values[idx])
        return Decision(self.actions[best_index], "DQL max-Q action")

    def observe_transition(
        self,
        observation: Dict[str, float],
        action: str,
        reward: float,
        next_observation: Dict[str, float],
        done: bool,
    ) -> None:
        state = self._vectorize(observation)
        next_state = self._vectorize(next_observation)
        action_index = self.actions.index(action)

        transition = Transition(state, action_index, reward, next_state, done)
        if self.use_replay_buffer:
            self.replay.append(transition)
            if len(self.replay) > self.replay_capacity:
                self.replay.pop(0)

            if len(self.replay) >= self.batch_size and self.steps % self.train_interval == 0:
                self._train_batch()
        elif self.steps % self.train_interval == 0:
            self.last_loss = self._train_transition(transition)

        self.steps += 1
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        if self.use_target_network and self.steps % self.target_sync_interval == 0:
            self.target.copy_from(self.online)

    def _train_batch(self) -> None:
        batch = self.rng.sample(self.replay, self.batch_size)
        total_loss = 0.0

        for item in batch:
            total_loss += self._train_transition(item)

        self.last_loss = total_loss / float(self.batch_size)

    def _train_transition(self, item: Transition) -> float:
        target_network = self.target if self.use_target_network else self.online
        _, _, next_q = target_network.forward(item.next_state)
        target = item.reward
        if not item.done:
            target += self.gamma * max(next_q)
        return self.online.train_one(
            item.state,
            item.action_index,
            target,
            self.learning_rate,
        )
