#!/usr/bin/env python3
"""Run the 20,000-subscription tiered-backlog stress experiment.

This runner is separate from ``run_experiments.py`` because the workload is much
larger and is intended to support a focused paper subsection. The scenario uses
20,000 subscriptions with four initial backlog tiers:

    25% at 100,000 messages
    25% at  50,000 messages
    25% at   5,000 messages
    25% at       0 messages

The initial assignment is deliberately tier-skewed across four persistent
connections. That creates the operational failure mode the paper studies: a
client can have the right total number of subscriptions but a poor connection
placement that concentrates backlog and subscription pressure.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from oaes_rebalancing_sim.environment import ScenarioConfig  # noqa: E402
from oaes_rebalancing_sim.metrics import MetricsWriter, latex_escape  # noqa: E402
from run_experiments import run_one  # noqa: E402


SCENARIO_NAME = "tiered_20000_backlog"


def tiered_config(steps: int) -> ScenarioConfig:
    """Return the large tiered-backlog workload requested for the paper."""

    return ScenarioConfig(
        name=SCENARIO_NAME,
        steps=steps,
        pod_count=8,
        subscription_count=20_000,
        initial_connections=4,
        max_connections=16,
        theta_n=2_500,
        beta=38_750.0,
        base_arrival_rate=0.0,
        hot_subscription_fraction=0.0,
        hot_multiplier=1.0,
        pod_capacity=100_000.0,
        client_ack_capacity=250_000.0,
        initial_backlog_tiers=((0.25, 100_000.0), (0.25, 50_000.0), (0.25, 5_000.0), (0.25, 0.0)),
        initial_assignment_mode="tier_skewed",
    )


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def write_tiered_setup_table(output_dir: Path, config: ScenarioConfig) -> None:
    path = output_dir / "tables" / "tiered_backlog_setup_table.tex"
    with path.open("w") as handle:
        handle.write("\\begin{table}[!t]\n")
        handle.write("\\centering\n")
        handle.write("\\tiny\n")
        handle.write("\\caption{Experimental configuration for the $20{,}000$-subscription tiered-backlog stress scenario. Pod count is the configured subscriber-service pod count in the simulated cluster.}\n")
        handle.write("\\label{tab:tiered_20000_setup}\n")
        handle.write("\\begin{tabular}{p{0.28\\textwidth}p{0.62\\textwidth}}\n")
        handle.write("\\toprule\n")
        handle.write("Parameter & Value \\\\\n")
        handle.write("\\midrule\n")
        handle.write(f"Subscriber pods & {config.pod_count} \\\\\n")
        handle.write(f"Subscriptions & {config.subscription_count:,} \\\\\n")
        handle.write(f"Initial persistent connections & {config.initial_connections} \\\\\n")
        handle.write(f"Maximum persistent connections & {config.max_connections} \\\\\n")
        handle.write(f"Subscription cap per connection $\\Theta_N$ & {config.theta_n:,} \\\\\n")
        handle.write(f"Pod processing threshold & {config.pod_capacity:,.0f} events/s \\\\\n")
        handle.write(f"Client ACK capacity & {config.client_ack_capacity:,.0f} events/s \\\\\n")
        handle.write("Initial backlog tiers & $25\\%$: $100{,}000$, $25\\%$: $50{,}000$, $25\\%$: $5{,}000$, $25\\%$: $0$ \\\\\n")
        handle.write("Initial placement & Tier-skewed over four initial connections \\\\\n")
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")
        handle.write("\\end{table}\n")


def write_tiered_summary_table(output_dir: Path) -> None:
    rows = read_csv(output_dir / "csv" / "summary.csv")
    rows = sorted(rows, key=lambda row: float(row["avg_total_backlog"]))
    static = next(row for row in rows if row["variant"] == "Static")
    static_backlog = float(static["avg_total_backlog"]) or 1.0

    path = output_dir / "tables" / "tiered_backlog_summary_table.tex"
    with path.open("w") as handle:
        handle.write("\\begin{table*}[!htbp]\n")
        handle.write("\\centering\n")
        handle.write("\\tiny\n")
        handle.write("\\caption{Large-scale tiered-backlog stress results with $20{,}000$ subscriptions. The initial distribution places $25\\%$ of subscriptions at $100{,}000$ queued messages, $25\\%$ at $50{,}000$, $25\\%$ at $5{,}000$, and $25\\%$ at zero backlog. Values are averaged over deterministic seeds and computed over the second half of each run.}\n")
        handle.write("\\label{tab:tiered_20000_summary}\n")
        handle.write("\\begin{tabular}{lrrrrrrr}\n")
        handle.write("\\toprule\n")
        handle.write("Variant & Avg backlog & Reduction & P95 backlog & Imbalance & Pod pressure & Throughput & Churn \\\\\n")
        handle.write("\\midrule\n")
        for row in rows:
            avg_backlog = float(row["avg_total_backlog"])
            reduction = 100.0 * (1.0 - avg_backlog / static_backlog)
            handle.write(
                f"{latex_escape(row['variant'])} & "
                f"{avg_backlog:.1f} & "
                f"{reduction:.1f}\\% & "
                f"{float(row['p95_subscription_backlog']):.1f} & "
                f"{float(row['avg_connection_imbalance']):.3f} & "
                f"{float(row['avg_pod_pressure']):.3f} & "
                f"{float(row['avg_throughput']):.1f} & "
                f"{float(row['connection_churn']):.1f} \\\\\n"
            )
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")
        handle.write("\\end{table*}\n")


def write_tiered_pod_distribution_table(output_dir: Path) -> None:
    rows = read_csv(output_dir / "csv" / "summary.csv")
    selected_variants = {"DQL", "Heuristic", "Static", "DQL-NoRebalancingAction", "DQL-NoConnectionScaling"}
    selected = [row for row in rows if row["variant"] in selected_variants]
    selected = sorted(selected, key=lambda row: float(row["avg_total_backlog"]))

    path = output_dir / "tables" / "tiered_backlog_pod_distribution_table.tex"
    with path.open("w") as handle:
        handle.write("\\begin{table}[!t]\n")
        handle.write("\\centering\n")
        handle.write("\\tiny\n")
        handle.write("\\caption{Tail-window pod distribution behavior in the $20{,}000$-subscription tiered-backlog stress scenario. The table reports offline evaluation metrics over the full simulated cluster; these metrics are not assumed to be visible to the client policy.}\n")
        handle.write("\\label{tab:tiered_20000_pod_distribution}\n")
        handle.write("\\begin{tabular}{lrrrrrrr}\n")
        handle.write("\\toprule\n")
        handle.write("Variant & Pods & Active pods & Max subs/pod & Sub. CV & Max backlog/pod & Backlog CV & Pod pressure \\\\\n")
        handle.write("\\midrule\n")
        for row in selected:
            handle.write(
                f"{latex_escape(row['variant'])} & "
                f"{float(row['configured_pod_count']):.0f} & "
                f"{float(row['avg_active_pod_count']):.1f} & "
                f"{float(row['avg_max_pod_subscriptions']):.1f} & "
                f"{float(row['avg_pod_subscription_cv']):.3f} & "
                f"{float(row['avg_max_pod_backlog']) / 1_000_000.0:.1f}M & "
                f"{float(row['avg_pod_backlog_cv']):.3f} & "
                f"{float(row['avg_pod_pressure']):.3f} \\\\\n"
            )
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")
        handle.write("\\end{table*}\n")


def write_tiered_action_table(output_dir: Path) -> None:
    rows = read_csv(output_dir / "csv" / "action_counts.csv")
    selected_variants = {"DQL", "Heuristic", "DQL-NoRebalancingAction", "DQL-NoConnectionScaling"}
    selected = [row for row in rows if row["variant"] in selected_variants]
    totals: Dict[str, int] = {}
    for row in selected:
        totals[row["variant"]] = totals.get(row["variant"], 0) + int(row["count"])

    path = output_dir / "tables" / "tiered_backlog_action_table.tex"
    with path.open("w") as handle:
        handle.write("\\begin{center}\n")
        handle.write("\\begin{minipage}{\\columnwidth}\n")
        handle.write("\\centering\n")
        handle.write("\\scriptsize\n")
        handle.write("\\captionof{table}{Action mix in the $20{,}000$-subscription tiered-backlog stress scenario. Percentages are computed over all seeds and decision intervals.}\n")
        handle.write("\\label{tab:tiered_20000_action_mix}\n")
        handle.write("\\begin{tabular}{llr}\n")
        handle.write("\\toprule\n")
        handle.write("Variant & Action & Share \\\\\n")
        handle.write("\\midrule\n")
        for row in sorted(selected, key=lambda item: (item["variant"], item["action"])):
            total = max(1, totals[row["variant"]])
            share = 100.0 * int(row["count"]) / total
            handle.write(f"{latex_escape(row['variant'])} & {latex_escape(row['action'])} & {share:.1f}\\% \\\\\n")
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")
        handle.write("\\end{minipage}\n")
        handle.write("\\end{center}\n")


def mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def roc_auc(labels: List[float], scores: List[float]) -> float | None:
    """Compute rank-based ROC-AUC with average ranks for tied scores."""

    positives = sum(1 for label in labels if label >= 0.5)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None

    ranked: List[Tuple[float, float]] = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum_positive = 0.0
    index = 0
    while index < len(ranked):
        next_index = index + 1
        while next_index < len(ranked) and ranked[next_index][0] == ranked[index][0]:
            next_index += 1

        # Ranks are one-based. Tied scores receive the average occupied rank.
        average_rank = 0.5 * ((index + 1) + next_index)
        for _, label in ranked[index:next_index]:
            if label >= 0.5:
                rank_sum_positive += average_rank
        index = next_index

    return (rank_sum_positive - positives * (positives + 1) / 2.0) / (positives * negatives)


def latex_score(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.3f}"


def write_tiered_model_diagnostics_table(output_dir: Path) -> None:
    """Write offline accuracy and ROC-AUC diagnostics for policy decisions."""

    rows = read_csv(output_dir / "csv" / "raw_timeseries.csv")
    by_variant_seed: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for row in rows:
        by_variant_seed.setdefault((row["variant"], row["seed"]), []).append(row)

    tail_rows: List[Dict[str, str]] = []
    for _, grouped_rows in by_variant_seed.items():
        max_t = max(int(row["t"]) for row in grouped_rows)
        tail_rows.extend(row for row in grouped_rows if int(row["t"]) > max_t // 2)

    selected_variants = {
        "DQL",
        "Heuristic",
        "Static",
        "EpsilonGreedy",
        "DQL-NoRebalancingAction",
        "DQL-NoConnectionScaling",
    }
    by_variant: Dict[str, List[Dict[str, str]]] = {}
    for row in tail_rows:
        if row["variant"] in selected_variants:
            by_variant.setdefault(row["variant"], []).append(row)

    diagnostics = []
    for variant, variant_rows in sorted(by_variant.items()):
        action_accuracy = mean([float(row["action_match"]) for row in variant_rows])
        intervention_accuracy = mean([float(row["intervention_match"]) for row in variant_rows])
        rebalance_accuracy = mean([float(row["rebalance_match"]) for row in variant_rows])
        intervention_auc = roc_auc(
            [float(row["oracle_intervention"]) for row in variant_rows],
            [float(row["chosen_intervention"]) for row in variant_rows],
        )
        rebalance_auc = roc_auc(
            [float(row["oracle_rebalance"]) for row in variant_rows],
            [float(row["chosen_rebalance"]) for row in variant_rows],
        )
        oracle_intervention_rate = mean([float(row["oracle_intervention"]) for row in variant_rows])
        policy_intervention_rate = mean([float(row["chosen_intervention"]) for row in variant_rows])
        diagnostics.append(
            {
                "variant": variant,
                "action_accuracy": action_accuracy,
                "intervention_accuracy": intervention_accuracy,
                "rebalance_accuracy": rebalance_accuracy,
                "intervention_auc": intervention_auc,
                "rebalance_auc": rebalance_auc,
                "oracle_intervention_rate": oracle_intervention_rate,
                "policy_intervention_rate": policy_intervention_rate,
            }
        )

    csv_path = output_dir / "csv" / "tiered_model_diagnostics.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant",
                "action_accuracy",
                "intervention_accuracy",
                "rebalance_accuracy",
                "intervention_auc",
                "rebalance_auc",
                "oracle_intervention_rate",
                "policy_intervention_rate",
            ],
        )
        writer.writeheader()
        writer.writerows(diagnostics)

    preferred_order = [
        "DQL",
        "Heuristic",
        "Static",
        "EpsilonGreedy",
        "DQL-NoRebalancingAction",
        "DQL-NoConnectionScaling",
    ]
    ordered = sorted(diagnostics, key=lambda row: preferred_order.index(row["variant"]))

    tex_path = output_dir / "tables" / "tiered_model_diagnostics_table.tex"
    with tex_path.open("w") as handle:
        handle.write("\\begin{center}\n")
        handle.write("\\begin{minipage}{\\columnwidth}\n")
        handle.write("\\centering\n")
        handle.write("\\tiny\n")
        handle.write("\\captionof{table}{Offline model-diagnostic metrics for the $20{,}000$-subscription tiered-backlog stress scenario. The oracle label is computed from client-visible pressure thresholds and is used only for evaluation. Binary accuracy reports agreement with the oracle on intervention and rebalancing families.}\n")
        handle.write("\\label{tab:tiered_model_diagnostics}\n")
        handle.write("\\resizebox{\\columnwidth}{!}{%\n")
        handle.write("\\begin{tabular}{@{}lrrrr@{}}\n")
        handle.write("\\toprule\n")
        handle.write("Variant & Interv. acc. & Rebal. acc. & Oracle interv. & Policy interv. \\\\\n")
        handle.write("\\midrule\n")
        for row in ordered:
            handle.write(
                f"{latex_escape(row['variant'])} & "
                f"{100.0 * row['intervention_accuracy']:.1f}\\% & "
                f"{100.0 * row['rebalance_accuracy']:.1f}\\% & "
                f"{100.0 * row['oracle_intervention_rate']:.1f}\\% & "
                f"{100.0 * row['policy_intervention_rate']:.1f}\\% \\\\\n"
            )
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")
        handle.write("}\n")
        handle.write("\\end{minipage}\n")
        handle.write("\\end{center}\n")


def write_tiered_normalized_scores(output_dir: Path) -> None:
    rows = read_csv(output_dir / "csv" / "summary.csv")
    selected = [row for row in rows if row["variant"] in {"DQL", "Heuristic", "DQL-NoRebalancingAction", "DQL-NoConnectionScaling", "Static"}]
    static = next(row for row in selected if row["variant"] == "Static")
    static_backlog = float(static["avg_total_backlog"]) or 1.0
    static_p95 = float(static["p95_subscription_backlog"]) or 1.0
    max_throughput = max(float(row["avg_throughput"]) for row in selected) or 1.0
    max_churn = max(float(row["connection_churn"]) for row in selected) or 1.0

    path = output_dir / "csv" / "tiered_policy_scores.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant", "backlog_score", "tail_score", "throughput_score", "imbalance_score", "stability_score"],
        )
        writer.writeheader()
        for row in selected:
            writer.writerow(
                {
                    "variant": row["variant"],
                    "backlog_score": max(0.0, min(1.0, 1.0 - float(row["avg_total_backlog"]) / static_backlog)),
                    "tail_score": max(0.0, min(1.0, 1.0 - float(row["p95_subscription_backlog"]) / static_p95)),
                    "throughput_score": max(0.0, min(1.0, float(row["avg_throughput"]) / max_throughput)),
                    "imbalance_score": max(0.0, min(1.0, 1.0 - float(row["avg_connection_imbalance"]))),
                    "stability_score": max(0.0, min(1.0, 1.0 - float(row["connection_churn"]) / max_churn)),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the 20,000-subscription tiered-backlog stress experiment.")
    parser.add_argument("--steps", type=int, default=3000, help="Decision intervals per variant and seed.")
    parser.add_argument("--seeds", type=int, default=3, help="Number of deterministic seeds.")
    args = parser.parse_args()

    config = tiered_config(args.steps)
    output_dir = ROOT / "output" / "tiered_20000"
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

    print(f"Scenario: {config.name}", flush=True)
    for variant in variants:
        print(f"  Variant: {variant}", flush=True)
        for seed in seed_bank[: args.seeds]:
            run_one(writer, config, variant, seed)

    writer.write_all()
    write_tiered_setup_table(output_dir, config)
    write_tiered_summary_table(output_dir)
    write_tiered_pod_distribution_table(output_dir)
    write_tiered_action_table(output_dir)
    write_tiered_model_diagnostics_table(output_dir)
    write_tiered_normalized_scores(output_dir)
    print(f"Wrote tiered-backlog artifacts to {output_dir}")


if __name__ == "__main__":
    main()
