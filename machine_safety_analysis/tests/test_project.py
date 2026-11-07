import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import safety_project

class ProjectTests(unittest.TestCase):
    def test_starter_dataset_and_full_validation(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            data, metrics = safety_project.generate(out, "starter", 20261022)
            truth = json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))
            report = safety_project.validate(data, truth)
            db_report = safety_project.validate_database(out / "machine_safety.db")
            self.assertEqual(report["status"], "PASS", report["errors"])
            self.assertEqual(db_report["status"], "PASS", db_report["errors"])
            self.assertEqual(len(data["plant"]), 2)
            self.assertEqual(len(data["machine"]), 12)
            self.assertEqual(len(data["alarm_definition"]), 40)
            self.assertEqual(len(data["alarm_event"]), 2001)
            self.assertEqual(len(truth), 5)
            self.assertEqual(len(report["detected_exceptions"]), 5)
            self.assertGreater(metrics["alarm_flood_event_count"], 0)

    def test_all_negative_scenarios_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            data, _ = safety_project.generate(out, "starter", 20261022)
            truth = json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))
            decisions = {x["decision"] for x in safety_project.validate(data, truth)["detected_exceptions"]}
            self.assertEqual(decisions, {
                "INVALID_ACK_TIMESTAMP_DETECTED", "UNSAFE_STATE_TRANSITION_DETECTED",
                "MISSING_TRIGGER_CONTEXT_DETECTED", "REPLAY_DUPLICATE_DETECTED",
                "UNVERIFIED_CLOSURE_REJECTED",
            })

if __name__ == "__main__":
    unittest.main(verbosity=2)
