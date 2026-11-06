"""Reanalyse packaged measurements without changing them or contacting a service.

Every comparison uses complete episode pairs. Policy labels remain those in the
original records: ScriptedProbeMigration is the pressure-aware greedy policy,
not one of the random ad-hoc timing controls. The bootstrap below is a new,
explicitly identified reanalysis; original registered inference is also shipped.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics


ROOT = Path(__file__).resolve().parent
ACTIONS = ("stay", "rebN", "rebG", "scale+", "scale-", "migrate")


def verify_manifest(root):
    """Check the exact file set and bytes, ignoring interpreter cache files."""
    manifest = json.loads((root / "MANIFEST.json").read_text())
    expected = set(manifest["files"])
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
        and p.name not in ("MANIFEST.json", ".DS_Store")
    }
    if actual != expected:
        raise ValueError("Package file set differs from its manifest")
    for relative, digest in manifest["files"].items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            raise ValueError("Checksum mismatch: " + relative)
    return len(expected)


def read_rows(relative, root=ROOT):
    with (root / "data" / relative).open(newline="") as stream:
        return list(csv.DictReader(stream))


def paired_rows(rows, policy, baseline, keys=("seed",)):
    """Reject missing or duplicate pairs instead of silently intersecting arms."""
    indexed = []
    for name in (policy, baseline):
        arm = {}
        for row in rows:
            if row["policy"] != name:
                continue
            key = tuple(row[k] for k in keys)
            if key in arm:
                raise ValueError("Duplicate paired episode: " + str(key))
            arm[key] = row
        indexed.append(arm)
    if not indexed[0] or indexed[0].keys() != indexed[1].keys():
        raise ValueError("Unequal paired episode coverage")
    return [(indexed[0][key], indexed[1][key]) for key in sorted(indexed[0])]


def mean_by_policy(rows, metrics):
    return {
        policy: {
            metric: statistics.mean(float(r[metric]) for r in rows if r["policy"] == policy)
            for metric in metrics
        }
        for policy in sorted({r["policy"] for r in rows})
    }


def percentile(values, q):
    """Linear-interpolation percentile for the recorded bootstrap distribution."""
    values = sorted(values)
    location = (len(values) - 1) * q
    lo = int(location)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (location - lo) * (values[hi] - values[lo])


def paired_bootstrap(differences, resamples=10000, seed=20261027):
    rng = random.Random(seed)
    samples = [
        statistics.mean(rng.choices(differences, k=len(differences)))
        for _ in range(resamples)
    ]
    return [percentile(samples, 0.025), percentile(samples, 0.975)]


def infer(checkpoint, features):
    """Evaluate the saved dense network only; do not apply an execution policy."""
    if len(features) != 21 or not all(math.isfinite(x) for x in features):
        raise ValueError("Expected 21 finite input features")
    network = checkpoint["online_network"]
    hidden = [
        max(0.0, sum(w * x for w, x in zip(row, features)) + bias)
        for row, bias in zip(network["w1"], network["b1"])
    ]
    outputs = [
        sum(w * x for w, x in zip(row, hidden)) + bias
        for row, bias in zip(network["w2"], network["b2"])
    ]
    return dict(zip(ACTIONS, outputs))


def validate_checkpoint(checkpoint):
    """Check both copies of the implemented architecture and the frozen state."""
    for name in ("online_network", "target_network"):
        network = checkpoint[name]
        assert len(network["w1"]) == len(network["b1"]) == 32
        assert all(len(row) == 21 for row in network["w1"])
        assert len(network["w2"]) == len(network["b2"]) == 6
        assert all(len(row) == 32 for row in network["w2"])
    assert checkpoint["epsilon"] == 0
    assert not checkpoint["training_enabled"]
    assert checkpoint["training_steps"] == 9985
    return 902


def analyse(root=ROOT):
    scale = read_rows("persistent-scaleout-recovery-complete/episode-metrics.csv", root)
    mixed = read_rows("v3/holdout-episodes.csv", root)
    assert len(scale) == 60 and len(mixed) == 120
    control_pairs = paired_rows(scale, "FrozenDQL", "KubernetesScaleOutOnly")
    greedy_pairs = paired_rows(scale, "FrozenDQL", "ScriptedProbeMigration")
    holdout_pairs = paired_rows(mixed, "FrozenDQL", "Heuristic", ("scenario", "seed"))
    assert len(control_pairs) == len(greedy_pairs) == 20 and len(holdout_pairs) == 40
    scale_means = mean_by_policy(scale, (
        "mean_throughput_events_per_second", "normalized_backlog_auc", "final_backlog_ratio"
    ))
    mixed_means = mean_by_policy(mixed, (
        "mean_reward", "mean_connection_subscription_variance",
        "mean_connection_backlog_variance", "mean_throughput_ratio"
    ))
    dql, base = scale_means["FrozenDQL"], scale_means["KubernetesScaleOutOnly"]
    dql_m, heuristic = mixed_means["FrozenDQL"], mixed_means["Heuristic"]
    differences = [
        float(a["mean_throughput_events_per_second"]) - float(b["mean_throughput_events_per_second"])
        for a, b in greedy_pairs
    ]
    live = json.loads((root / "data/live-dql-20261026/manuscript-summary.json").read_text())
    assert len(live["actions"]) == 3
    assert all(sum(stage) == 1000 for stage in live["stage_bindings"])
    assert sum(a["subscriptions"] for a in live["actions"]) == 750
    assert live["distinct_subscriptions_moved"] == 500
    assert all(a["retained_other_sessions"] == 3 for a in live["actions"])
    assert live["deliveries"] == live["ack_receipts"] == 8000
    assert live["unresolved_deliveries"] == 0
    checkpoint = json.loads((root / "model/frozen-policy.json").read_text())
    return {
        "network_parameters_per_copy": validate_checkpoint(checkpoint),
        "scaleout_means": scale_means,
        "scaleout_dql_vs_unchanged": {
            "throughput_ratio": dql["mean_throughput_events_per_second"] / base["mean_throughput_events_per_second"],
            "backlog_auc_reduction_percent": 100 * (1 - dql["normalized_backlog_auc"] / base["normalized_backlog_auc"]),
        },
        "mixed_workload_means": mixed_means,
        "mixed_dql_vs_heuristic": {
            "reward_difference": dql_m["mean_reward"] - heuristic["mean_reward"],
            "subscription_variance_reduction_percent": 100 * (1 - dql_m["mean_connection_subscription_variance"] / heuristic["mean_connection_subscription_variance"]),
            "throughput_change_percent": 100 * (dql_m["mean_throughput_ratio"] / heuristic["mean_throughput_ratio"] - 1),
        },
        "descriptive_reanalysis_dql_minus_greedy_events_per_second": {
            "paired_episodes": 20, "mean": statistics.mean(differences),
            "bootstrap_percentile_ci95": paired_bootstrap(differences),
            "bootstrap_seed": 20261027, "resamples": 10000,
            "is_original_registered_primary_test": False,
        },
        "loaded_live_trial_checks_passed": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", help="JSON array of 21 normalized values for offline inference")
    args = parser.parse_args()
    result = {"verified_files": verify_manifest(ROOT), "analysis": analyse()}
    if args.features:
        checkpoint = json.loads((ROOT / "model/frozen-policy.json").read_text())
        result["q_values_not_execution_permissions"] = infer(checkpoint, json.loads(args.features))
    print(json.dumps(result, indent=2, allow_nan=False))
