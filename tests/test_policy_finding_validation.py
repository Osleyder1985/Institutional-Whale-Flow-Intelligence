import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_policy_evidence import MANIFEST_NAME, build_extraction_bundle
from scripts.validate_policy_findings import (
    FindingValidationError, ROOT, validate_policy_findings, write_validation_report,
)


class PolicyFindingValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.evidence_dir = self.directory / "original-evidence"
        self.evidence_dir.mkdir()
        self.bundle_path = self.directory / "bundle.json"
        self.review_path = self.directory / "review.json"
        self.output_path = self.directory / "report.json"
        source_bytes = b"Section 4.1 permits personal research.\\nNo commercial use."
        self.snapshot_hash = hashlib.sha256(source_bytes).hexdigest()
        (self.evidence_dir / "policy_a.md").write_bytes(source_bytes)
        manifest = {
            "manifest_version": "1.0.0",
            "storage_scope": "LOCAL_ONLY",
            "external_upload_performed": False,
            "external_sync_performed": False,
            "authorization_status": "NOT_GRANTED",
            "legal_review_status": "NOT_PERFORMED",
            "documents": [{
                "document_id": "policy_a",
                "provider": "Fixture",
                "requested_url": "https://example.invalid/policy",
                "final_url": "https://example.invalid/policy",
                "retrieved_at_utc": "2026-11-14T00:00:00Z",
                "sha256": self.snapshot_hash,
                "bytes_written": len(source_bytes),
                "local_filename": "policy_a.md",
                "evidence_status": "CAPTURED_UNREVIEWED",
                "authorization_status": "NOT_GRANTED",
            }],
        }
        (self.evidence_dir / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        self.bundle = build_extraction_bundle(self.evidence_dir)
        self.review = {
            "review_register_version": "1.0.0",
            "register_scope": "METADATA_AND_REFERENCES_ONLY",
            "reviewer": "reviewer-id",
            "reviewed_at_utc": "2026-11-14T12:00:00Z",
            "findings": [{
                "finding_id": "POL-001",
                "proposition": "The source states that the activity is permitted for personal research.",
                "conclusion_type": "OBSERVED_TEXT",
                "applicability_status": "NOT_ASSESSED",
                "review_state": "DRAFT",
                "source": {
                    "document_id": "policy_a",
                    "snapshot_sha256": self.snapshot_hash,
                    "declared_version": "v1",
                },
                "locator": {
                    "kind": "document_text",
                    "exact_text": "Section 4.1 permits personal research.",
                },
            }],
        }
        self.write_inputs()

    def tearDown(self):
        self.temp.cleanup()

    def write_inputs(self):
        self.bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8")
        self.review_path.write_text(json.dumps(self.review), encoding="utf-8")

    def validate(self):
        return validate_policy_findings(self.bundle_path, self.review_path, self.evidence_dir)

    def test_exact_snapshot_and_text_locator_are_verified(self):
        report = self.validate()
        self.assertEqual(report["validation_status"], "ALL_REFERENCES_VERIFIED")
        self.assertEqual(report["findings"][0]["reference_status"], "REFERENCE_VERIFIED")
        self.assertTrue(report["reference_verification_only"])

    def test_tampered_bundle_text_is_rejected_against_original_snapshot(self):
        self.bundle["documents"][0]["text"] = "Forged source text."
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "EXTRACTION_BUNDLE_DOES_NOT_MATCH_ORIGINAL_SNAPSHOTS"):
            self.validate()

    def test_original_snapshot_change_is_rejected_by_capture_manifest(self):
        (self.evidence_dir / "policy_a.md").write_text("Changed original.", encoding="utf-8")
        with self.assertRaisesRegex(FindingValidationError, "ORIGINAL_SNAPSHOT_RECONSTRUCTION_FAILED"):
            self.validate()

    def test_snapshot_hash_mismatch_rejected(self):
        self.review["findings"][0]["source"]["snapshot_sha256"] = "a" * 64
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "SNAPSHOT_HASH_MISMATCH"):
            self.validate()

    def test_unknown_document_rejected(self):
        self.review["findings"][0]["source"]["document_id"] = "missing"
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "SOURCE_DOCUMENT_NOT_IN_BUNDLE"):
            self.validate()

    def test_text_not_in_snapshot_rejected(self):
        self.review["findings"][0]["locator"]["exact_text"] = "Invented clause."
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "TEXT_LOCATOR_NOT_FOUND"):
            self.validate()

    def test_pdf_page_locator_rejected_for_non_pdf_snapshot(self):
        self.review["findings"][0]["locator"] = {
            "kind": "pdf_page", "page": 1, "exact_text": "Section 4.1 permits personal research.",
        }
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "TEXT_LOCATOR_NOT_FOUND_ON_PAGE"):
            self.validate()

    def test_incomplete_finding_rejected(self):
        del self.review["findings"][0]["source"]["snapshot_sha256"]
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "SNAPSHOT_HASH_INVALID"):
            self.validate()

    def test_invalid_applicability_state_rejected(self):
        self.review["findings"][0]["applicability_status"] = "AUTHORIZED"
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "APPLICABILITY_STATUS_INVALID"):
            self.validate()

    def test_bundle_cannot_claim_legal_conclusion(self):
        self.bundle["legal_conclusion"] = "APPROVED"
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "EXTRACTION_BUNDLE_LEGAL_SCOPE_INVALID"):
            self.validate()

    def test_duplicate_finding_ids_rejected(self):
        self.review["findings"].append(dict(self.review["findings"][0]))
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "FINDING_ID_DUPLICATE_OR_INVALID"):
            self.validate()

    def test_validation_report_never_overwrites(self):
        report = self.validate()
        write_validation_report(report, self.output_path)
        with self.assertRaisesRegex(FindingValidationError, "VALIDATION_OUTPUT_ALREADY_EXISTS"):
            write_validation_report(report, self.output_path)

    def test_validation_report_cannot_be_written_inside_repository(self):
        report = self.validate()
        with self.assertRaisesRegex(FindingValidationError, "VALIDATION_OUTPUT_INSIDE_REPOSITORY"):
            write_validation_report(report, ROOT / "tests" / "should-not-exist.json")


if __name__ == "__main__":
    unittest.main()
