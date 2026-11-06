"""Controllers and deployable action templates used by the local simulator.

The controllers in this file intentionally operate only on the client-visible
observation dictionary produced by the environment. They do not inspect the
global simulator state. This mirrors the partial-observability constraint in
the paper: the client can use active connection statistics, one probe sample,
and local queue measurements, but not a perfect cluster-wide view.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


class Action:
    """Names of bounded actions that can be executed by a real client.

    The simulator keeps the actions as strings rather than integers because the
    generated CSV files and tables should remain easy to inspect by hand.
    """

    STAY = "stay"
    REBALANCE_COUNT = "rebalance_count"
    REBALANCE_BACKLOG = "rebalance_backlog"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MIGRATE = "migrate"

    ALL = [
        STAY,
        REBALANCE_COUNT,
        REBALANCE_BACKLOG,
        SCALE_UP,
        SCALE_DOWN,
        MIGRATE,
    ]


@dataclass
class Decision:
    """Controller output for one decision interval."""

    action: str
    reason: str


class BaseController:
    """Shared interface implemented by every controller variant."""

    name = "Base"

    def select_action(self, observation: Dict[str, float], allowed_actions: Iterable[str]) -> Decision:
        raise NotImplementedError

    def observe_transition(
        self,
        observation: Dict[str, float],
        action: str,
        reward: float,
        next_observation: Dict[str, float],
        done: bool,
    ) -> None:
        """Receive a transition after the environment has applied the action.

        Rule-based controllers do not learn, so the default implementation is a
        no-op. Learning controllers override this method.
        """


class StaticController(BaseController):
    """Negative-control baseline: keep the initial assignment forever."""

    name = "Static"

    def select_action(self, observation: Dict[str, float], allowed_actions: Iterable[str]) -> Decision:
        return Decision(Action.STAY, "static baseline")


class HeuristicController(BaseController):
    """Threshold-based controller used as a strong non-learning baseline."""

    name = "Heuristic"

    def select_action(self, observation: Dict[str, float], allowed_actions: Iterable[str]) -> Decision:
        allowed = set(allowed_actions)

        # Subscription-count imbalance is handled first because a connection
        # carrying too many subscriptions can become unreliable even before its
        # backlog becomes extreme.
        if observation["norm_vn"] > 0.45 and Action.REBALANCE_COUNT in allowed:
            return Decision(Action.REBALANCE_COUNT, "subscription-count variance above threshold")

        # Backlog imbalance means at least one connection is accumulating more
        # queued messages than the others.
        if observation["norm_vg"] > 0.45 and Action.REBALANCE_BACKLOG in allowed:
            return Decision(Action.REBALANCE_BACKLOG, "backlog variance above threshold")

        # Scale up only when there is both backlog pressure and room under the
        # configured connection cap.
        if observation["norm_total_backlog"] > 0.55 and Action.SCALE_UP in allowed:
            return Decision(Action.SCALE_UP, "total backlog pressure above threshold")

        # Migrate only if the sampled probe pod is substantially better than the
        # current active pod pressure. This is the local version of hysteresis.
        pressure_gap = observation["active_pod_pressure"] - observation["probe_pod_pressure"]
        if pressure_gap > 0.18 and Action.MIGRATE in allowed:
            return Decision(Action.MIGRATE, "probe pod has lower pressure")

        if observation["connection_utilization"] < 0.25 and Action.SCALE_DOWN in allowed:
            return Decision(Action.SCALE_DOWN, "connections are lightly utilized")

        return Decision(Action.STAY, "no heuristic trigger")


class EpsilonGreedyController(BaseController):
    """Simple action-value baseline without a neural network.

    This baseline is intentionally weaker than DQL, but useful. It answers the
    question: do we need a deep value function, or is one scalar value per action
    enough for this workload?
    """

    name = "EpsilonGreedy"

    def __init__(self, seed: int, epsilon: float = 0.18, alpha: float = 0.12):
        self.rng = random.Random(seed)
        self.epsilon = epsilon
        self.alpha = alpha
        self.q_values = {action: 0.0 for action in Action.ALL}

    def select_action(self, observation: Dict[str, float], allowed_actions: Iterable[str]) -> Decision:
        allowed = list(allowed_actions)
        if self.rng.random() < self.epsilon:
            return Decision(self.rng.choice(allowed), "epsilon exploration")

        best_action = max(allowed, key=lambda action: self.q_values.get(action, 0.0))
        return Decision(best_action, "highest learned action value")

    def observe_transition(
        self,
        observation: Dict[str, float],
        action: str,
        reward: float,
        next_observation: Dict[str, float],
        done: bool,
    ) -> None:
        old_value = self.q_values.get(action, 0.0)
        self.q_values[action] = old_value + self.alpha * (reward - old_value)

        # A small decay makes exploration high early and lower later.
        self.epsilon = max(0.03, self.epsilon * 0.995)
