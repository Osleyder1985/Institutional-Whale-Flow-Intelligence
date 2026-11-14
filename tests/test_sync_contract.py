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
        schema = json.loads(SCHEMAS["operations"].read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertFalse(validator.is_valid(record))

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
            self.assertRegex(cursor["issued_at_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

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



class ReferenceSyncProtocolSimulationTests(unittest.TestCase):
    """In-memory protocol model; not a production transport or persistence test."""

    def setUp(self):
        self.server_inbox = {}
        self.server_sequence = 0
        self.server_outbox = []
        self.clients = {
            "desktop": {"pending": {}, "cursor": 0, "snapshots": {}},
            "android": {"pending": {}, "cursor": 0, "snapshots": {}},
            "ios": {"pending": {}, "cursor": 0, "snapshots": {}},
        }

    def submit(self, client, operation_id, fingerprint, dependencies=(), entity=None):
        from iwfi.sync_contract import classify_idempotent_replay
        if operation_id in self.server_inbox:
            prior = self.server_inbox[operation_id]
            outcome = classify_idempotent_replay(prior["fingerprint"], fingerprint)
            if outcome == "DUPLICATE":
                return dict(prior, outcome="DUPLICATE")
            return {"outcome": "REJECTED", "reason_code": "IDEMPOTENCY_KEY_REUSE"}
        if any(dep not in self.server_inbox or self.server_inbox[dep]["outcome"] != "ACCEPTED"
               for dep in dependencies):
            return {"outcome": "DEPENDENCY_PENDING", "cursor": None}
        self.server_sequence += 1
        receipt = {
            "outcome": "ACCEPTED", "fingerprint": fingerprint,
            "server_sequence": self.server_sequence, "cursor": self.server_sequence,
        }
        self.server_inbox[operation_id] = receipt
        self.server_outbox.append((self.server_sequence, client, operation_id, entity))
        return receipt

    def test_three_clients_lost_ack_retry_and_duplicate_delivery(self):
        first = self.submit("desktop", "op-1", "a" * 64)
        self.assertEqual(first["outcome"], "ACCEPTED")
        # Simulate lost acknowledgement: desktop retries the same immutable operation.
        replay = self.submit("desktop", "op-1", "a" * 64)
        self.assertEqual(replay["outcome"], "DUPLICATE")
        self.submit("android", "op-2", "b" * 64, dependencies=("op-1",))
        self.submit("ios", "op-3", "c" * 64, dependencies=("op-1",))
        self.assertEqual(self.server_sequence, 3)
        self.assertEqual(len(self.server_inbox), 3)
        self.assertEqual([row[0] for row in self.server_outbox], [1, 2, 3])

    def test_causal_dependency_pending_does_not_advance_cursor(self):
        receipt = self.submit("android", "child", "d" * 64, dependencies=("parent",))
        self.assertEqual(receipt["outcome"], "DEPENDENCY_PENDING")
        self.assertIsNone(receipt["cursor"])
        self.assertEqual(self.server_sequence, 0)
        self.submit("desktop", "parent", "e" * 64)
        accepted = self.submit("android", "child", "d" * 64, dependencies=("parent",))
        self.assertEqual(accepted["outcome"], "ACCEPTED")
        self.assertEqual(accepted["server_sequence"], 2)

    def test_same_operation_id_with_changed_content_is_rejected(self):
        self.submit("desktop", "reused", "f" * 64)
        rejected = self.submit("ios", "reused", "0" * 64)
        self.assertEqual(rejected["reason_code"], "IDEMPOTENCY_KEY_REUSE")
        self.assertEqual(self.server_inbox["reused"]["fingerprint"], "f" * 64)

    def test_conflicting_claims_are_both_preserved_without_last_write_wins(self):
        self.submit("desktop", "claim-a", "1" * 64, entity={"claim": "EXCHANGE"})
        self.submit("android", "claim-b", "2" * 64, entity={"claim": "CUSTODIAN"})
        claims = [row[3]["claim"] for row in self.server_outbox if row[3]]
        self.assertEqual(claims, ["EXCHANGE", "CUSTODIAN"])

    def test_snapshot_remains_frozen_after_later_evidence_arrives(self):
        frozen_snapshot = {"snapshot_id": "snap-1", "evidence_ids": ["obs-1"], "frozen": True}
        self.clients["desktop"]["snapshots"]["snap-1"] = copy.deepcopy(frozen_snapshot)
        self.submit("android", "new-evidence", "3" * 64, entity={"observation_id": "obs-2"})
        self.assertEqual(self.clients["desktop"]["snapshots"]["snap-1"], frozen_snapshot)
        self.assertEqual(self.clients["desktop"]["snapshots"]["snap-1"]["evidence_ids"], ["obs-1"])

    def test_each_client_advances_only_to_server_confirmed_sequence(self):
        receipt = self.submit("ios", "accepted", "4" * 64)
        self.clients["ios"]["cursor"] = receipt["cursor"]
        pending = self.submit("android", "blocked", "5" * 64, dependencies=("missing",))
        self.assertEqual(self.clients["ios"]["cursor"], 1)
        self.assertEqual(pending["cursor"], None)
        self.assertEqual(self.clients["android"]["cursor"], 0)

    def test_receipt_is_bound_to_originating_device_stream_and_full_operation(self):
        from iwfi.sync_contract import operation_fingerprint, validate_receipt_binding
        operation = copy.deepcopy(FIXTURES["operations"][0])
        receipt = copy.deepcopy(FIXTURES["receipts"][0])
        receipt["operation_fingerprint"] = operation_fingerprint(operation)
        self.assertTrue(validate_receipt_binding(operation, receipt))
        receipt["device_id"] = "different-device"
        with self.assertRaises(ValueError):
            validate_receipt_binding(operation, receipt)

    def test_receipt_cannot_advance_an_unrelated_stream_cursor(self):
        from iwfi.sync_contract import operation_fingerprint, validate_receipt_binding
        operation = copy.deepcopy(FIXTURES["operations"][0])
        receipt = copy.deepcopy(FIXTURES["receipts"][0])
        receipt["operation_fingerprint"] = operation_fingerprint(operation)
        receipt["stream_id"] = "another-stream"
        with self.assertRaises(ValueError):
            validate_receipt_binding(operation, receipt)

    def test_invalid_calendar_date_is_rejected_in_operation_timestamp(self):
        record = copy.deepcopy(FIXTURES["operations"][0])
        record["created_at_device_utc"] = "2026-02-30T10:00:00Z"
        schema = json.loads(SCHEMAS["operations"].read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertFalse(validator.is_valid(record))


if __name__ == "__main__":
    unittest.main()
