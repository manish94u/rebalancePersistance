#!/usr/bin/env python3
"""Run local simulation experiments for the rebalancing paper.

The runner is deliberately explicit. Every scenario, controller variant, and
seed is declared in this file so that a reviewer can reproduce the exact local
simulation artifacts used by the paper.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from oaes_rebalancing_sim.controllers import (  # noqa: E402
    Action,
    EpsilonGreedyController,
    HeuristicController,
    StaticController,
)
from oaes_rebalancing_sim.dql import DQLController  # noqa: E402
from oaes_rebalancing_sim.environment import ScenarioConfig, SimulationEnvironment  # noqa: E402
from oaes_rebalancing_sim.metrics import MetricsWriter  # noqa: E402


def scenario_configs(steps_override: int):
    """Return the local workloads used in the paper's simulator section."""

    return [
        ScenarioConfig(
            name="steady_high_subscription",
            steps=steps_override,
            pod_count=4,
            subscription_count=220,
            initial_connections=2,
            max_connections=6,
            theta_n=70,
            beta=12.0,
            base_arrival_rate=1.35,
            hot_subscription_fraction=0.18,
            hot_multiplier=2.1,
            pod_capacity=125.0,
            client_ack_capacity=170.0,
        ),
        ScenarioConfig(
            name="bursty_backlog",
            steps=steps_override,
            pod_count=4,
            subscription_count=180,
            initial_connections=2,
            max_connections=6,
            theta_n=60,
            beta=10.0,
            base_arrival_rate=1.25,
            hot_subscription_fraction=0.16,
            hot_multiplier=2.4,
            pod_capacity=115.0,
            client_ack_capacity=145.0,
            burst_start=45,
            burst_end=95,
        ),
        ScenarioConfig(
            name="client_slowdown",
            steps=steps_override,
            pod_count=4,
            subscription_count=180,
            initial_connections=2,
            max_connections=6,
            theta_n=60,
            beta=10.0,
            base_arrival_rate=1.18,
            hot_subscription_fraction=0.20,
            hot_multiplier=2.2,
            pod_capacity=130.0,
            client_ack_capacity=160.0,
            slowdown_start=55,
            slowdown_end=105,
            slowdown_factor=0.48,
        ),
    ]


def make_controller(variant: str, seed: int):
    """Factory for every compared policy variant."""

    if variant == "Static":
        return StaticController()
    if variant == "Heuristic":
        return HeuristicController()
    if variant == "EpsilonGreedy":
        return EpsilonGreedyController(seed=seed + 1000)
    if variant == "DQL":
        return DQLController(seed=seed + 2000, reward_mode="full")
    if variant == "DQL-NoMigrationPenalty":
        return DQLController(seed=seed + 3000, reward_mode="no_migration_penalty")
    if variant == "DQL-NoBacklogTerm":
        return DQLController(seed=seed + 4000, reward_mode="no_backlog_term")
    if variant == "DQL-NoSubscriptionTerm":
        return DQLController(seed=seed + 5000, reward_mode="no_subscription_term")
    if variant == "DQL-NoRebalancingAction":
        return DQLController(seed=seed + 6000, reward_mode="full")
    if variant == "DQL-NoProbe":
        return DQLController(seed=seed + 7000, reward_mode="full")
    if variant == "DQL-NoTargetNetwork":
        return DQLController(seed=seed + 8000, reward_mode="full", use_target_network=False)
    if variant == "DQL-NoReplayBuffer":
        return DQLController(seed=seed + 9000, reward_mode="full", use_replay_buffer=False)
    if variant == "DQL-NoConnectionScaling":
        return DQLController(seed=seed + 10000, reward_mode="full")
    raise ValueError(f"Unknown variant: {variant}")


def filtered_allowed_actions(variant: str, allowed_actions):
    actions = list(allowed_actions)
    if variant == "DQL-NoRebalancingAction":
        actions = [
            action
            for action in actions
            if action not in {Action.REBALANCE_COUNT, Action.REBALANCE_BACKLOG}
        ]
    if variant == "DQL-NoConnectionScaling":
        actions = [
            action
            for action in actions
            if action not in {Action.SCALE_UP, Action.SCALE_DOWN}
        ]
    return actions


def observed_for_variant(variant: str, observation):
    if variant != "DQL-NoProbe":
        return observation
    modified = dict(observation)
    # Hide the additional random probe signal by replacing it with the mean
    # pressure already visible through active connections. The controller still
    # sees local connection and backlog state, but loses off-path pod sampling.
    modified["probe_pod_pressure"] = modified["active_pod_pressure"]
    return modified


def oracle_action(observation, allowed_actions):
    """Return an offline oracle label for model-diagnostic evaluation.

    The oracle is not used by the controller. It converts the observable
    pressure signals into a deterministic action label so that accuracy and
    ROC-AUC style diagnostics can be reported without pretending that DQL is a
    supervised classifier.
    """

    allowed = set(allowed_actions)
    rebalance_candidates = []
    if observation["norm_vn"] > 0.45 and Action.REBALANCE_COUNT in allowed:
        rebalance_candidates.append((observation["norm_vn"], Action.REBALANCE_COUNT))
    if observation["norm_vg"] > 0.45 and Action.REBALANCE_BACKLOG in allowed:
        rebalance_candidates.append((observation["norm_vg"], Action.REBALANCE_BACKLOG))
    if rebalance_candidates:
        return max(rebalance_candidates, key=lambda item: item[0])[1]
    if observation["norm_total_backlog"] > 0.55 and Action.SCALE_UP in allowed:
        return Action.SCALE_UP
    pressure_gap = observation["active_pod_pressure"] - observation["probe_pod_pressure"]
    if pressure_gap > 0.18 and Action.MIGRATE in allowed:
        return Action.MIGRATE
    if observation["connection_utilization"] < 0.25 and Action.SCALE_DOWN in allowed:
        return Action.SCALE_DOWN
    return Action.STAY


def intervention_score(observation):
    """Continuous score for ROC-AUC against an intervention/no-intervention label."""

    scale_down_pressure = max(0.0, 0.25 - observation["connection_utilization"]) / 0.25
    probe_pressure_gap = max(0.0, observation["active_pod_pressure"] - observation["probe_pod_pressure"])
    return max(
        observation["norm_total_backlog"],
        observation["norm_vn"],
        observation["norm_vg"],
        probe_pressure_gap,
        scale_down_pressure,
    )


def rebalance_score(observation):
    """Continuous score for ROC-AUC against a rebalance/no-rebalance label."""

    return max(observation["norm_vn"], observation["norm_vg"])


def run_one(writer: MetricsWriter, config: ScenarioConfig, variant: str, seed: int) -> None:
    env = SimulationEnvironment(config, seed=seed)
    controller = make_controller(variant, seed)
    reward_mode = getattr(controller, "reward_mode", "full")

    observation = env.observe()
    for _ in range(config.steps):
        policy_observation = observed_for_variant(variant, observation)
        base_allowed = env.allowed_actions()
        allowed = filtered_allowed_actions(variant, base_allowed)
        decision = controller.select_action(policy_observation, allowed)
        oracle = oracle_action(policy_observation, base_allowed)
        oracle_intervention = 0.0 if oracle == Action.STAY else 1.0
        chosen_intervention = 0.0 if decision.action == Action.STAY else 1.0
        oracle_rebalance = 1.0 if oracle in {Action.REBALANCE_COUNT, Action.REBALANCE_BACKLOG} else 0.0
        chosen_rebalance = (
            1.0 if decision.action in {Action.REBALANCE_COUNT, Action.REBALANCE_BACKLOG} else 0.0
        )
        metrics = env.step(decision.action)
        metrics.update(
            {
                "oracle_action": oracle,
                "oracle_intervention": oracle_intervention,
                "chosen_intervention": chosen_intervention,
                "oracle_rebalance": oracle_rebalance,
                "chosen_rebalance": chosen_rebalance,
                "action_match": 1.0 if decision.action == oracle else 0.0,
                "intervention_match": 1.0 if chosen_intervention == oracle_intervention else 0.0,
                "rebalance_match": 1.0 if chosen_rebalance == oracle_rebalance else 0.0,
                "intervention_score": intervention_score(policy_observation),
                "rebalance_score": rebalance_score(policy_observation),
            }
        )
        reward = env.reward(metrics, mode=reward_mode)
        next_observation = env.observe()
        next_policy_observation = observed_for_variant(variant, next_observation)
        done = env.t >= config.steps
        controller.observe_transition(policy_observation, decision.action, reward, next_policy_observation, done)
        metrics["training_loss"] = getattr(controller, "last_loss", 0.0)
        writer.add_step(
            scenario=config.name,
            variant=variant,
            seed=seed,
            t=env.t,
            action=decision.action,
            reason=decision.reason,
            reward=reward,
            metrics=metrics,
        )
        observation = next_observation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local OAES rebalancing simulator experiments.")
    parser.add_argument(
        "--steps",
        type=int,
        default=3000,
        help="Decision intervals per scenario/variant/seed. Use 3000 for paper local runs; 10000 for heavier stability runs.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help="Number of deterministic seeds to run.",
    )
    args = parser.parse_args()

    output_dir = ROOT / "output"
    writer = MetricsWriter(output_dir)

    variants = [
        "Static",
        "Heuristic",
        "EpsilonGreedy",
        "DQL",
        "DQL-NoMigrationPenalty",
        "DQL-NoBacklogTerm",
        "DQL-NoSubscriptionTerm",
        "DQL-NoRebalancingAction",
        "DQL-NoProbe",
        "DQL-NoTargetNetwork",
        "DQL-NoReplayBuffer",
        "DQL-NoConnectionScaling",
    ]
    seed_bank = [11, 17, 23, 31, 47, 59, 71, 83, 97, 109]
    seeds = seed_bank[: args.seeds]

    for config in scenario_configs(args.steps):
        print(f"Scenario: {config.name}", flush=True)
        for variant in variants:
            print(f"  Variant: {variant}", flush=True)
            for seed in seeds:
                run_one(writer, config, variant, seed)

    writer.write_all()
    print(f"Wrote simulator artifacts to {output_dir}")


if __name__ == "__main__":
    main()
