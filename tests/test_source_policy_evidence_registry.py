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
        self.validator.validate(self.registry)
        self.assertEqual(self.registry["default_status"], "UNASSESSED")
        self.assertEqual(self.registry["sources"], [])

    def test_provider_policy_requires_original_document_hash_and_review(self):
        record = {
            "source_id": "synthetic:test-source",
            "provider_name": "Synthetic provider",
            "assessment_status": "APPROVED",
            "policies": [{
                "policy_id": "synthetic-policy-1",
                "policy_version": "1.0",
                "issuer": "Synthetic issuer",
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

    def test_unverified_policy_cannot_be_marked_as_approved_evidence(self):
        record = {
            "source_id": "synthetic:test-source",
            "provider_name": "Synthetic provider",
            "assessment_status": "APPROVED",
            "policies": [{
                "policy_id": "synthetic-policy-1", "policy_version": "1.0",
                "issuer": "Synthetic issuer", "document_ref": "synthetic-document",
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
