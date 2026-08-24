import unittest

from itsm_sync.core import MockInventoryProvider, MutationJournal, MutationNotAllowed, PartialMutationError, SyncConfig, apply_plan, build_plan, call_with_retry, flatten_pages, normalize_name


class SyncTests(unittest.TestCase):
    def test_normalization_and_pagination(self):
        self.assertEqual(normalize_name("Signal--Board!"), "signal board")
        self.assertEqual(flatten_pages([[{"id": "1"}], [{"id": "2"}]]), [{"id": "1"}, {"id": "2"}])

    def test_plan_is_deterministic_and_detects_create_update(self):
        plan = build_plan(
            [[{"id": "a", "name": "Signal Board", "kind": "application"}, {"id": "b", "name": "New Tool", "kind": "application"}]],
            [[{"id": "cmdb", "name": "signal board", "kind": "service"}]],
            SyncConfig(max_changes=5),
        )
        self.assertEqual([item.action for item in plan], ["create", "update"])
        self.assertEqual(plan[0].source.name, "New Tool")

    def test_threshold_and_mutation_gate(self):
        with self.assertRaises(ValueError):
            build_plan([[{"id": "a", "name": "One"}, {"id": "b", "name": "Two"}]], [[]], SyncConfig(max_changes=1))
        plan = build_plan([[{"id": "a", "name": "One"}]], [[]])
        applied = apply_plan(plan)
        self.assertFalse(applied[0]["applied"])
        with self.assertRaises(MutationNotAllowed):
            apply_plan(plan, dry_run=False, allow_mutations=True)

    def test_duplicate_target_names_are_blocked(self):
        with self.assertRaisesRegex(ValueError, "ambiguous normalized target name"):
            build_plan([[{"id": "a", "name": "Signal Board"}]], [[{"id": "one", "name": "Signal Board"}, {"id": "two", "name": "signal-board"}]])

    def test_retry_does_not_repeat_permanent_errors(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            raise ValueError("validation failed")

        with self.assertRaises(ValueError):
            call_with_retry(operation, attempts=3, base_delay=0)
        self.assertEqual(calls, 1)

    def test_retry_repeats_transient_errors(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise TimeoutError("temporary timeout")
            return "ok"

        self.assertEqual(call_with_retry(operation, attempts=3, base_delay=0), "ok")
        self.assertEqual(calls, 3)

    def test_mutation_boundary_enforces_threshold_and_reports_partial_apply(self):
        plan = build_plan([[{"id": "a", "name": "One"}, {"id": "b", "name": "Two"}]], [[]], SyncConfig(max_changes=5))
        with self.assertRaisesRegex(ValueError, "mutation boundary"):
            apply_plan(plan, max_changes=1)

        applied_keys = []

        def create(payload):
            applied_keys.append(payload["name"])
            if len(applied_keys) == 2:
                raise RuntimeError("adapter failure")

        with self.assertRaises(PartialMutationError) as raised:
            apply_plan(plan, dry_run=False, allow_mutations=True, create=create, update=lambda *_: None, max_changes=5)
        self.assertEqual(raised.exception.applied[0]["key"], "a")
        self.assertEqual(applied_keys, ["One", "Two"])

    def test_incomplete_collection_is_not_plannable(self):
        with self.assertRaisesRegex(ValueError, "collections must be complete"):
            build_plan([[{"id": "a", "name": "One"}]], [[]], source_complete=False)

    def test_mock_provider_and_journal_support_explicit_execute(self):
        plan = build_plan([[{"id": "a", "name": "One"}]], [[]])
        provider = MockInventoryProvider([[]])
        journal = MutationJournal()
        result = apply_plan(plan, dry_run=False, allow_mutations=True, create=provider.create, update=provider.update, journal=journal)
        self.assertTrue(result[0]["applied"])
        self.assertEqual(len(journal.records), 1)
        self.assertEqual(len(provider.records), 1)


if __name__ == "__main__":
    unittest.main()
