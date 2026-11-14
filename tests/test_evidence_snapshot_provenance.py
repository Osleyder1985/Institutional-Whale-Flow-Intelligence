import hashlib
import json
from pathlib import Path
import unittest

import jsonschema

from iwfi.evidence_snapshot_provenance import (
    build_reconstruction_manifest,
    build_snapshot_descriptor,
    build_snapshot_relation,
    verify_manifest_dependencies,
    verify_snapshot_payload,
)


RETRIEVED = "2026-11-12T10:00:00Z"
CUTOFF = "2026-11-12T11:00:00Z"


def descriptor(payload=b'{"asset":"BTC"}', snapshot_id="snap-btc-001",
               source_id="synthetic-btc", storage_ref="fixture://btc/001"):
    return build_snapshot_descriptor(
        source_id=source_id,
        source_snapshot_id=snapshot_id,
        retrieved_at_utc=RETRIEVED,
        published_at_utc=None,
        media_type="application/json",
        rights_policy_ref="policy:synthetic-fixture",
        retention_decision="RETAINED",
        payload=payload,
        hash_permitted=True,
        storage_ref=storage_ref,
    )


class EvidenceSnapshotProvenanceTests(unittest.TestCase):
    def test_raw_payload_hash_is_sha256_and_verifies(self):
        payload = b'{"asset":"BTC"}'
        snapshot = descriptor(payload=payload)
        result = verify_snapshot_payload(snapshot, payload)
        self.assertEqual(result["status"], "HASH_VERIFIED")
        self.assertEqual(snapshot["payload_hash"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(snapshot["payload_size_bytes"], len(payload))

    def test_modified_payload_fails_hash_verification(self):
        snapshot = descriptor()
        self.assertEqual(verify_snapshot_payload(snapshot, b'{"asset":"ETH"}')["status"], "HASH_MISMATCH")

    def test_truncated_payload_fails_size_verification(self):
        snapshot = descriptor()
        self.assertEqual(verify_snapshot_payload(snapshot, b'{"asset":')["status"], "SIZE_MISMATCH")

    def test_retention_without_authorized_hash_fails_closed(self):
        with self.assertRaises(ValueError):
            build_snapshot_descriptor(
                source_id="synthetic", source_snapshot_id="snap-1",
                retrieved_at_utc=RETRIEVED, media_type="application/json",
                rights_policy_ref="policy:restricted", retention_decision="RETAINED",
                payload=b"private", hash_permitted=False, storage_ref="fixture://private",
            )

    def test_metadata_only_can_record_hash_when_policy_allows(self):
        snapshot = build_snapshot_descriptor(
            source_id="synthetic", source_snapshot_id="snap-meta",
            retrieved_at_utc=RETRIEVED, media_type="application/json",
            rights_policy_ref="policy:hash-only", retention_decision="NOT_RETAINED_POLICY",
            payload=b"permitted-hash-only", hash_permitted=True,
        )
        self.assertEqual(snapshot["payload_retention"], "NOT_RETAINED_POLICY")
        self.assertEqual(snapshot["hash_status"], "AVAILABLE")
        self.assertIsNone(snapshot["storage_ref"])

    def test_prohibited_hash_is_not_fabricated(self):
        snapshot = build_snapshot_descriptor(
            source_id="synthetic", source_snapshot_id="snap-no-hash",
            retrieved_at_utc=RETRIEVED, media_type="application/octet-stream",
            rights_policy_ref="policy:no-hash", retention_decision="NOT_RETAINED_POLICY",
            payload=b"restricted", hash_permitted=False,
        )
        self.assertEqual(snapshot["hash_status"], "NOT_PERMITTED")
        self.assertIsNone(snapshot["payload_hash"])

    def test_canonical_json_requires_explicit_version(self):
        with self.assertRaises(ValueError):
            build_snapshot_descriptor(
                source_id="synthetic", source_snapshot_id="snap-canonical",
                retrieved_at_utc=RETRIEVED, media_type="application/json",
                rights_policy_ref="policy:synthetic", retention_decision="NOT_RETAINED_POLICY",
                payload=b"{}", hash_permitted=True, hash_scope="CANONICAL_JSON",
            )

    def test_raw_bytes_cannot_claim_canonicalization_version(self):
        with self.assertRaises(ValueError):
            build_snapshot_descriptor(
                source_id="synthetic", source_snapshot_id="snap-raw",
                retrieved_at_utc=RETRIEVED, media_type="application/json",
                rights_policy_ref="policy:synthetic", retention_decision="NOT_RETAINED_POLICY",
                payload=b"{}", hash_permitted=True, canonicalization_version="v1",
            )

    def test_snapshot_relation_preserves_correction_as_new_record(self):
        relation = build_snapshot_relation(
            relation_id="rel-001", from_snapshot_id="snap-old",
            to_snapshot_id="snap-new", relation_type="CORRECTS",
            recorded_at_utc=CUTOFF, rights_policy_ref="policy:synthetic",
        )
        self.assertEqual(relation["relation_type"], "CORRECTS")
        self.assertEqual(relation["from_snapshot_id"], "snap-old")
        self.assertEqual(relation["to_snapshot_id"], "snap-new")

    def test_relation_rejects_self_reference(self):
        with self.assertRaises(ValueError):
            build_snapshot_relation(
                relation_id="rel-self", from_snapshot_id="same", to_snapshot_id="same",
                relation_type="SUPERSEDES", recorded_at_utc=CUTOFF,
                rights_policy_ref="policy:synthetic",
            )

    def test_manifest_is_deterministic_for_dependency_order(self):
        first, second = descriptor(snapshot_id="snap-b"), descriptor(
            payload=b'{"asset":"ETH"}', snapshot_id="snap-e", source_id="synthetic-eth")
        args = dict(claim_id="claim-001", contract_versions={"actor_registry": "1.2.0"},
                    algorithm_id="iwfi-reconstruction", algorithm_version="1.0.0",
                    parameters={"strict": True}, knowledge_cutoff_utc=CUTOFF,
                    valid_time_utc=RETRIEVED)
        one = build_reconstruction_manifest(snapshot_descriptors=[first, second], **args)
        two = build_reconstruction_manifest(snapshot_descriptors=[second, first], **args)
        self.assertEqual(one, two)

    def test_manifest_verifies_exact_dependencies_offline(self):
        snapshot = descriptor()
        manifest = build_reconstruction_manifest(
            claim_id="claim-001", snapshot_descriptors=[snapshot],
            contract_versions={"actor_registry": "1.2.0"},
            algorithm_id="iwfi-reconstruction", algorithm_version="1.0.0",
            parameters={"strict": True}, knowledge_cutoff_utc=CUTOFF,
            valid_time_utc=RETRIEVED,
        )
        result = verify_manifest_dependencies(
            manifest, {snapshot["source_snapshot_id"]: snapshot},
            {snapshot["source_snapshot_id"]: b'{"asset":"BTC"}'},
        )
        self.assertEqual(result["status"], "RECONSTRUCTION_INPUTS_VERIFIED")

    def test_manifest_detects_payload_tampering(self):
        snapshot = descriptor()
        manifest = build_reconstruction_manifest(
            claim_id="claim-002", snapshot_descriptors=[snapshot],
            contract_versions={"actor_registry": "1.2.0"},
            algorithm_id="iwfi-reconstruction", algorithm_version="1.0.0",
            parameters={}, knowledge_cutoff_utc=CUTOFF, valid_time_utc=RETRIEVED,
        )
        result = verify_manifest_dependencies(
            manifest, {snapshot["source_snapshot_id"]: snapshot},
            {snapshot["source_snapshot_id"]: b"tampered"},
        )
        self.assertEqual(result["status"], "INTEGRITY_FAILED")

    def test_manifest_detects_correct_hash_attached_to_wrong_snapshot_reference(self):
        original = descriptor()
        manifest = build_reconstruction_manifest(
            claim_id="claim-003", snapshot_descriptors=[original],
            contract_versions={"actor_registry": "1.2.0"},
            algorithm_id="iwfi-reconstruction", algorithm_version="1.0.0",
            parameters={}, knowledge_cutoff_utc=CUTOFF, valid_time_utc=RETRIEVED,
        )
        substituted = descriptor(
            payload=b'{"asset":"ETH"}', snapshot_id="snap-btc-001",
            source_id="different-source", storage_ref="fixture://substituted")
        result = verify_manifest_dependencies(
            manifest, {original["source_snapshot_id"]: substituted},
            {original["source_snapshot_id"]: b'{"asset":"ETH"}'},
        )
        self.assertEqual(result["dependencies"][0]["status"], "SNAPSHOT_REFERENCE_MISMATCH")
        self.assertEqual(result["status"], "INTEGRITY_FAILED")

    def test_manifest_hash_detects_dependency_manifest_mutation(self):
        snapshot = descriptor()
        manifest = build_reconstruction_manifest(
            claim_id="claim-004", snapshot_descriptors=[snapshot],
            contract_versions={"actor_registry": "1.2.0"},
            algorithm_id="iwfi-reconstruction", algorithm_version="1.0.0",
            parameters={"threshold": 1}, knowledge_cutoff_utc=CUTOFF,
            valid_time_utc=RETRIEVED,
        )
        manifest["parameters"]["threshold"] = 2
        result = verify_manifest_dependencies(
            manifest, {snapshot["source_snapshot_id"]: snapshot},
            {snapshot["source_snapshot_id"]: b'{"asset":"BTC"}'},
        )
        self.assertEqual(result["manifest_status"], "MANIFEST_HASH_MISMATCH")


    def test_btc_eth_snapshot_fixtures_validate_schema_and_hash(self):
        root = Path(__file__).parent
        schema = json.loads((root.parent / "schemas" / "evidence-snapshot-v1.0.schema.json").read_text(encoding="utf-8"))
        fixture = json.loads((root / "fixtures" / "evidence-snapshots-v1.0.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["fixture_version"], "1.0.0")
        self.assertEqual(len(fixture["snapshots"]), 2)
        for item in fixture["snapshots"]:
            descriptor_data = item["descriptor"]
            jsonschema.validate(descriptor_data, schema)
            payload = item["payload_utf8"].encode("utf-8")
            self.assertEqual(verify_snapshot_payload(descriptor_data, payload)["status"], "HASH_VERIFIED")

    def test_snapshot_schema_rejects_missing_recorded_timestamp(self):
        root = Path(__file__).parent
        schema = json.loads((root.parent / "schemas" / "evidence-snapshot-v1.0.schema.json").read_text(encoding="utf-8"))
        snapshot = descriptor()
        snapshot.pop("recorded_at_utc")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(snapshot, schema)

    def test_missing_snapshot_fails_closed(self):
        snapshot = descriptor()
        manifest = build_reconstruction_manifest(
            claim_id="claim-005", snapshot_descriptors=[snapshot],
            contract_versions={"actor_registry": "1.2.0"},
            algorithm_id="iwfi-reconstruction", algorithm_version="1.0.0",
            parameters={}, knowledge_cutoff_utc=CUTOFF, valid_time_utc=RETRIEVED,
        )
        result = verify_manifest_dependencies(manifest, {}, {})
        self.assertEqual(result["dependencies"][0]["status"], "SNAPSHOT_MISSING")
        self.assertEqual(result["status"], "INTEGRITY_FAILED")


if __name__ == "__main__":
    unittest.main()
