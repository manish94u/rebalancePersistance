"""Small independent checks for package integrity, pairing, and model inference."""

import copy
import json
import math
import unittest

import reanalyse as analysis


class EvidenceTests(unittest.TestCase):
    def test_manifest(self):
        self.assertGreater(analysis.verify_manifest(analysis.ROOT), 20)

    def test_missing_and_duplicate_pairs_rejected(self):
        rows = [{"policy": "a", "seed": "1"}, {"policy": "b", "seed": "1"}]
        self.assertEqual(len(analysis.paired_rows(rows, "a", "b")), 1)
        with self.assertRaises(ValueError):
            analysis.paired_rows(rows[:1], "a", "b")
        with self.assertRaises(ValueError):
            analysis.paired_rows(rows + rows[:1], "a", "b")

    def test_saved_network(self):
        checkpoint = json.loads((analysis.ROOT / "model/frozen-policy.json").read_text())
        before = copy.deepcopy(checkpoint)
        self.assertEqual(analysis.validate_checkpoint(checkpoint), 902)
        values = analysis.infer(checkpoint, [0.0] * 21)
        self.assertEqual(tuple(values), analysis.ACTIONS)
        self.assertTrue(all(math.isfinite(value) for value in values.values()))
        self.assertEqual(checkpoint, before)
        with self.assertRaises(ValueError):
            analysis.infer(checkpoint, [0.0] * 20)

    def test_measured_effects_and_live_accounting(self):
        result = analysis.analyse()
        scale = result["scaleout_means"]
        self.assertAlmostEqual(scale["FrozenDQL"]["mean_throughput_events_per_second"], 219761.6666666667)
        self.assertAlmostEqual(scale["ScriptedProbeMigration"]["mean_throughput_events_per_second"], 221260.0)
        self.assertAlmostEqual(result["mixed_dql_vs_heuristic"]["reward_difference"], 0.03178930482113085)
        self.assertTrue(result["loaded_live_trial_checks_passed"])


if __name__ == "__main__":
    unittest.main()
