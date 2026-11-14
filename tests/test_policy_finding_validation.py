import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_policy_findings import (
    FindingValidationError, ROOT, validate_policy_findings, write_validation_report,
)


class PolicyFindingValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.bundle_path = self.directory / "bundle.json"
        self.review_path = self.directory / "review.json"
        self.output_path = self.directory / "report.json"
        self.document_text = "Section 4.1 permits personal research.\nNo commercial use."
        self.page_text = "Section 25. Services may be suspended."
        self.snapshot_hash = hashlib.sha256(b"snapshot bytes").hexdigest()
        self.bundle = {
            "bundle_version": "1.0.0",
            "bundle_scope": "LOCAL_ONLY",
            "technical_integrity_verified": True,
            "legal_conclusion": "NOT_PROVIDED",
            "documents": [{
                "document_id": "policy_a",
                "sha256": self.snapshot_hash,
                "text": self.document_text,
                "pages": [{"page": 1, "text": self.page_text}],
            }],
        }
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

    def test_exact_snapshot_and_text_locator_are_verified(self):
        report = validate_policy_findings(self.bundle_path, self.review_path)
        self.assertEqual(report["validation_status"], "ALL_REFERENCES_VERIFIED")
        self.assertEqual(report["findings"][0]["reference_status"], "REFERENCE_VERIFIED")
        self.assertTrue(report["reference_verification_only"])

    def test_snapshot_hash_mismatch_rejected(self):
        self.review["findings"][0]["source"]["snapshot_sha256"] = "a" * 64
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "SNAPSHOT_HASH_MISMATCH"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_unknown_document_rejected(self):
        self.review["findings"][0]["source"]["document_id"] = "missing"
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "SOURCE_DOCUMENT_NOT_IN_BUNDLE"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_text_not_in_snapshot_rejected(self):
        self.review["findings"][0]["locator"]["exact_text"] = "Invented clause."
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "TEXT_LOCATOR_NOT_FOUND"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_pdf_page_locator_must_match_selected_page(self):
        self.review["findings"][0]["locator"] = {
            "kind": "pdf_page", "page": 2,
            "exact_text": "Section 25. Services may be suspended.",
        }
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "TEXT_LOCATOR_NOT_FOUND_ON_PAGE"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_pdf_page_locator_succeeds_on_exact_page(self):
        self.review["findings"][0]["locator"] = {
            "kind": "pdf_page", "page": 1,
            "exact_text": "Section 25. Services may be suspended.",
        }
        self.write_inputs()
        report = validate_policy_findings(self.bundle_path, self.review_path)
        self.assertEqual(report["findings"][0]["page"], 1)

    def test_incomplete_finding_rejected(self):
        del self.review["findings"][0]["source"]["snapshot_sha256"]
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "SNAPSHOT_HASH_INVALID"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_invalid_applicability_state_rejected(self):
        self.review["findings"][0]["applicability_status"] = "AUTHORIZED"
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "APPLICABILITY_STATUS_INVALID"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_bundle_cannot_claim_legal_conclusion(self):
        self.bundle["legal_conclusion"] = "APPROVED"
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "EXTRACTION_BUNDLE_LEGAL_SCOPE_INVALID"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_duplicate_finding_ids_rejected(self):
        self.review["findings"].append(dict(self.review["findings"][0]))
        self.write_inputs()
        with self.assertRaisesRegex(FindingValidationError, "FINDING_ID_DUPLICATE_OR_INVALID"):
            validate_policy_findings(self.bundle_path, self.review_path)

    def test_validation_report_never_overwrites(self):
        report = validate_policy_findings(self.bundle_path, self.review_path)
        write_validation_report(report, self.output_path)
        with self.assertRaisesRegex(FindingValidationError, "VALIDATION_OUTPUT_ALREADY_EXISTS"):
            write_validation_report(report, self.output_path)

    def test_validation_report_cannot_be_written_inside_repository(self):
        report = validate_policy_findings(self.bundle_path, self.review_path)
        with self.assertRaisesRegex(FindingValidationError, "VALIDATION_OUTPUT_INSIDE_REPOSITORY"):
            write_validation_report(report, ROOT / "tests" / "should-not-exist.json")


if __name__ == "__main__":
    unittest.main()
