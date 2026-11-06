"""Fast physical/accounting invariants, independent of a desired policy ranking.

No test asserts that DQL must beat another policy. The tests ensure a run does
not gain throughput by losing queues, duplicating subscription ownership, or
confusing an interval event count with a per-second rate.
"""

from dataclasses import replace
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulator"))
from oaes_rebalancing_sim.controllers import Action
from oaes_rebalancing_sim.environment import SimulationEnvironment
from run_experiments import scenario_configs
from run_tiered_backlog_experiment import tiered_config, write_tiered_setup_table


class SimulatorContractTests(unittest.TestCase):
    def config(self):
        return replace(scenario_configs(20)[0],
                       initial_backlog_tiers=((1.0, 1000.0),))

    def assert_assignments(self, env):
        """Every subscription has exactly one matching connection owner."""
        assigned = [sid for connection in env.connections for sid in connection.subscriptions]
        self.assertEqual(sorted(assigned), list(range(env.config.subscription_count)))
        self.assertEqual(len(set(assigned)), env.config.subscription_count)
        for connection in env.connections:
            for sid in connection.subscriptions:
                self.assertEqual(env.subscriptions[sid].connection_id, connection.connection_id)

    def test_seeded_replay_is_deterministic(self):
        left = SimulationEnvironment(self.config(), 11)
        right = SimulationEnvironment(self.config(), 11)
        for _ in range(12):
            self.assertEqual(left.observe(), right.observe())
            self.assertEqual(left.step(Action.STAY), right.step(Action.STAY))

    def test_actions_preserve_backlog_accounting_and_ownership(self):
        env = SimulationEnvironment(self.config(), 17)
        for requested in Action.ALL * 3:
            action = requested if requested in env.allowed_actions() else Action.STAY
            before = env.total_backlog()
            metrics = env.step(action)
            self.assertAlmostEqual(before + metrics["generated"] - metrics["throughput"],
                                   env.total_backlog(), places=6)
            self.assertTrue(all(s.backlog >= 0 and math.isfinite(s.backlog)
                                for s in env.subscriptions))
            self.assert_assignments(env)
            self.assertEqual(sum(p.subscription_count for p in env.pods), env.config.subscription_count)
            self.assertAlmostEqual(sum(p.cumulative_backlog for p in env.pods),
                                   env.total_backlog(), places=6)

    def test_interval_counts_and_rates_are_not_confused(self):
        env = SimulationEnvironment(replace(self.config(), decision_interval_seconds=10.0), 23)
        metrics = env.step(Action.STAY)
        self.assertAlmostEqual(metrics["throughput"] / 10.0,
                               metrics["throughput_events_per_second"])

    def test_initial_20000_subscription_tiers(self):
        env = SimulationEnvironment(tiered_config(1), 11)
        self.assertEqual(len(env.subscriptions), 20000)
        self.assertEqual(env.total_backlog(), 775000000)
        for backlog in (100000, 50000, 5000, 0):
            self.assertEqual(sum(s.backlog == backlog for s in env.subscriptions), 5000)
        self.assert_assignments(env)

    def test_invalid_decision_cadence_is_rejected(self):
        for cadence in (0, -1, float("nan"), float("inf")):
            with self.subTest(cadence=cadence), self.assertRaises(ValueError):
                SimulationEnvironment(replace(self.config(), decision_interval_seconds=cadence), 11)

    def test_setup_table_has_matching_latex_environment(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "tables").mkdir()
            write_tiered_setup_table(root, tiered_config(1))
            text = (root / "tables/tiered_backlog_setup_table.tex").read_text()
            self.assertIn("\\begin{table}", text)
            self.assertIn("\\end{table}", text)
            self.assertNotIn("\\end{table*}", text)


if __name__ == "__main__":
    unittest.main()
