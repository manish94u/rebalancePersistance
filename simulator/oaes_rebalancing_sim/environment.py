"""Simulation environment for subscription-aware persistent messaging.

The environment is intentionally simple enough to audit, but it keeps the key
relationships required by the paper:

    per-subscription backlog
        -> connection-level cumulative backlog
        -> pod-level cumulative backlog

The online controller receives only a partial observation. Offline metrics can
inspect the full simulated cluster, but the controller cannot.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .controllers import Action


@dataclass
class Subscription:
    subscription_id: int
    arrival_rate: float
    backlog: float = 0.0
    connection_id: int = 0


@dataclass
class Connection:
    connection_id: int
    pod_id: int
    subscriptions: List[int] = field(default_factory=list)
    age: int = 0


@dataclass
class Pod:
    pod_id: int
    max_processing_threshold: float
    subscription_count: int = 0
    cumulative_backlog: float = 0.0


@dataclass
class ScenarioConfig:
    name: str
    steps: int
    pod_count: int
    subscription_count: int
    initial_connections: int
    max_connections: int
    theta_n: int
    beta: float
    base_arrival_rate: float
    hot_subscription_fraction: float
    hot_multiplier: float
    pod_capacity: float
    client_ack_capacity: float
    burst_start: int = 10**9
    burst_end: int = 10**9
    slowdown_start: int = 10**9
    slowdown_end: int = 10**9
    slowdown_factor: float = 1.0
    initial_backlog_tiers: Tuple[Tuple[float, float], ...] = ()
    initial_assignment_mode: str = "round_robin"
    initial_connection_weights: Tuple[float, ...] = ()
    initial_connection_pods: Tuple[int, ...] = ()
    scale_up_rebalance_to_capacity: bool = False
    # Arrival, Pod-processing, and client-ACK capacities are rates expressed
    # per second.  The simulator advances one controller decision at a time,
    # so this duration converts those rates into interval event counts.  The
    # one-second default preserves all previously recorded experiments.
    decision_interval_seconds: float = 1.0


class SimulationEnvironment:
    """Stateful environment advanced one decision interval at a time."""

    def __init__(self, config: ScenarioConfig, seed: int):
        if (
            not math.isfinite(config.decision_interval_seconds)
            or config.decision_interval_seconds <= 0.0
        ):
            raise ValueError("decision_interval_seconds must be finite and positive")
        self.config = config
        self.rng = random.Random(seed)
        self.t = 0
        self.last_total_backlog = 0.0
        self.throughput_last_step = 0.0
        self.migrations = 0
        self.connection_churn = 0
        self.recent_migration = 0.0
        self.scale_up_subscription_moves = 0
        self.last_scale_up_subscription_moves = 0
        self.last_scale_up_target_restored = False

        self.pods = [
            Pod(pod_id=i, max_processing_threshold=config.pod_capacity)
            for i in range(config.pod_count)
        ]

        if config.initial_connection_pods and (
            len(config.initial_connection_pods) != config.initial_connections
        ):
            raise ValueError(
                "initial_connection_pods must match initial_connections"
            )
        self.connections: List[Connection] = []
        for c in range(config.initial_connections):
            pod_id = (
                config.initial_connection_pods[c]
                if config.initial_connection_pods
                else c % config.pod_count
            )
            if pod_id < 0 or pod_id >= config.pod_count:
                raise ValueError("initial_connection_pods contains an invalid pod")
            self.connections.append(Connection(connection_id=c, pod_id=pod_id))

        self.subscriptions: List[Subscription] = []
        hot_count = int(config.subscription_count * config.hot_subscription_fraction)
        hot_ids = set(self.rng.sample(range(config.subscription_count), hot_count))

        for sid in range(config.subscription_count):
            rate = config.base_arrival_rate
            if sid in hot_ids:
                rate *= config.hot_multiplier
            connection_id = self._initial_connection_for_subscription(sid)
            self.subscriptions.append(
                Subscription(subscription_id=sid, arrival_rate=rate, connection_id=connection_id)
            )
            self.connections[connection_id].subscriptions.append(sid)

        self._apply_initial_backlog_tiers()
        self._refresh_pod_stats()

    def allowed_actions(self) -> List[str]:
        actions = [Action.STAY, Action.REBALANCE_COUNT, Action.REBALANCE_BACKLOG, Action.MIGRATE]
        if len(self.connections) < self.config.max_connections:
            actions.append(Action.SCALE_UP)
        # Scale-down is deliberately guarded. A real client should not close a
        # delivery connection while the workload is still backlogged merely
        # because a learning policy sampled the action.
        min_subs = min(len(connection.subscriptions) for connection in self.connections)
        low_backlog = self.total_backlog() < 0.15 * self._backlog_reference()
        if len(self.connections) > 1 and (min_subs == 0 or (low_backlog and min_subs <= self.config.theta_n // 8)):
            actions.append(Action.SCALE_DOWN)
        return actions

    def observe(self) -> Dict[str, float]:
        """Return the partial client-visible observation vector."""

        total_backlog = self.total_backlog()
        vn = self.connection_subscription_variance()
        vg = self.connection_backlog_variance()
        active_pressure = self._mean_active_pod_pressure()
        probe_pressure = self._probe_pod_pressure()

        return {
            "norm_total_backlog": self._clip(total_backlog / self._backlog_reference()),
            "backlog_growth": self._clip((total_backlog - self.last_total_backlog) / self._backlog_reference()),
            "norm_vn": self._clip(vn / self._vn_reference()),
            "norm_vg": self._clip(vg / self._vg_reference()),
            "connection_utilization": self._clip(len(self.connections) / float(self.config.max_connections)),
            "active_pod_pressure": active_pressure,
            "probe_pod_pressure": probe_pressure,
            "recent_migration": self.recent_migration,
            "norm_throughput": self._clip(self.throughput_last_step / max(1.0, self._client_parallel_capacity())),
        }

    def step(
        self,
        action: str,
        migration_target_pod_id: Optional[int] = None,
        migration_source_connection_id: Optional[int] = None,
    ) -> Dict[str, float]:
        """Apply an action, advance workload dynamics, and return raw metrics.

        ``migration_target_pod_id`` models promotion of the pod sampled by the retained probe.
        ``migration_source_connection_id`` models the concrete source resolved by the deployment
        executor. Existing paper experiments omit both values and preserve their original
        highest-pressure-to-lowest-pressure behavior.
        """

        self.last_total_backlog = self.total_backlog()
        self.last_scale_up_subscription_moves = 0
        self.last_scale_up_target_restored = False
        action_applied = self._apply_action(
            action,
            migration_target_pod_id,
            migration_source_connection_id,
        )

        generated = self._generate_arrivals()
        delivered = self._drain_backlog()

        for connection in self.connections:
            connection.age += 1

        # ``delivered`` is an interval count used for conservation accounting.
        # Observations and rewards consume a rate so that changing the decision
        # cadence does not make an identical transport appear more capable.
        self.throughput_last_step = (
            delivered / self.config.decision_interval_seconds
        )
        self.t += 1
        self.recent_migration = max(0.0, self.recent_migration * 0.75)
        self._refresh_pod_stats()

        return {
            "generated": generated,
            "throughput": delivered,
            "throughput_events_per_second": self.throughput_last_step,
            "total_backlog": self.total_backlog(),
            "p95_subscription_backlog": self.p95_subscription_backlog(),
            "vn": self.connection_subscription_variance(),
            "vg": self.connection_backlog_variance(),
            "connection_imbalance": self.local_imbalance(),
            "pod_pressure": self._mean_active_pod_pressure(),
            "connection_count": float(len(self.connections)),
            "configured_pod_count": float(self.config.pod_count),
            "active_pod_count": float(self.active_pod_count()),
            "max_pod_subscriptions": float(self.max_pod_subscriptions()),
            "pod_subscription_cv": self.pod_subscription_cv(),
            "max_pod_backlog": self.max_pod_backlog(),
            "pod_backlog_cv": self.pod_backlog_cv(),
            "migration_count": float(self.migrations),
            "connection_churn": float(self.connection_churn),
            "scale_up_subscription_moves": float(
                self.last_scale_up_subscription_moves
            ),
            "scale_up_target_restored": (
                1.0 if self.last_scale_up_target_restored else 0.0
            ),
            "action_applied": 1.0 if action_applied else 0.0,
        }

    def reward(self, metrics: Dict[str, float], mode: str = "full") -> float:
        """Compute the deployable scalar reward used by learning controllers."""

        backlog_term = self._clip(metrics["total_backlog"] / self._backlog_reference())
        vn_term = self._clip(metrics["vn"] / self._vn_reference())
        vg_term = self._clip(metrics["vg"] / self._vg_reference())
        pressure_term = self._clip(metrics["pod_pressure"])
        throughput_rate = metrics.get(
            "throughput_events_per_second",
            metrics["throughput"] / self.config.decision_interval_seconds,
        )
        throughput_term = self._clip(
            throughput_rate / max(1.0, self._client_parallel_capacity())
        )
        migration_term = 1.0 if self.recent_migration > 0.0 else 0.0
        connection_cost = len(self.connections) / float(self.config.max_connections)

        if mode == "no_migration_penalty":
            migration_weight = 0.0
        else:
            migration_weight = 0.08

        backlog_weight = 0.0 if mode == "no_backlog_term" else 0.30
        subscription_weight = 0.0 if mode == "no_subscription_term" else 0.18

        return (
            0.30 * throughput_term
            - backlog_weight * backlog_term
            - subscription_weight * vn_term
            - 0.16 * vg_term
            - 0.14 * pressure_term
            - migration_weight * migration_term
            - 0.04 * connection_cost
        )

    def total_backlog(self) -> float:
        return sum(sub.backlog for sub in self.subscriptions)

    def connection_backlog(self, connection: Connection) -> float:
        return sum(self.subscriptions[sid].backlog for sid in connection.subscriptions)

    def connection_subscription_variance(self) -> float:
        values = [len(connection.subscriptions) for connection in self.connections]
        return self._variance(values)

    def connection_backlog_variance(self) -> float:
        values = [self.connection_backlog(connection) for connection in self.connections]
        return self._variance(values)

    def local_imbalance(self) -> float:
        vn = self._clip(self.connection_subscription_variance() / self._vn_reference())
        vg = self._clip(self.connection_backlog_variance() / self._vg_reference())
        return 0.5 * vn + 0.5 * vg

    def p95_subscription_backlog(self) -> float:
        values = sorted(sub.backlog for sub in self.subscriptions)
        if not values:
            return 0.0
        index = int(0.95 * (len(values) - 1))
        return values[index]

    def active_pod_count(self) -> int:
        """Return pods carrying at least one active persistent connection."""

        return len({connection.pod_id for connection in self.connections})

    def max_pod_subscriptions(self) -> int:
        return max((pod.subscription_count for pod in self.pods), default=0)

    def max_pod_backlog(self) -> float:
        return max((pod.cumulative_backlog for pod in self.pods), default=0.0)

    def pod_subscription_cv(self) -> float:
        return self._coefficient_of_variation(float(pod.subscription_count) for pod in self.pods)

    def pod_backlog_cv(self) -> float:
        return self._coefficient_of_variation(pod.cumulative_backlog for pod in self.pods)

    def _apply_action(
        self,
        action: str,
        migration_target_pod_id: Optional[int] = None,
        migration_source_connection_id: Optional[int] = None,
    ) -> bool:
        if action == Action.STAY:
            return True
        if action == Action.REBALANCE_COUNT:
            return self._rebalance_by_count()
        if action == Action.REBALANCE_BACKLOG:
            return self._rebalance_by_backlog()
        if action == Action.SCALE_UP:
            return self._scale_up()
        if action == Action.SCALE_DOWN:
            return self._scale_down()
        if action == Action.MIGRATE:
            return self._migrate_highest_pressure_connection(
                migration_target_pod_id,
                migration_source_connection_id,
            )
        return False

    def _rebalance_by_count(self) -> bool:
        candidate_pairs = []
        for source in self.connections:
            if not source.subscriptions:
                continue
            for target in self.connections:
                if (
                    source is target
                    or len(target.subscriptions) >= self.config.theta_n
                ):
                    continue
                gap = len(source.subscriptions) - len(target.subscriptions)
                if gap >= 2:
                    candidate_pairs.append(
                        (
                            gap,
                            len(source.subscriptions),
                            -len(target.subscriptions),
                            source.connection_id,
                            target.connection_id,
                            source,
                            target,
                        )
                    )
        if not candidate_pairs:
            return False
        *_rank, high, low = max(
            candidate_pairs, key=lambda candidate: candidate[:5]
        )
        # Match the deployment executor: preserve backlog balance while reducing
        # count skew, with subscription id as the deterministic tie-break.
        sid = min(
            high.subscriptions,
            key=lambda item: (self.subscriptions[item].backlog, item),
        )
        high.subscriptions.remove(sid)
        low.subscriptions.append(sid)
        self.subscriptions[sid].connection_id = low.connection_id
        return True

    def _rebalance_by_backlog(self) -> bool:
        candidates = []
        for source in self.connections:
            if not source.subscriptions:
                continue
            source_backlog = self.connection_backlog(source)
            for target in self.connections:
                if (
                    source is target
                    or len(target.subscriptions) >= self.config.theta_n
                ):
                    continue
                before_gap = source_backlog - self.connection_backlog(target)
                if before_gap <= 0.0:
                    continue
                for sid in source.subscriptions:
                    backlog = self.subscriptions[sid].backlog
                    reduction = before_gap - abs(before_gap - 2.0 * backlog)
                    if backlog > 0.01 and reduction > 0.0:
                        candidates.append(
                            (
                                reduction,
                                before_gap,
                                backlog,
                                sid,
                                source.connection_id,
                                target.connection_id,
                                source,
                                target,
                            )
                        )
        if not candidates:
            return False
        selected = max(candidates, key=lambda candidate: candidate[:6])
        (
            _reduction,
            _gap,
            _backlog,
            sid,
            _source_id,
            _target_id,
            high,
            low,
        ) = selected
        high.subscriptions.remove(sid)
        low.subscriptions.append(sid)
        self.subscriptions[sid].connection_id = low.connection_id
        return True

    def _scale_up(self) -> bool:
        if len(self.connections) >= self.config.max_connections:
            return False
        pod_id = min(self.pods, key=self._pod_pressure).pod_id
        new_id = max(c.connection_id for c in self.connections) + 1
        self.connections.append(Connection(connection_id=new_id, pod_id=pod_id))
        self.connection_churn += 1
        self.last_scale_up_subscription_moves = 0
        self.last_scale_up_target_restored = False
        if self.config.scale_up_rebalance_to_capacity:
            while (
                max(len(connection.subscriptions) for connection in self.connections)
                > self.config.theta_n
            ):
                if not self._rebalance_by_count():
                    break
                self.last_scale_up_subscription_moves += 1
                self.scale_up_subscription_moves += 1
            self.last_scale_up_target_restored = (
                max(len(connection.subscriptions) for connection in self.connections)
                <= self.config.theta_n
            )
        return True

    def _scale_down(self) -> bool:
        if len(self.connections) <= 1:
            return False
        low = min(self.connections, key=lambda c: (len(c.subscriptions), self.connection_backlog(c)))
        low_backlog = self.total_backlog() < 0.15 * self._backlog_reference()
        if len(low.subscriptions) > 0 and not low_backlog:
            return False
        if len(low.subscriptions) > max(1, self.config.theta_n // 8):
            return False
        targets = [c for c in self.connections if c.connection_id != low.connection_id]
        target = min(targets, key=lambda c: len(c.subscriptions))
        for sid in list(low.subscriptions):
            target.subscriptions.append(sid)
            self.subscriptions[sid].connection_id = target.connection_id
        self.connections.remove(low)
        self.connection_churn += 1
        return True

    def _migrate_highest_pressure_connection(
        self,
        target_pod_id: Optional[int] = None,
        source_connection_id: Optional[int] = None,
    ) -> bool:
        targeted_deployment_move = (
            target_pod_id is not None and source_connection_id is not None
        )
        if self.recent_migration > 0.10 and not targeted_deployment_move:
            return False
        if target_pod_id is None:
            target_pod = min(self.pods, key=self._pod_pressure)
        else:
            if target_pod_id < 0 or target_pod_id >= len(self.pods):
                raise ValueError("migration_target_pod_id is outside the pod set")
            target_pod = self.pods[target_pod_id]
        candidates = [
            connection
            for connection in self.connections
            if connection.pod_id != target_pod.pod_id
            and connection.subscriptions
        ]
        if not candidates:
            return False
        if source_connection_id is None:
            current = max(
                candidates,
                key=lambda connection: self._pod_pressure(
                    self.pods[connection.pod_id]
                ),
            )
            if (
                self._pod_pressure(self.pods[current.pod_id])
                - self._pod_pressure(target_pod)
                < 0.20
            ):
                return False
        else:
            requested = [
                connection
                for connection in candidates
                if connection.connection_id == source_connection_id
            ]
            if not requested:
                return False
            current = requested[0]
        current.pod_id = target_pod.pod_id
        self.migrations += 1
        self.recent_migration = 1.0
        return True

    def _generate_arrivals(self) -> float:
        if self.config.base_arrival_rate <= 0.0 and self.config.hot_subscription_fraction <= 0.0:
            return 0.0
        generated = 0.0
        burst_active = self.config.burst_start <= self.t <= self.config.burst_end
        for sub in self.subscriptions:
            rate = sub.arrival_rate
            if burst_active and sub.subscription_id % 7 == 0:
                rate *= 3.2
            # Convert the per-second rate to the expected count in this
            # decision interval. Gaussian noise is a lightweight stand-in for
            # stochastic arrivals; its scale follows the square root of the
            # interval count, and negative samples are clipped to zero.
            interval_mean = rate * self.config.decision_interval_seconds
            amount = max(
                0.0,
                self.rng.gauss(
                    interval_mean,
                    max(0.1, math.sqrt(interval_mean) * 0.25),
                ),
            )
            sub.backlog += amount
            generated += amount
        return generated

    def _drain_backlog(self) -> float:
        total_delivered = 0.0
        # Both capacity inputs are rates.  Convert them to event budgets for
        # this decision interval before distributing the budgets across active
        # persistent connections.
        interval_seconds = self.config.decision_interval_seconds
        client_capacity = self._client_parallel_capacity() * interval_seconds
        if self.config.slowdown_start <= self.t <= self.config.slowdown_end:
            client_capacity *= self.config.slowdown_factor

        per_connection_client_capacity = client_capacity / max(1, len(self.connections))

        pod_connection_counts: Dict[int, int] = {}
        for connection in self.connections:
            pod_connection_counts[connection.pod_id] = pod_connection_counts.get(connection.pod_id, 0) + 1

        for connection in self.connections:
            pod = self.pods[connection.pod_id]
            pod_share = (
                pod.max_processing_threshold
                * interval_seconds
                / max(1, pod_connection_counts[connection.pod_id])
            )
            reliability = max(0.35, 1.0 - 0.42 * self._pod_pressure(pod))
            capacity = min(per_connection_client_capacity, pod_share * reliability)
            backlog = self.connection_backlog(connection)
            delivered = min(capacity, backlog)
            total_delivered += delivered

            if backlog <= 0.0:
                continue
            for sid in list(connection.subscriptions):
                sub = self.subscriptions[sid]
                share = delivered * (sub.backlog / backlog)
                sub.backlog = max(0.0, sub.backlog - share)

        return total_delivered

    def _client_parallel_capacity(self) -> float:
        """Return effective client processing capacity after connection scaling.

        Additional persistent connections increase usable client-side
        parallelism, but not linearly forever. The cap preserves the earlier
        modeling point: drain time still depends on client processing capability,
        not only on pod capacity.
        """

        parallel_gain = 1.0 + 0.55 * max(0, len(self.connections) - 1)
        parallel_gain = min(parallel_gain, 3.0)
        return self.config.client_ack_capacity * parallel_gain

    def _refresh_pod_stats(self) -> None:
        for pod in self.pods:
            pod.subscription_count = 0
            pod.cumulative_backlog = 0.0
        for connection in self.connections:
            pod = self.pods[connection.pod_id]
            pod.subscription_count += len(connection.subscriptions)
            pod.cumulative_backlog += self.connection_backlog(connection)

    def _mean_active_pod_pressure(self) -> float:
        if not self.connections:
            return 0.0
        return sum(self._pod_pressure(self.pods[c.pod_id]) for c in self.connections) / len(self.connections)

    def _probe_pod_pressure(self) -> float:
        return self._pod_pressure(self.rng.choice(self.pods))

    def _pod_pressure(self, pod: Pod) -> float:
        sub_pressure = pod.subscription_count / max(1.0, self.config.theta_n * 2.0)
        backlog_pressure = pod.cumulative_backlog / self._backlog_reference()
        capacity_pressure = pod.cumulative_backlog / max(1.0, pod.max_processing_threshold * 4.0)
        return self._clip(0.40 * sub_pressure + 0.35 * backlog_pressure + 0.25 * capacity_pressure)

    def _backlog_reference(self) -> float:
        tiered_backlog = sum(fraction * backlog for fraction, backlog in self.config.initial_backlog_tiers)
        if tiered_backlog > 0.0:
            return max(1.0, tiered_backlog * self.config.subscription_count)
        return max(1.0, self.config.beta * self.config.subscription_count)

    def _initial_connection_for_subscription(self, subscription_id: int) -> int:
        if self.config.initial_assignment_mode == "weighted":
            weights = self.config.initial_connection_weights
            if len(weights) != self.config.initial_connections:
                raise ValueError(
                    "initial_connection_weights must match initial_connections"
                )
            if any(weight < 0.0 for weight in weights) or sum(weights) <= 0.0:
                raise ValueError(
                    "initial_connection_weights must be non-negative with a positive sum"
                )
            position = (subscription_id + 0.5) / self.config.subscription_count
            cumulative = 0.0
            total_weight = sum(weights)
            for connection_id, weight in enumerate(weights):
                cumulative += weight / total_weight
                if position <= cumulative:
                    return connection_id
            return self.config.initial_connections - 1
        if self.config.initial_assignment_mode != "tier_skewed" or not self.config.initial_backlog_tiers:
            return subscription_id % self.config.initial_connections

        cursor = 0
        for tier_index, (fraction, _backlog) in enumerate(self.config.initial_backlog_tiers):
            width = int(round(fraction * self.config.subscription_count))
            if subscription_id < cursor + width:
                return min(tier_index, self.config.initial_connections - 1)
            cursor += width
        return self.config.initial_connections - 1

    def _apply_initial_backlog_tiers(self) -> None:
        if not self.config.initial_backlog_tiers:
            return

        cursor = 0
        for tier_index, (fraction, backlog) in enumerate(self.config.initial_backlog_tiers):
            if tier_index == len(self.config.initial_backlog_tiers) - 1:
                end = self.config.subscription_count
            else:
                end = min(self.config.subscription_count, cursor + int(round(fraction * self.config.subscription_count)))
            for sid in range(cursor, end):
                self.subscriptions[sid].backlog = float(backlog)
            cursor = end

    def _vn_reference(self) -> float:
        sigma_tol = 0.20 * self.config.theta_n
        return max(1.0, sigma_tol * sigma_tol)

    def _vg_reference(self) -> float:
        sigma_tol = 0.20 * self.config.beta * self.config.theta_n
        return max(1.0, sigma_tol * sigma_tol)

    @staticmethod
    def _variance(values: Iterable[float]) -> float:
        values = [float(v) for v in values]
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return sum((value - mean) ** 2 for value in values) / len(values)

    @staticmethod
    def _coefficient_of_variation(values: Iterable[float]) -> float:
        values = [float(v) for v in values]
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        if mean <= 0.0:
            return 0.0
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(variance) / mean

    @staticmethod
    def _clip(value: float) -> float:
        return max(0.0, min(1.0, value))
