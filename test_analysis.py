import unittest, copy
import analysis, evidence


class Checks(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(analysis.generate(50), analysis.generate(50))

    def test_no_duplicate_episodes(self):
        r = analysis.generate()
        self.assertEqual(len(r), len({x["episode_id"] for x in r}))

    def test_no_label_features(self):
        self.assertFalse(
            set(analysis.FEATURES)
            & {"recovered_within_60d", "actual_recovered", "outcome_known_at"}
        )

    def test_maturity(self):
        r = analysis.generate()
        self.assertTrue(all(x["outcome_known_at"] > x["decision_at"] for x in r))

    def test_evidence_contract(self):
        for c in evidence.fixtures():
            with self.subTest(c["name"]):
                self.assertEqual(c["result"]["status"], c["expected"])

    def test_no_cross_payer(self):
        c = copy.deepcopy(evidence.BASE)
        c["payer"] = "B"
        self.assertNotIn("P-A-1", [p["id"] for p in evidence.retrieve(c)])

    def test_policy_availability(self):
        c = copy.deepcopy(evidence.BASE)
        c["decision_at"] = "2024-01-01"
        self.assertEqual(evidence.retrieve(c), [])

    def test_output_schema(self):
        self.assertEqual(evidence.validate(evidence.BASE, {})["status"], "hold")


class ResultChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        from pathlib import Path

        cls.r = json.loads(
            Path(analysis.__file__).with_name("results.json").read_text()
        )

    def test_period_boundaries(self):
        s = self.r["split"]
        self.assertLess(s["train_latest_label"], "2025-11-01")
        self.assertLess(s["calibration_latest_label"], s["test_first_decision"])

    def test_calibration_bin_denominators(self):
        for key in ("raw", "calibrated"):
            self.assertEqual(
                sum(b["n"] for b in self.r[key]["bins"]), self.r["split"]["test"]
            )

    def test_no_duplicate_test_claim(self):
        a = self.r["claims"]
        self.assertEqual(len(a), self.r["split"]["test"])
        self.assertEqual(len(a), len({r["episode_id"] for r in a}))

    def test_queue_reconciles(self):
        for rule, key in [
            ("oldest", lambda r: r["age_days"]),
            ("largest", lambda r: r["allowed_amount"]),
            ("expected_net", lambda r: r["expected_net"]),
        ]:
            a = sorted(self.r["claims"], key=lambda r: (-key(r), r["episode_id"]))[:100]
            self.assertAlmostEqual(
                sum(r["actual_recovered"] - 20 for r in a),
                self.r["queue"][rule]["net"],
                places=2,
            )

    def test_malformed_output(self):
        for x in ([], None, {"action": []}, dict(evidence.GOOD, policy_id=[])):
            self.assertEqual(evidence.validate(evidence.BASE, x)["status"], "hold")


class LedgerChecks(unittest.TestCase):
    def setUp(self):
        import ledger

        self.ledger = ledger
        self.rows = {r["episode_id"]: r for r in ledger.build(*ledger.fixture())}

    def test_snapshot_excludes_future_version(self):
        self.assertEqual(self.rows["E01"]["version_id"], 1)
        self.assertEqual(self.rows["E01"]["allowed_cents"], 10000)

    def test_duplicate_payment_and_reversal(self):
        self.assertEqual(self.rows["E01"]["recovered_cents"], 5000)
        self.assertEqual(self.rows["E02"]["recovered_cents"], 0)
        self.assertEqual(self.rows["E02"]["recovered_60d"], 0)

    def test_maturity_and_window(self):
        self.assertNotIn("E03", self.rows)
        self.assertEqual(self.rows["E04"]["recovered_cents"], 0)
        self.assertEqual(self.rows["E05"]["recovered_cents"], 0)

    def test_conflicting_replay_rejected(self):
        _, _, events = self.ledger.fixture()
        conflict = events[0].copy()
        conflict["net_paid_cents"] = 1
        with self.assertRaises(ValueError):
            self.ledger.deduplicate(events + [conflict])

    def test_ambiguous_episode_allocation_rejected(self):
        episodes, versions, events = self.ledger.fixture()
        with self.assertRaises(ValueError):
            self.ledger.build(
                episodes + [("E06", "C01", "2026-02-01")], versions, events
            )


if __name__ == "__main__":
    unittest.main()
