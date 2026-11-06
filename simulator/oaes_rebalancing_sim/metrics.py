"""Metrics and artifact writers for the local simulator."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def p95(values: Iterable[float]) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    return values[int(0.95 * (len(values) - 1))]


def roc_auc(labels: Iterable[float], scores: Iterable[float]) -> float | None:
    """Return rank-based ROC-AUC, or None when only one class is present."""

    ranked = sorted(zip(scores, labels), key=lambda item: item[0])
    positives = sum(1 for _, label in ranked if float(label) >= 0.5)
    negatives = len(ranked) - positives
    if positives == 0 or negatives == 0:
        return None

    rank_sum_positive = 0.0
    index = 0
    while index < len(ranked):
        next_index = index + 1
        while next_index < len(ranked) and float(ranked[next_index][0]) == float(ranked[index][0]):
            next_index += 1
        average_rank = 0.5 * ((index + 1) + next_index)
        for _, label in ranked[index:next_index]:
            if float(label) >= 0.5:
                rank_sum_positive += average_rank
        index = next_index

    return (rank_sum_positive - positives * (positives + 1) / 2.0) / (positives * negatives)


def latex_score(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.3f}"


def latex_escape(value: object) -> str:
    """Escape the small set of characters used in generated table labels."""

    return str(value).replace("_", "\\_")


class MetricsWriter:
    """Collect simulation records and write CSV/LaTeX artifacts."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.csv_dir = output_dir / "csv"
        self.table_dir = output_dir / "tables"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.table_dir.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict[str, object]] = []
        self.action_records: List[Dict[str, object]] = []
        self.per_seed_summary: List[Dict[str, object]] = []

    def add_step(
        self,
        scenario: str,
        variant: str,
        seed: int,
        t: int,
        action: str,
        reason: str,
        reward: float,
        metrics: Dict[str, object],
    ) -> None:
        row: Dict[str, object] = {
            "scenario": scenario,
            "variant": variant,
            "seed": seed,
            "t": t,
            "action": action,
            "reason": reason,
            "reward": reward,
        }
        row.update(metrics)
        self.records.append(row)
        self.action_records.append(
            {
                "scenario": scenario,
                "variant": variant,
                "seed": seed,
                "action": action,
            }
        )

    def write_all(self) -> None:
        self._write_raw_timeseries()
        summary = self._write_summary()
        self._write_averaged_timeseries()
        action_counts = self._write_action_counts()
        self._write_boxplot_data()
        self._write_dql_action_heatmap(action_counts)
        self._write_contour_data(summary)
        self._write_radar_data(summary)
        self._write_latex_summary_table(summary)
        self._write_latex_full_summary_table(summary)
        self._write_latex_ablation_table(summary)
        self._write_latex_action_table(action_counts)
        self._write_model_diagnostics_table()
        self._write_learning_curve_artifacts()

    def _write_raw_timeseries(self) -> None:
        if not self.records:
            return
        path = self.csv_dir / "raw_timeseries.csv"
        fieldnames = list(self.records[0].keys())
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.records)

    def _write_summary(self) -> List[Dict[str, object]]:
        grouped: Dict[Tuple[str, str, int], List[Dict[str, object]]] = defaultdict(list)
        for row in self.records:
            grouped[(str(row["scenario"]), str(row["variant"]), int(row["seed"]))].append(row)

        per_seed_summary = []
        for (scenario, variant, seed), rows in grouped.items():
            half = len(rows) // 2
            tail = rows[half:]
            per_seed_summary.append(
                {
                    "scenario": scenario,
                    "variant": variant,
                    "seed": seed,
                    "avg_total_backlog": mean(float(r["total_backlog"]) for r in tail),
                    "p95_subscription_backlog": p95(float(r["p95_subscription_backlog"]) for r in tail),
                    "avg_connection_imbalance": mean(float(r["connection_imbalance"]) for r in tail),
                    "avg_pod_pressure": mean(float(r["pod_pressure"]) for r in tail),
                    "configured_pod_count": mean(float(r.get("configured_pod_count", 0.0)) for r in tail),
                    "avg_active_pod_count": mean(float(r.get("active_pod_count", 0.0)) for r in tail),
                    "avg_max_pod_subscriptions": mean(float(r.get("max_pod_subscriptions", 0.0)) for r in tail),
                    "avg_pod_subscription_cv": mean(float(r.get("pod_subscription_cv", 0.0)) for r in tail),
                    "avg_max_pod_backlog": mean(float(r.get("max_pod_backlog", 0.0)) for r in tail),
                    "avg_pod_backlog_cv": mean(float(r.get("pod_backlog_cv", 0.0)) for r in tail),
                    "avg_throughput": mean(float(r["throughput"]) for r in tail),
                    "migration_count": max(float(r["migration_count"]) for r in rows),
                    "connection_churn": max(float(r["connection_churn"]) for r in rows),
                    "avg_reward": mean(float(r["reward"]) for r in tail),
                }
            )

        self.per_seed_summary = per_seed_summary

        per_seed_path = self.csv_dir / "per_seed_summary.csv"
        with per_seed_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(per_seed_summary[0].keys()))
            writer.writeheader()
            writer.writerows(per_seed_summary)

        final_grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = defaultdict(list)
        for row in per_seed_summary:
            final_grouped[(str(row["scenario"]), str(row["variant"]))].append(row)

        summary: List[Dict[str, object]] = []
        for (scenario, variant), rows in sorted(final_grouped.items()):
            summary.append(
                {
                    "scenario": scenario,
                    "variant": variant,
                    "avg_total_backlog": mean(float(r["avg_total_backlog"]) for r in rows),
                    "p95_subscription_backlog": mean(float(r["p95_subscription_backlog"]) for r in rows),
                    "avg_connection_imbalance": mean(float(r["avg_connection_imbalance"]) for r in rows),
                    "avg_pod_pressure": mean(float(r["avg_pod_pressure"]) for r in rows),
                    "configured_pod_count": mean(float(r["configured_pod_count"]) for r in rows),
                    "avg_active_pod_count": mean(float(r["avg_active_pod_count"]) for r in rows),
                    "avg_max_pod_subscriptions": mean(float(r["avg_max_pod_subscriptions"]) for r in rows),
                    "avg_pod_subscription_cv": mean(float(r["avg_pod_subscription_cv"]) for r in rows),
                    "avg_max_pod_backlog": mean(float(r["avg_max_pod_backlog"]) for r in rows),
                    "avg_pod_backlog_cv": mean(float(r["avg_pod_backlog_cv"]) for r in rows),
                    "avg_throughput": mean(float(r["avg_throughput"]) for r in rows),
                    "migration_count": mean(float(r["migration_count"]) for r in rows),
                    "connection_churn": mean(float(r["connection_churn"]) for r in rows),
                    "avg_reward": mean(float(r["avg_reward"]) for r in rows),
                }
            )

        path = self.csv_dir / "summary.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary[0].keys()))
            writer.writeheader()
            writer.writerows(summary)

        return summary

    def _write_boxplot_data(self) -> None:
        """Write prepared box-plot statistics for tail backlog distributions."""

        grouped: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        for row in self.per_seed_summary:
            grouped[(str(row["scenario"]), str(row["variant"]))].append(float(row["avg_total_backlog"]))

        rows = []
        for (scenario, variant), values in sorted(grouped.items()):
            values = sorted(values)
            rows.append(
                {
                    "scenario": scenario,
                    "variant": variant,
                    "lower_whisker": values[0],
                    "lower_quartile": self._quantile(values, 0.25),
                    "median": self._quantile(values, 0.50),
                    "upper_quartile": self._quantile(values, 0.75),
                    "upper_whisker": values[-1],
                }
            )

        path = self.csv_dir / "boxplot_backlog.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "scenario",
                    "variant",
                    "lower_whisker",
                    "lower_quartile",
                    "median",
                    "upper_quartile",
                    "upper_whisker",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

    def _write_dql_action_heatmap(self, action_counts: List[Dict[str, object]]) -> None:
        """Write DQL action percentages as a rectangular heatmap CSV."""

        scenarios = sorted({str(row["scenario"]) for row in action_counts})
        actions = ["stay", "rebalance_count", "rebalance_backlog", "scale_up", "scale_down", "migrate"]
        counts = defaultdict(int)
        totals = defaultdict(int)
        for row in action_counts:
            if str(row["variant"]) != "DQL":
                continue
            scenario = str(row["scenario"])
            action = str(row["action"])
            count = int(row["count"])
            counts[(scenario, action)] += count
            totals[scenario] += count

        path = self.csv_dir / "dql_action_heatmap.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["scenario", "scenario_idx", "action", "action_idx", "percentage"],
            )
            writer.writeheader()
            for scenario_idx, scenario in enumerate(scenarios):
                for action_idx, action in enumerate(actions):
                    denominator = max(1, totals[scenario])
                    writer.writerow(
                        {
                            "scenario": scenario,
                            "scenario_idx": scenario_idx,
                            "action": action,
                            "action_idx": action_idx,
                            "percentage": 100.0 * counts[(scenario, action)] / denominator,
                        }
                    )

    def _write_contour_data(self, summary: List[Dict[str, object]]) -> None:
        """Write a 2-D performance surface for contour plotting.

        The contour uses DQL-family variants. The x-axis is normalized backlog
        performance, the y-axis is normalized throughput, and the contour value
        is a composite score. This is not used by the online controller; it is
        an offline visualization of the tradeoff surface.
        """

        dql_rows = [row for row in summary if str(row["variant"]).startswith("DQL")]
        max_backlog = max(float(row["avg_total_backlog"]) for row in dql_rows) or 1.0
        max_throughput = max(float(row["avg_throughput"]) for row in dql_rows) or 1.0

        path = self.csv_dir / "contour_performance_surface.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["scenario", "variant", "x_backlog_score", "y_throughput_score", "z_composite"],
            )
            writer.writeheader()
            for row in dql_rows:
                backlog_score = 1.0 - float(row["avg_total_backlog"]) / max_backlog
                throughput_score = float(row["avg_throughput"]) / max_throughput
                imbalance_score = 1.0 - min(1.0, float(row["avg_connection_imbalance"]))
                composite = 0.45 * backlog_score + 0.35 * throughput_score + 0.20 * imbalance_score
                writer.writerow(
                    {
                        "scenario": row["scenario"],
                        "variant": row["variant"],
                        "x_backlog_score": backlog_score,
                        "y_throughput_score": throughput_score,
                        "z_composite": composite,
                    }
                )

    def _write_radar_data(self, summary: List[Dict[str, object]]) -> None:
        """Write normalized metrics for radar-style policy comparison."""

        selected_variants = ["DQL", "Heuristic", "EpsilonGreedy", "Static", "DQL-NoRebalancingAction"]
        grouped = defaultdict(list)
        for row in summary:
            if row["variant"] in selected_variants:
                grouped[str(row["variant"])].append(row)

        static_rows = grouped["Static"]
        static_backlog = mean(float(row["avg_total_backlog"]) for row in static_rows) or 1.0
        static_p95 = mean(float(row["p95_subscription_backlog"]) for row in static_rows) or 1.0
        max_throughput = max(mean(float(row["avg_throughput"]) for row in rows) for rows in grouped.values()) or 1.0
        max_churn = max(mean(float(row["connection_churn"]) for row in rows) for rows in grouped.values()) or 1.0

        rows = []
        for variant in selected_variants:
            values = grouped.get(variant, [])
            if not values:
                continue
            backlog_score = 1.0 - mean(float(row["avg_total_backlog"]) for row in values) / static_backlog
            tail_score = 1.0 - mean(float(row["p95_subscription_backlog"]) for row in values) / static_p95
            throughput_score = mean(float(row["avg_throughput"]) for row in values) / max_throughput
            imbalance_score = 1.0 - min(1.0, mean(float(row["avg_connection_imbalance"]) for row in values))
            stability_score = 1.0 - mean(float(row["connection_churn"]) for row in values) / max_churn
            rows.append(
                {
                    "variant": variant,
                    "backlog": max(0.0, min(1.0, backlog_score)),
                    "tail": max(0.0, min(1.0, tail_score)),
                    "throughput": max(0.0, min(1.0, throughput_score)),
                    "imbalance": max(0.0, min(1.0, imbalance_score)),
                    "stability": max(0.0, min(1.0, stability_score)),
                }
            )

        path = self.csv_dir / "radar_policy_scores.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["variant", "backlog", "tail", "throughput", "imbalance", "stability"],
            )
            writer.writeheader()
            writer.writerows(rows)

    def _write_averaged_timeseries(self) -> None:
        grouped: Dict[Tuple[str, str, int], List[Dict[str, object]]] = defaultdict(list)
        for row in self.records:
            grouped[(str(row["scenario"]), str(row["variant"]), int(row["t"]))].append(row)

        by_scenario: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for (scenario, variant, t), rows in sorted(grouped.items()):
            by_scenario[scenario].append(
                {
                    "scenario": scenario,
                    "variant": variant,
                    "t": t,
                    "total_backlog": mean(float(r["total_backlog"]) for r in rows),
                    "p95_subscription_backlog": mean(float(r["p95_subscription_backlog"]) for r in rows),
                    "throughput": mean(float(r["throughput"]) for r in rows),
                    "connection_imbalance": mean(float(r["connection_imbalance"]) for r in rows),
                    "pod_pressure": mean(float(r["pod_pressure"]) for r in rows),
                }
            )

        for scenario, rows in by_scenario.items():
            path = self.csv_dir / f"timeseries_{scenario}.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            # A wide format is easier for pgfplots line charts.
            self._write_wide_timeseries(scenario, rows, "total_backlog")
            self._write_wide_timeseries(scenario, rows, "throughput")
            self._write_wide_timeseries(scenario, rows, "connection_imbalance")

    def _write_wide_timeseries(self, scenario: str, rows: List[Dict[str, object]], metric: str) -> None:
        variants = sorted({str(row["variant"]) for row in rows})
        times = sorted({int(row["t"]) for row in rows})
        lookup = {(str(row["variant"]), int(row["t"])): float(row[metric]) for row in rows}
        path = self.csv_dir / f"wide_{scenario}_{metric}.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["t"] + variants)
            for t in times:
                writer.writerow([t] + [f"{lookup.get((variant, t), 0.0):.4f}" for variant in variants])

    def _write_action_counts(self) -> List[Dict[str, object]]:
        grouped: Dict[Tuple[str, str, str], int] = defaultdict(int)
        for row in self.action_records:
            grouped[(str(row["scenario"]), str(row["variant"]), str(row["action"]))] += 1

        rows = [
            {"scenario": scenario, "variant": variant, "action": action, "count": count}
            for (scenario, variant, action), count in sorted(grouped.items())
        ]
        path = self.csv_dir / "action_counts.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["scenario", "variant", "action", "count"])
            writer.writeheader()
            writer.writerows(rows)
        return rows

    def _write_latex_summary_table(self, summary: List[Dict[str, object]]) -> None:
        path = self.table_dir / "local_sim_summary_table.tex"
        selected = [row for row in summary if row["scenario"] == "bursty_backlog"]
        selected = sorted(selected, key=lambda row: float(row["avg_total_backlog"]))

        with path.open("w") as handle:
            handle.write("\\begin{table*}[!htbp]\n")
            handle.write("\\centering\n")
            handle.write("\\tiny\n")
            handle.write("\\caption{Simulation results for the bursty-backlog scenario. Values are averaged over deterministic seeds and computed over the second half of each run.}\n")
            handle.write("\\label{tab:local_sim_bursty_summary}\n")
            handle.write("\\begin{tabular}{lrrrrrr}\n")
            handle.write("\\toprule\n")
            handle.write("Variant & Avg backlog & P95 sub. backlog & Imbalance & Pod pressure & Throughput & Migrations \\\\\n")
            handle.write("\\midrule\n")
            for row in selected:
                handle.write(
                    f"{latex_escape(row['variant'])} & "
                    f"{float(row['avg_total_backlog']):.1f} & "
                    f"{float(row['p95_subscription_backlog']):.1f} & "
                    f"{float(row['avg_connection_imbalance']):.3f} & "
                    f"{float(row['avg_pod_pressure']):.3f} & "
                    f"{float(row['avg_throughput']):.1f} & "
                    f"{float(row['migration_count']):.1f} \\\\\n"
                )
            handle.write("\\bottomrule\n")
            handle.write("\\end{tabular}\n")
            handle.write("\\end{table*}\n")

    def _write_latex_full_summary_table(self, summary: List[Dict[str, object]]) -> None:
        path = self.table_dir / "local_sim_full_summary_table.tex"
        selected = sorted(summary, key=lambda row: (str(row["scenario"]), float(row["avg_total_backlog"])))

        with path.open("w") as handle:
            handle.write("\\begin{table*}[!htbp]\n")
            handle.write("\\centering\n")
            handle.write("\\tiny\n")
            handle.write("\\caption{Full simulator summary across scenarios and controller variants. Lower backlog, lower imbalance, higher throughput, and controlled churn indicate better operational behavior.}\n")
            handle.write("\\label{tab:local_sim_full_summary}\n")
            handle.write("\\begin{tabular}{llrrrrrr}\n")
            handle.write("\\toprule\n")
            handle.write("Scenario & Variant & Avg backlog & P95 backlog & Imbalance & Pod pressure & Throughput & Churn \\\\\n")
            handle.write("\\midrule\n")
            for row in selected:
                handle.write(
                    f"{latex_escape(row['scenario'])} & {latex_escape(row['variant'])} & "
                    f"{float(row['avg_total_backlog']):.1f} & "
                    f"{float(row['p95_subscription_backlog']):.1f} & "
                    f"{float(row['avg_connection_imbalance']):.3f} & "
                    f"{float(row['avg_pod_pressure']):.3f} & "
                    f"{float(row['avg_throughput']):.1f} & "
                    f"{float(row['connection_churn']):.1f} \\\\\n"
                )
            handle.write("\\bottomrule\n")
            handle.write("\\end{tabular}\n")
            handle.write("\\end{table*}\n")

    def _write_latex_ablation_table(self, summary: List[Dict[str, object]]) -> None:
        path = self.table_dir / "local_sim_ablation_table.tex"
        variants = {
            "DQL",
            "DQL-NoMigrationPenalty",
            "DQL-NoBacklogTerm",
            "DQL-NoSubscriptionTerm",
            "DQL-NoRebalancingAction",
            "DQL-NoProbe",
            "DQL-NoTargetNetwork",
            "DQL-NoReplayBuffer",
            "DQL-NoConnectionScaling",
        }
        selected = [row for row in summary if row["variant"] in variants]
        selected = sorted(selected, key=lambda row: (str(row["scenario"]), str(row["variant"])))

        with path.open("w") as handle:
            handle.write("\\begin{table*}[!htbp]\n")
            handle.write("\\centering\n")
            handle.write("\\tiny\n")
            handle.write("\\caption{DQL ablation results across scenarios. The ablations remove one modeling component at a time while preserving the same action executor.}\n")
            handle.write("\\label{tab:local_sim_dql_ablations}\n")
            handle.write("\\begin{tabular}{llrrrrr}\n")
            handle.write("\\toprule\n")
            handle.write("Scenario & Variant & Avg backlog & P95 backlog & Imbalance & Throughput & Churn \\\\\n")
            handle.write("\\midrule\n")
            for row in selected:
                handle.write(
                    f"{latex_escape(row['scenario'])} & {latex_escape(row['variant'])} & "
                    f"{float(row['avg_total_backlog']):.1f} & "
                    f"{float(row['p95_subscription_backlog']):.1f} & "
                    f"{float(row['avg_connection_imbalance']):.3f} & "
                    f"{float(row['avg_throughput']):.1f} & "
                    f"{float(row['connection_churn']):.1f} \\\\\n"
                )
            handle.write("\\bottomrule\n")
            handle.write("\\end{tabular}\n")
            handle.write("\\end{table*}\n")

    def _write_latex_action_table(self, action_counts: List[Dict[str, object]]) -> None:
        path = self.table_dir / "local_sim_action_table.tex"
        selected = [
            row
            for row in action_counts
            if row["scenario"] == "bursty_backlog" and row["variant"] in {"Heuristic", "EpsilonGreedy", "DQL"}
        ]

        with path.open("w") as handle:
            handle.write("\\begin{table}[!t]\n")
            handle.write("\\centering\n")
            handle.write("\\scriptsize\n")
            handle.write("\\caption{Action counts in the bursty-backlog simulation.}\n")
            handle.write("\\label{tab:local_sim_action_counts}\n")
            handle.write("\\begin{tabular}{llr}\n")
            handle.write("\\toprule\n")
            handle.write("Variant & Action & Count \\\\\n")
            handle.write("\\midrule\n")
            for row in selected:
                handle.write(f"{latex_escape(row['variant'])} & {latex_escape(row['action'])} & {int(row['count'])} \\\\\n")
            handle.write("\\bottomrule\n")
            handle.write("\\end{tabular}\n")
            handle.write("\\end{table}\n")

    def _write_model_diagnostics_table(self) -> None:
        selected_variants = [
            "DQL",
            "Heuristic",
            "Static",
            "EpsilonGreedy",
            "DQL-NoRebalancingAction",
            "DQL-NoConnectionScaling",
        ]
        grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for row in self.records:
            variant = str(row["variant"])
            if variant in selected_variants and "action_match" in row:
                grouped[variant].append(row)

        diagnostics = []
        for variant in selected_variants:
            rows = grouped.get(variant, [])
            if not rows:
                continue
            diagnostics.append(
                {
                    "variant": variant,
                    "action_accuracy": mean(float(row["action_match"]) for row in rows),
                    "intervention_accuracy": mean(float(row["intervention_match"]) for row in rows),
                    "rebalance_accuracy": mean(float(row["rebalance_match"]) for row in rows),
                    "intervention_auc": roc_auc(
                        [float(row["oracle_intervention"]) for row in rows],
                        [float(row["chosen_intervention"]) for row in rows],
                    ),
                    "rebalance_auc": roc_auc(
                        [float(row["oracle_rebalance"]) for row in rows],
                        [float(row["chosen_rebalance"]) for row in rows],
                    ),
                    "oracle_intervention_rate": mean(float(row["oracle_intervention"]) for row in rows),
                    "policy_intervention_rate": mean(float(row["chosen_intervention"]) for row in rows),
                }
            )

        csv_path = self.csv_dir / "model_diagnostics.csv"
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

        path = self.table_dir / "local_sim_model_diagnostics_table.tex"
        with path.open("w") as handle:
            handle.write("\\begin{table*}[!htbp]\n")
            handle.write("\\centering\n")
            handle.write("\\scriptsize\n")
            handle.write("\\caption{Offline model-diagnostic metrics pooled across the simulator workloads. The oracle labels are computed from client-visible pressure thresholds and are used only for evaluation, not for training.}\n")
            handle.write("\\label{tab:local_sim_model_diagnostics}\n")
            handle.write("\\begin{tabular}{lrrrrrrr}\n")
            handle.write("\\toprule\n")
            handle.write("Variant & Action acc. & Interv. acc. & Rebal. acc. & Interv. AUC & Rebal. AUC & Oracle interv. & Policy interv. \\\\\n")
            handle.write("\\midrule\n")
            for row in diagnostics:
                handle.write(
                    f"{latex_escape(row['variant'])} & "
                    f"{100.0 * float(row['action_accuracy']):.1f}\\% & "
                    f"{100.0 * float(row['intervention_accuracy']):.1f}\\% & "
                    f"{100.0 * float(row['rebalance_accuracy']):.1f}\\% & "
                    f"{latex_score(row['intervention_auc'])} & "
                    f"{latex_score(row['rebalance_auc'])} & "
                    f"{100.0 * float(row['oracle_intervention_rate']):.1f}\\% & "
                    f"{100.0 * float(row['policy_intervention_rate']):.1f}\\% \\\\\n"
                )
            handle.write("\\bottomrule\n")
            handle.write("\\end{tabular}\n")
            handle.write("\\end{table*}\n")

    def _write_learning_curve_artifacts(self) -> None:
        """Write cumulative-reward and Bellman-loss curves for full DQL."""

        dql_rows = [row for row in self.records if str(row["variant"]) == "DQL"]
        if not dql_rows:
            return

        grouped: Dict[Tuple[str, int], List[Dict[str, object]]] = defaultdict(list)
        for row in dql_rows:
            grouped[(str(row["scenario"]), int(row["seed"]))].append(row)

        by_time: Dict[Tuple[str, int], List[Tuple[float, float]]] = defaultdict(list)
        for (scenario, _seed), rows in grouped.items():
            cumulative_reward = 0.0
            for row in sorted(rows, key=lambda item: int(item["t"])):
                cumulative_reward += float(row["reward"])
                by_time[(scenario, int(row["t"]))].append(
                    (cumulative_reward, float(row.get("training_loss", 0.0)))
                )

        curve_rows = []
        for (scenario, t), values in sorted(by_time.items()):
            curve_rows.append(
                {
                    "scenario": scenario,
                    "t": t,
                    "cumulative_reward": mean(value[0] for value in values),
                    "training_loss": mean(value[1] for value in values),
                }
            )

        path = self.csv_dir / "dql_learning_curves.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["scenario", "t", "cumulative_reward", "training_loss"],
            )
            writer.writeheader()
            writer.writerows(curve_rows)

        self._write_wide_learning_curve(curve_rows, "cumulative_reward")
        self._write_wide_learning_curve(curve_rows, "training_loss")
        self._write_learning_diagnostic_curves(curve_rows)

        tex_path = self.table_dir / "local_sim_learning_curve_figure.tex"
        with tex_path.open("w") as handle:
            handle.write("\\begin{figure*}[!htbp]\n")
            handle.write("\\centering\n")
            handle.write("\\begin{subfigure}{0.48\\textwidth}\n")
            handle.write("\\centering\n")
            handle.write("\\begin{tikzpicture}\n")
            handle.write("\\begin{axis}[width=\\linewidth,height=4.75cm,xlabel={Decision interval},ylabel={Norm. accumulated penalty},ymin=0,grid=both,legend columns=3,legend style={font=\\tiny, at={(0.5,1.08)}, anchor=south, draw=black!35, fill=white, fill opacity=0.96, text opacity=1},tick label style={font=\\tiny},label style={font=\\scriptsize}]\n")
            for scenario, color in [
                ("steady_high_subscription", "blue"),
                ("bursty_backlog", "green!55!black"),
                ("client_slowdown", "orange!90!black"),
            ]:
                handle.write(f"\\addplot+[thick,{color},mark=none] table[x=t,y={scenario},col sep=comma]{{experiments/local_simulator/output/csv/wide_dql_accumulated_penalty_norm.csv}};\n")
            handle.write("\\legend{High subscription,Bursty backlog,Client slowdown}\n")
            handle.write("\\end{axis}\n")
            handle.write("\\end{tikzpicture}\n")
            handle.write("\\caption{Normalized accumulated penalty.}\n")
            handle.write("\\end{subfigure}\\hfill\n")
            handle.write("\\begin{subfigure}{0.48\\textwidth}\n")
            handle.write("\\centering\n")
            handle.write("\\begin{tikzpicture}\n")
            handle.write("\\begin{axis}[width=\\linewidth,height=4.75cm,xlabel={Decision interval},ylabel={Smoothed Bellman loss},ymode=log,grid=both,tick label style={font=\\tiny},label style={font=\\scriptsize}]\n")
            for scenario, color in [
                ("steady_high_subscription", "blue"),
                ("bursty_backlog", "green!55!black"),
                ("client_slowdown", "orange!90!black"),
            ]:
                handle.write(f"\\addplot+[thick,{color},mark=none] table[x=t,y={scenario},col sep=comma]{{experiments/local_simulator/output/csv/wide_dql_training_loss_smooth.csv}};\n")
            handle.write("\\end{axis}\n")
            handle.write("\\end{tikzpicture}\n")
            handle.write("\\caption{Smoothed temporal-difference loss.}\n")
            handle.write("\\end{subfigure}\n")
            handle.write("\\caption{Learning diagnostics for the full DQL controller. The left panel reports accumulated penalty normalized by the largest final accumulated penalty across the three workloads; lower growth indicates less cumulative operating cost. The right panel reports a moving-average Bellman loss for the same color-coded workloads, making convergence behavior visible without overlapping legends.}\n")
            handle.write("\\label{fig:local_learning_curves}\n")
            handle.write("\\end{figure*}\n")

    def _write_wide_learning_curve(self, rows: List[Dict[str, object]], metric: str) -> None:
        scenarios = sorted({str(row["scenario"]) for row in rows})
        times = sorted({int(row["t"]) for row in rows})
        lookup = {(str(row["scenario"]), int(row["t"])): float(row[metric]) for row in rows}
        path = self.csv_dir / f"wide_dql_{metric}.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["t"] + scenarios)
            for t in times:
                values = []
                for scenario in scenarios:
                    value = lookup.get((scenario, t), 0.0)
                    if metric == "training_loss":
                        value = max(value, 1.0e-6)
                    values.append(f"{value:.6f}")
                writer.writerow([t] + values)

    def _write_learning_diagnostic_curves(self, rows: List[Dict[str, object]]) -> None:
        scenarios = sorted({str(row["scenario"]) for row in rows})
        times = sorted({int(row["t"]) for row in rows})
        reward_lookup = {
            (str(row["scenario"]), int(row["t"])): float(row["cumulative_reward"])
            for row in rows
        }
        loss_lookup = {
            (str(row["scenario"]), int(row["t"])): max(float(row["training_loss"]), 1.0e-6)
            for row in rows
        }
        final_penalties = [
            max(0.0, -reward_lookup.get((scenario, times[-1]), 0.0))
            for scenario in scenarios
        ]
        penalty_ref = max(final_penalties) if final_penalties else 1.0
        if penalty_ref <= 0:
            penalty_ref = 1.0

        penalty_path = self.csv_dir / "wide_dql_accumulated_penalty_norm.csv"
        with penalty_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["t"] + scenarios)
            for t in times:
                values = []
                for scenario in scenarios:
                    penalty = max(0.0, -reward_lookup.get((scenario, t), 0.0))
                    values.append(f"{penalty / penalty_ref:.6f}")
                writer.writerow([t] + values)

        window = 75
        smooth_path = self.csv_dir / "wide_dql_training_loss_smooth.csv"
        with smooth_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["t"] + scenarios)
            series_by_scenario = {
                scenario: [loss_lookup.get((scenario, t), 1.0e-6) for t in times]
                for scenario in scenarios
            }
            running_sums = {scenario: 0.0 for scenario in scenarios}
            running_values: Dict[str, List[float]] = {scenario: [] for scenario in scenarios}
            for index, t in enumerate(times):
                values = []
                for scenario in scenarios:
                    value = series_by_scenario[scenario][index]
                    running_values[scenario].append(value)
                    running_sums[scenario] += value
                    if len(running_values[scenario]) > window:
                        running_sums[scenario] -= running_values[scenario].pop(0)
                    smooth = running_sums[scenario] / len(running_values[scenario])
                    values.append(f"{max(smooth, 1.0e-6):.6f}")
                writer.writerow([t] + values)


    @staticmethod
    def _quantile(values: List[float], q: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        position = q * (len(values) - 1)
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        fraction = position - lower
        return values[lower] * (1.0 - fraction) + values[upper] * fraction
