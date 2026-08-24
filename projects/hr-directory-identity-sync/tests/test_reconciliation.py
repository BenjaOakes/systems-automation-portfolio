import json
import unittest
from pathlib import Path

from hr_directory_sync.normalization.normalize import normalize_employee
from hr_directory_sync.policy.rules import Policy, PolicyError
from hr_directory_sync.providers.mock import MockADProvider, MockEntraProvider, MockHRProvider, collect_directory
from hr_directory_sync.reconciliation.engine import apply_plan, build_plan


ROOT = Path(__file__).parents[1]


class HrDirectorySyncTests(unittest.TestCase):
    def setUp(self):
        self.policy = Policy.from_mapping(json.loads((ROOT / "config" / "identity-policy.example.json").read_text()))
        rows = []
        with (ROOT / "examples" / "employees.example.csv").open(newline="", encoding="utf-8") as handle:
            import csv
            rows = list(csv.DictReader(handle))
        directory = json.loads((ROOT / "examples" / "directory.example.json").read_text())
        self.employees = MockHRProvider(rows)
        self.entra = MockEntraProvider(directory["entra"])
        self.ad = MockADProvider(directory["ad"])

    def test_normalization_marks_invalid_input(self):
        employee = normalize_employee({"employee_id": "E1", "given_name": "", "surname": "Example", "work_email": "bad", "department": "engineering", "brand": "northstar"})
        self.assertIn("missing_name", employee.errors)
        self.assertIn("invalid_work_email", employee.errors)

    def test_policy_rejects_unknown_business_values(self):
        employee = normalize_employee({"employee_id": "E1", "given_name": "Ari", "surname": "Example", "work_email": "ari@northstar.example", "department": "unknown", "brand": "northstar"})
        with self.assertRaises(PolicyError):
            self.policy.desired_attributes(employee)

    def test_synthetic_plan_contains_expected_safety_categories(self):
        hr_rows, hr_complete = self.employees.list_employees()
        directory, directory_complete = collect_directory(self.entra, self.ad)
        plan = build_plan(hr_rows, directory, self.policy, source_complete=hr_complete, directory_complete=directory_complete)
        by_id = {item.employee_id: item for item in plan.items}
        self.assertEqual(by_id["E1001"].action, "Create")
        self.assertEqual(by_id["E1002"].status, "NoChange")
        self.assertEqual(by_id["E1005"].action, "Disable")
        self.assertEqual(by_id["E1006"].status, "Blocked")
        self.assertIn("ambiguous_directory_match", by_id["E1007"].reasons)
        self.assertIn("upn_or_mail_collision", by_id["E1008"].reasons)
        self.assertEqual(by_id["E1009"].status, "ReviewRequired")
        self.assertIn("invalid_work_email", by_id["E1010"].reasons)

    def test_incomplete_collection_is_blocked_before_planning(self):
        with self.assertRaisesRegex(ValueError, "collections must be complete"):
            build_plan([], [], self.policy, source_complete=False)

    def test_dry_run_does_not_mutate_and_execute_is_explicit(self):
        hr_rows, _ = self.employees.list_employees()
        directory, _ = collect_directory(self.entra, self.ad)
        plan = build_plan(hr_rows[:2], directory, self.policy)
        before = len(self.entra.records)
        dry = apply_plan(plan, entra_provider=self.entra, ad_provider=self.ad)
        self.assertEqual(len(self.entra.records), before)
        self.assertTrue(all(not item["applied"] for item in dry))

    def test_mock_execution_is_idempotent_after_first_run(self):
        hr_rows, _ = self.employees.list_employees()
        directory, _ = collect_directory(self.entra, self.ad)
        plan = build_plan(hr_rows[:2], directory, self.policy)
        apply_plan(plan, entra_provider=self.entra, ad_provider=self.ad, dry_run=False, execute=True)
        directory_after, _ = collect_directory(self.entra, self.ad)
        second = build_plan(hr_rows[:2], directory_after, self.policy)
        self.assertEqual({item.employee_id: item.status for item in second.items}["E1001"], "NoChange")


if __name__ == "__main__":
    unittest.main()
