import hashlib
import json
import unittest
from pathlib import Path

import jsonschema

from scripts.documentary_claim_provenance import (
    DocumentaryClaimError, validate_claim, validate_claim_collection, validate_snapshot_catalog,
)


BODY_HASH = hashlib.sha256(b"snapshot bytes").hexdigest()
SPAN_HASH = hashlib.sha256(b"section 3.1 extracted span").hexdigest()
SNAPSHOT = {
    "document_id": "policy_terms_v1",
    "snapshot_sha256": BODY_HASH,
    "source_url": "https://example.org/policy-v1.txt",
    "retrieved_at_utc": "2026-11-14T12:00:00Z",
    "document_version": "v1",
}


def claim(**changes):
    value = {
        "contract_version": "1.0.0",
        "claim_id": "claim-001",
        "claim_text": "The source defines a non-commercial use restriction.",
        "expression_type": "PARAPHRASE",
        "epistemic_status": "PROVIDER_LABELLED",
        "evidence": [{
            **SNAPSHOT,
            "locator": {"locator_type": "CLAUSE", "value": "3.1"},
            "extracted_span_sha256": SPAN_HASH,
        }],
        "targets": [{"target_type": "HYPOTHESIS", "target_id": "hypothesis-7", "relation": "SUPPORTS"}],
        "review_status": "PENDING",
        "reviewer": None,
        "reviewed_at_utc": None,
        "uncertainty_note": "Applicability to the project has not been assessed.",
        "authorization_status": "NOT_GRANTED",
        "legal_review_status": "NOT_PERFORMED",
        "recorded_at_utc": "2026-11-14T12:05:00Z",
    }
    value.update(changes)
    return value


class DocumentaryClaimProvenanceTests(unittest.TestCase):
    def test_valid_paraphrase_links_exact_snapshot_and_clause(self):
        self.assertTrue(validate_claim(claim(), [SNAPSHOT])["valid"])

    def test_missing_snapshot_hash_rejected(self):
        item = claim()
        item["evidence"][0]["snapshot_sha256"] = ""
        self.assertIn("SNAPSHOT_REFERENCE_INVALID", validate_claim(item, [SNAPSHOT])["errors"])

    def test_wrong_snapshot_hash_rejected(self):
        item = claim()
        item["evidence"][0]["snapshot_sha256"] = "0" * 64
        self.assertIn("SNAPSHOT_NOT_REGISTERED_OR_HASH_MISMATCH", validate_claim(item, [SNAPSHOT])["errors"])

    def test_source_url_mismatch_rejected(self):
        item = claim()
        item["evidence"][0]["source_url"] = "https://example.org/other.txt"
        self.assertIn("SNAPSHOT_METADATA_MISMATCH", validate_claim(item, [SNAPSHOT])["errors"])

    def test_retrieval_time_or_version_mismatch_rejected(self):
        item = claim()
        item["evidence"][0]["document_version"] = "v2"
        self.assertIn("SNAPSHOT_METADATA_MISMATCH", validate_claim(item, [SNAPSHOT])["errors"])

    def test_invalid_clause_locator_rejected(self):
        item = claim()
        item["evidence"][0]["locator"] = {"locator_type": "UNKNOWN", "value": "3.1"}
        self.assertIn("LOCATOR_INVALID", validate_claim(item, [SNAPSHOT])["errors"])

    def test_invalid_character_range_rejected(self):
        item = claim()
        item["evidence"][0]["locator"] = {"locator_type": "CHARACTER_RANGE", "value": "offsets", "start_offset": 8, "end_offset": 4}
        self.assertIn("LOCATOR_RANGE_INVALID", validate_claim(item, [SNAPSHOT])["errors"])

    def test_verbatim_requires_extracted_span_hash_not_quote_text(self):
        item = claim(expression_type="VERBATIM")
        del item["evidence"][0]["extracted_span_sha256"]
        self.assertIn("EXTRACTED_SPAN_HASH_REQUIRED", validate_claim(item, [SNAPSHOT])["errors"])

    def test_inference_is_not_misrepresented_as_literal_quote(self):
        item = claim(expression_type="INFERENCE", epistemic_status="INFERRED")
        item["evidence"][0].pop("extracted_span_sha256")
        self.assertTrue(validate_claim(item, [SNAPSHOT])["valid"])
        item["evidence"][0]["extracted_span_sha256"] = SPAN_HASH
        self.assertIn("INFERENCE_MUST_NOT_CLAIM_LITERAL_SPAN", validate_claim(item, [SNAPSHOT])["errors"])

    def test_inference_without_evidence_rejected(self):
        item = claim(expression_type="INFERENCE", epistemic_status="INFERRED", evidence=[])
        self.assertIn("EVIDENCE_REQUIRED", validate_claim(item, [SNAPSHOT])["errors"])

    def test_missing_iwfi_target_rejected(self):
        item = claim(targets=[])
        self.assertIn("IWFI_TARGET_REQUIRED", validate_claim(item, [SNAPSHOT])["errors"])

    def test_reviewed_claim_requires_reviewer_and_timestamp(self):
        item = claim(review_status="REVIEWED")
        self.assertIn("REVIEW_METADATA_REQUIRED", validate_claim(item, [SNAPSHOT])["errors"])

    def test_authorization_cannot_be_promoted(self):
        item = claim(authorization_status="GRANTED")
        self.assertIn("AUTHORIZATION_STATE_MUST_REMAIN_NOT_GRANTED", validate_claim(item, [SNAPSHOT])["errors"])

    def test_legal_review_state_cannot_be_fabricated(self):
        item = claim(legal_review_status="COMPLETED")
        self.assertIn("LEGAL_REVIEW_STATE_MUST_REMAIN_NOT_PERFORMED", validate_claim(item, [SNAPSHOT])["errors"])

    def test_conflicting_claims_are_preserved_as_a_group(self):
        first = claim(contradiction_group_id="policy-version-conflict")
        second = claim(claim_id="claim-002", claim_text="A later snapshot describes a different scope.",
                       contradiction_group_id="policy-version-conflict")
        second["evidence"][0]["snapshot_sha256"] = "1" * 64
        second["evidence"][0]["document_version"] = "v2"
        second["evidence"][0]["retrieved_at_utc"] = "2026-11-15T12:00:00Z"
        catalog = [SNAPSHOT, {**SNAPSHOT, "snapshot_sha256": "1" * 64, "document_version": "v2",
                              "retrieved_at_utc": "2026-11-15T12:00:00Z"}]
        result = validate_claim_collection([first, second], catalog)
        self.assertTrue(result["valid"])
        self.assertEqual(result["contradiction_groups"]["policy-version-conflict"], ["claim-001", "claim-002"])

    def test_duplicate_claim_ids_rejected(self):
        result = validate_claim_collection([claim(), claim()], [SNAPSHOT])
        self.assertFalse(result["valid"])
        self.assertIn("DUPLICATE_CLAIM_ID", result["errors"])

    def test_multiple_distinct_clauses_from_one_snapshot_are_allowed(self):
        item = claim()
        second = dict(item["evidence"][0])
        second["locator"] = {"locator_type": "CLAUSE", "value": "4.2"}
        second["extracted_span_sha256"] = hashlib.sha256(b"section 4.2").hexdigest()
        item["evidence"].append(second)
        self.assertTrue(validate_claim(item, [SNAPSHOT])["valid"])

    def test_json_schema_accepts_valid_claim_and_enforces_expression_rules(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "documentary-attribution-claim-v1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        valid = claim()
        self.assertEqual(list(validator.iter_errors(valid)), [])

        verbatim_without_span = claim(expression_type="VERBATIM")
        verbatim_without_span["evidence"][0].pop("extracted_span_sha256")
        self.assertTrue(list(validator.iter_errors(verbatim_without_span)))

        inference_with_literal_span = claim(expression_type="INFERENCE", epistemic_status="INFERRED")
        self.assertTrue(list(validator.iter_errors(inference_with_literal_span)))

    def test_json_schema_requires_reviewer_metadata_for_reviewed_claim(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "documentary-attribution-claim-v1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        item = claim(review_status="REVIEWED")
        self.assertTrue(list(validator.iter_errors(item)))

    def test_duplicate_snapshot_identity_rejected(self):
        with self.assertRaisesRegex(DocumentaryClaimError, "DUPLICATE_SNAPSHOT_IDENTITY"):
            validate_snapshot_catalog([SNAPSHOT, SNAPSHOT])

    def test_claim_without_snapshot_catalog_rejected(self):
        self.assertFalse(validate_claim(claim(), [])["valid"])


if __name__ == "__main__":
    unittest.main()
