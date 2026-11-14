"""Versioned offline synchronization envelope, receipt and cursor contracts."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
FIXTURES = json.loads((ROOT / "fixtures" / "sync-contract-scenarios.json").read_text(encoding="utf-8"))
SCHEMAS = {
    "operations": ROOT.parent / "schemas" / "sync-operation.schema.json",
    "receipts": ROOT.parent / "schemas" / "sync-receipt.schema.json",
    "cursors": ROOT.parent / "schemas" / "sync-cursor.schema.json",
}


class SyncContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validators = {}
        cls.schemas = {}
        for name, path in SCHEMAS.items():
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            cls.schemas[name] = schema
            cls.validators[name] = Draft202012Validator(schema, format_checker=FormatChecker())

    def test_all_synthetic_contract_fixtures_validate(self):
        for name, records in FIXTURES.items():
            for index, record in enumerate(records):
                with self.subTest(contract=name, index=index):
                    self.assertEqual(list(self.validators[name].iter_errors(record)), [])

    def test_contract_schemas_are_versioned_draft_2020_12(self):
        for schema in self.schemas.values():
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["properties"]["contract_version"]["const"], "1.0.0")

    def test_operation_id_must_be_uuid(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        record["operation_id"] = "not-a-uuid"
        self.assertFalse(self.validators["operations"].is_valid(record))

    def test_operation_rejects_non_utc_device_timestamp(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        record["created_at_device_utc"] = "2026-11-14T10:00:00+00:00"
        self.assertFalse(self.validators["operations"].is_valid(record))

    def test_operation_rejects_duplicate_causal_dependencies(self):
        record = copy.deepcopy(FIXTURES["operations"][1])
        record["causal_dependencies"] = [
            "11111111-1111-4111-8111-111111111111",
            "11111111-1111-4111-8111-111111111111",
        ]
        self.assertFalse(self.validators["operations"].is_valid(record))

    def test_operation_cannot_depend_on_itself(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        record["causal_dependencies"] = [record["operation_id"]]
        from iwfi.sync_contract import validate_operation_semantics
        with self.assertRaises(ValueError):
            validate_operation_semantics(record)

    def test_payload_hash_matches_canonical_payload_bytes(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        from iwfi.sync_contract import canonical_payload_hash, validate_operation_semantics
        record["payload_hash"] = canonical_payload_hash(record["payload"])
        self.assertTrue(self.validators["operations"].is_valid(record))
        self.assertTrue(validate_operation_semantics(record))
        record["payload"]["normalized_only"] = False
        self.assertNotEqual(record["payload_hash"], canonical_payload_hash(record["payload"]))
        with self.assertRaises(ValueError):
            validate_operation_semantics(record)

    def test_raw_allowed_retention_requires_terms_record(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        record["retention"] = {"retention_class": "RAW_ALLOWED", "terms_record_id": None}
        self.assertFalse(self.validators["operations"].is_valid(record))
        record["retention"]["terms_record_id"] = "provider-terms-v1"
        self.assertTrue(self.validators["operations"].is_valid(record))

    def test_accepted_receipt_requires_server_sequence_and_cursor(self):
        record = copy.deepcopy(FIXTURES["receipts"][0])
        record["server_sequence"] = None
        self.assertFalse(self.validators["receipts"].is_valid(record))
        record["server_sequence"] = 101
        record["cursor"] = None
        self.assertFalse(self.validators["receipts"].is_valid(record))

    def test_dependency_pending_receipt_cannot_advance_cursor(self):
        record = copy.deepcopy(FIXTURES["receipts"][2])
        record["cursor"] = "cursor-101"
        self.assertFalse(self.validators["receipts"].is_valid(record))

    def test_duplicate_receipt_is_idempotent_replay(self):
        record = copy.deepcopy(FIXTURES["receipts"][1])
        self.assertTrue(self.validators["receipts"].is_valid(record))
        record["idempotent_replay"] = False
        self.assertFalse(self.validators["receipts"].is_valid(record))
        self.assertEqual(record["outcome"], "DUPLICATE")

    def test_terminal_cursor_has_no_next_page(self):
        record = copy.deepcopy(FIXTURES["cursors"][0])
        record["next_cursor"] = "another-page"
        self.assertFalse(self.validators["cursors"].is_valid(record))

    def test_nonterminal_cursor_requires_next_cursor(self):
        record = copy.deepcopy(FIXTURES["cursors"][1])
        record["next_cursor"] = None
        self.assertFalse(self.validators["cursors"].is_valid(record))

    def test_cursor_is_server_sequence_not_device_timestamp(self):
        for cursor in FIXTURES["cursors"]:
            self.assertIsInstance(cursor["server_sequence"], int)
            self.assertGreaterEqual(cursor["server_sequence"], 0)
            self.assertRegex(cursor["issued_at_utc"], r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$")

    def test_operation_ids_are_stable_and_distinct_for_new_operations(self):
        ids = [item["operation_id"] for item in FIXTURES["operations"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(FIXTURES["operations"][1]["causal_dependencies"], [ids[0]])

    def test_unknown_envelope_fields_are_rejected(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        record["server_sequence"] = 99
        self.assertFalse(self.validators["operations"].is_valid(record))


    def test_operation_fingerprint_is_stable_for_object_key_order(self):
        from iwfi.sync_contract import operation_fingerprint
        record = copy.deepcopy(FIXTURES["operations"][0])
        reordered = dict(reversed(list(record.items())))
        self.assertEqual(operation_fingerprint(record), operation_fingerprint(reordered))

    def test_operation_fingerprint_changes_when_payload_changes(self):
        from iwfi.sync_contract import operation_fingerprint
        record = copy.deepcopy(FIXTURES["operations"][0])
        before = operation_fingerprint(record)
        record["payload"]["network_id"] = "eip155:1"
        self.assertNotEqual(before, operation_fingerprint(record))

    def test_idempotency_replay_requires_identical_full_operation_fingerprint(self):
        from iwfi.sync_contract import classify_idempotent_replay
        self.assertEqual(classify_idempotent_replay("a" * 64, "a" * 64), "DUPLICATE")
        self.assertEqual(classify_idempotent_replay("a" * 64, "b" * 64), "IDEMPOTENCY_KEY_REUSE")
        with self.assertRaises(ValueError):
            classify_idempotent_replay("not-a-hash", "b" * 64)

    def test_semantic_validator_rejects_duplicate_dependencies(self):
        from iwfi.sync_contract import validate_operation_semantics, canonical_payload_hash
        record = copy.deepcopy(FIXTURES["operations"][1])
        record["payload_hash"] = canonical_payload_hash(record["payload"])
        record["causal_dependencies"] = [record["operation_id"], record["operation_id"]]
        with self.assertRaises(ValueError):
            validate_operation_semantics(record)


if __name__ == "__main__":
    unittest.main()
