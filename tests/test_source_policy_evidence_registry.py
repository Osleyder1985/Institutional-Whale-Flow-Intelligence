import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]


class SourcePolicyEvidenceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(
            (ROOT / "schemas" / "source-policy-evidence-registry-v1.0.schema.json").read_text(encoding="utf-8"))
        self.registry = json.loads(
            (ROOT / "data" / "source-policy-evidence-registry-v1.0.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(self.schema)

    def test_empty_registry_is_valid_and_unassessed(self):
        empty_registry = {
            "registry_version": "1.0.0",
            "default_status": "UNASSESSED",
            "sources": []
        }
        self.validator.validate(empty_registry)
        self.assertEqual(empty_registry["default_status"], "UNASSESSED")
        self.assertEqual(empty_registry["sources"], [])

    def test_seeded_source_scopes_remain_pending_without_policy_evidence(self):
        self.validator.validate(self.registry)
        self.assertEqual(self.registry["default_status"], "UNASSESSED")
        self.assertGreater(len(self.registry["sources"]), 0)
        source_ids = [source["source_id"] for source in self.registry["sources"]]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        for source in self.registry["sources"]:
            self.assertEqual(source["assessment_status"], "PENDING_EVIDENCE")
            self.assertEqual(source["policies"], [])

    def test_provider_policy_requires_original_document_hash_and_review(self):
        record = {
            "source_id": "synthetic:test-source",
            "provider_name": "Synthetic provider",
            "assessment_status": "APPROVED",
            "policies": [{
                "policy_id": "synthetic-policy-1",
                "policy_version": "1.0",
                "issuer": "Synthetic issuer",
                "rights_ref": "synthetic-rights-reference",
                "status": "ACTIVE",
                "document_ref": "synthetic-document",
                "document_sha256": "a" * 64,
                "retrieved_at_utc": "2026-11-13T00:00:00Z",
                "reviewed_at_utc": "2026-11-13T12:00:00Z",
                "review_status": "VERIFIED",
                "reviewer_id": "synthetic-reviewer",
                "review_scope": ["RETAIN_LOCAL"],
                "allowed_actions": ["RETAIN_LOCAL"],
                "prohibited_actions": [],
                "valid_from_utc": "2026-01-01T00:00:00Z",
                "expires_at_utc": "2027-01-01T00:00:00Z"
            }]
        }
        self.validator.validate({"registry_version": "1.0.0", "default_status": "UNASSESSED", "sources": [record]})
        del record["policies"][0]["document_sha256"]
        with self.assertRaises(ValidationError):
            self.validator.validate({"registry_version": "1.0.0", "default_status": "UNASSESSED", "sources": [record]})

    def test_approved_provider_without_policy_is_rejected(self):
        record = {
            "source_id": "synthetic:test-source",
            "provider_name": "Synthetic provider",
            "assessment_status": "APPROVED",
            "policies": []
        }
        with self.assertRaises(ValidationError):
            self.validator.validate({"registry_version": "1.0.0", "default_status": "UNASSESSED", "sources": [record]})

    def test_unverified_policy_cannot_be_marked_as_approved_evidence(self):
        record = {
            "source_id": "synthetic:test-source",
            "provider_name": "Synthetic provider",
            "assessment_status": "APPROVED",
            "policies": [{
                "policy_id": "synthetic-policy-1", "policy_version": "1.0",
                "issuer": "Synthetic issuer", "rights_ref": "synthetic-rights-reference", "status": "ACTIVE", "document_ref": "synthetic-document",
                "document_sha256": "a" * 64, "retrieved_at_utc": "2026-11-13T00:00:00Z",
                "reviewed_at_utc": "2026-11-13T12:00:00Z", "review_status": "PENDING",
                "reviewer_id": "synthetic-reviewer", "review_scope": ["RETAIN_LOCAL"],
                "allowed_actions": ["RETAIN_LOCAL"], "prohibited_actions": [],
                "valid_from_utc": "2026-01-01T00:00:00Z", "expires_at_utc": "2027-01-01T00:00:00Z"
            }]
        }
        with self.assertRaises(ValidationError):
            self.validator.validate({"registry_version": "1.0.0", "default_status": "UNASSESSED", "sources": [record]})


if __name__ == "__main__":
    unittest.main()
