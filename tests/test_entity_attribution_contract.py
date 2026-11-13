"""Draft 2020-12 validation and evidence invariants for attribution claims."""
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
FIXTURE_PATH = ROOT / "fixtures" / "entity-attribution-claims.json"
SCHEMA_PATH = ROOT.parent / "schemas" / "entity-attribution-claim.schema.json"


class EntityAttributionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.claims = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def test_schema_is_valid_draft_2020_12(self):
        self.assertEqual(
            self.schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )

    def test_all_synthetic_claims_validate(self):
        for claim in self.claims:
            errors = list(self.validator.iter_errors(claim))
            self.assertEqual(
                errors,
                [],
                f"{claim['claim_id']} failed: "
                + "; ".join(error.message for error in errors),
            )

    def test_provider_label_is_not_promoted_to_verified(self):
        claim = next(x for x in self.claims if x["claim_id"] == "claim-provider-label-001")
        self.assertEqual(claim["epistemic_status"], "PROVIDER_LABELLED")
        self.assertEqual(claim["review_status"], "UNREVIEWED")

    def test_conflicting_evidence_is_preserved_separately(self):
        claim = next(x for x in self.claims if x["epistemic_status"] == "DISPUTED")
        self.assertEqual(len(claim["supporting_evidence"]), 1)
        self.assertEqual(len(claim["counter_evidence"]), 1)
        self.assertNotEqual(
            claim["supporting_evidence"][0]["source"],
            claim["counter_evidence"][0]["source"],
        )

    def test_unknown_claim_can_exist_without_supporting_evidence(self):
        claim = next(x for x in self.claims if x["epistemic_status"] == "UNKNOWN")
        self.assertEqual(claim["supporting_evidence"], [])
        self.assertEqual(claim["counter_evidence"], [])

    def test_supersession_preserves_both_historical_claims(self):
        by_id = {claim["claim_id"]: claim for claim in self.claims}
        newer = by_id["claim-temporal-new-006"]
        older = by_id[newer["supersedes_claim_id"]]
        self.assertIn(older, self.claims)
        self.assertEqual(older["object"]["object_id"], "iwfi-entity-old")
        self.assertEqual(newer["object"]["object_id"], "iwfi-entity-new")
        self.assertNotEqual(older["claim_id"], newer["claim_id"])

    def test_validity_interval_is_chronologically_ordered(self):
        for claim in self.claims:
            start = claim["valid_from_utc"]
            end = claim["valid_to_utc"]
            if start is not None and end is not None:
                self.assertLessEqual(
                    datetime.fromisoformat(start.replace("Z", "+00:00")),
                    datetime.fromisoformat(end.replace("Z", "+00:00")),
                )

    def test_schema_rejects_verified_claim_without_support(self):
        claim = copy.deepcopy(next(x for x in self.claims if x["epistemic_status"] == "VERIFIED"))
        claim["supporting_evidence"] = []
        self.assertFalse(self.validator.is_valid(claim))

    def test_schema_rejects_disputed_claim_without_counter_evidence(self):
        claim = copy.deepcopy(next(x for x in self.claims if x["epistemic_status"] == "DISPUTED"))
        claim["counter_evidence"] = []
        self.assertFalse(self.validator.is_valid(claim))

    def test_schema_rejects_address_without_network_id(self):
        claim = copy.deepcopy(self.claims[0])
        claim["subject"]["network_id"] = None
        self.assertFalse(self.validator.is_valid(claim))

    def test_schema_rejects_label_claim_targeting_entity(self):
        claim = copy.deepcopy(self.claims[0])
        claim["object"] = {
            "object_type": "ENTITY",
            "object_id": "iwfi-entity-0001",
            "network_id": None,
        }
        self.assertFalse(self.validator.is_valid(claim))

    def test_schema_rejects_non_utc_claim_timestamp(self):
        claim = copy.deepcopy(self.claims[0])
        claim["recorded_at_utc"] = "2026-11-13T03:00:00+00:00"
        self.assertFalse(self.validator.is_valid(claim))

    def test_schema_rejects_unsupported_confidence_or_clustering_fields(self):
        claim = copy.deepcopy(self.claims[0])
        claim["confidence"] = 0.99
        self.assertFalse(self.validator.is_valid(claim))
        claim.pop("confidence")
        claim["cluster_id"] = "auto-cluster-1"
        self.assertFalse(self.validator.is_valid(claim))


if __name__ == "__main__":
    unittest.main()
