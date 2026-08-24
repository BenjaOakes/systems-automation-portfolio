import unittest

from identity_planner.planner import Policy, normalize_local_part, plan_migration, valid_address


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.policy = Policy.from_dict({"default_brand": "brand-a", "brand_domains": {"brand-a": "brand-a.example", "brand-b": "brand-b.example"}, "department_domains": {"research": "brand-b.example"}})

    def test_normalization_and_validation(self):
        self.assertEqual(normalize_local_part("Ari!", "Example Jr"), "ari.example.jr")
        self.assertTrue(valid_address("ari.example@brand-a.example"))
        self.assertFalse(valid_address("not-an-address"))

    def test_policy_and_alias_preservation(self):
        rows = plan_migration([{"GivenName": "Ari", "Surname": "Example", "Department": "Research", "Brand": "brand-a", "CurrentUPN": "ari@legacy.example", "CurrentPrimaryEmail": "ari@legacy.example", "ExistingAliases": ["smtp:old@legacy.example"]}], self.policy)
        self.assertEqual(rows[0]["ProposedUPN"], "ari.example@brand-b.example")
        self.assertIn("ari@legacy.example", rows[0]["AliasesToPreserve"])
        self.assertEqual(rows[0]["Status"], "Ready")

    def test_alias_string_is_parsed_for_collision_detection(self):
        records = [
            {"GivenName": "Existing", "Surname": "Person", "Brand": "brand-a", "ExistingAliases": "smtp:someone.example@brand-a.example"},
            {"GivenName": "Someone", "Surname": "Example", "Brand": "brand-a"},
        ]
        rows = plan_migration(records, self.policy)
        self.assertEqual(rows[1]["Status"], "Blocked")
        self.assertIn("existing_collision:someone.example@brand-a.example", rows[1]["Reason"])

    def test_unknown_policy_inputs_are_blocked(self):
        rows = plan_migration([{"GivenName": "Ari", "Surname": "Example", "Brand": "unknown-brand"}], self.policy)
        self.assertEqual(rows[0]["Status"], "Blocked")
        self.assertIn("unknown_brand:unknown-brand", rows[0]["Reason"])

        rows = plan_migration([{"GivenName": "Ari", "Surname": "Example", "Brand": "brand-a", "Department": "unknown-department"}], self.policy)
        self.assertEqual(rows[0]["Status"], "Blocked")
        self.assertIn("unknown_department:unknown-department", rows[0]["Reason"])

    def test_policy_domains_are_validated(self):
        with self.assertRaises(ValueError):
            Policy.from_dict({"default_brand": "brand-a", "brand_domains": {"brand-a": "not a domain"}})

    def test_duplicate_proposals_are_blocked(self):
        records = [{"GivenName": "Ari", "Surname": "Example", "Brand": "brand-a"}, {"GivenName": "Ari", "Surname": "Example", "Brand": "brand-a"}]
        rows = plan_migration(records, self.policy)
        self.assertTrue(all(row["Status"] == "Blocked" for row in rows))
        self.assertTrue(all("duplicate_proposal" in row["Reason"] for row in rows))


if __name__ == "__main__":
    unittest.main()
