"""Contract invariants plus full Draft 2020-12 fixture validation."""
import copy
import json
import re
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE_PATH = ROOT / "fixtures" / "source-observations.json"
SCHEMA_PATH = ROOT.parent / "schemas" / "source-observation.schema.json"
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
STATUSES = {"VERIFIED", "PROVIDER_LABELLED", "INFERRED", "UNKNOWN", "DISPUTED"}
NETWORKS = {
    ("bitcoin:btc", "BTC", "bitcoin-mainnet"),
    ("ethereum:eth", "ETH", "eip155:1"),
}


class SourceObservationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_all_fixtures_validate_against_draft_2020_12_schema(self):
        for fixture in self.fixtures:
            errors = list(self.validator.iter_errors(fixture))
            self.assertEqual(
                errors,
                [],
                f"{fixture['observation_id']} failed schema validation: "
                + "; ".join(error.message for error in errors),
            )

    def test_schema_rejects_asset_symbol_network_mismatch(self):
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["asset"]["symbol"] = "ETH"
        self.assertFalse(self.validator.is_valid(fixture))

    def test_schema_rejects_transfer_unit_mismatch(self):
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["movement"]["unit"] = "ETH"
        self.assertFalse(self.validator.is_valid(fixture))

    def test_schema_rejects_exchange_flow_encoded_as_movement(self):
        fixture = copy.deepcopy(next(
            x for x in self.fixtures if x["observation_type"] == "EXCHANGE_FLOW_METRIC"
        ))
        fixture["movement"] = None
        self.assertFalse(self.validator.is_valid(fixture))

    def test_schema_rejects_non_utc_timestamp(self):
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["retrieved_at_utc"] = "2026-11-11T10:00:03+00:00"
        self.assertFalse(self.validator.is_valid(fixture))

    def test_schema_rejects_raw_retention_while_terms_are_pending(self):
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["retention"] = {
            "retention_classification": "UNKNOWN_PENDING_TERMS",
            "raw_payload_retained": True,
        }
        self.assertFalse(self.validator.is_valid(fixture))

    def test_schema_is_draft_2020_12_and_versioned(self):
        self.assertEqual(
            self.schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        self.assertEqual(self.schema["properties"]["contract_version"]["const"], "1.0.0")

    def test_fixture_ids_are_unique_and_required_fields_exist(self):
        ids = [item["observation_id"] for item in self.fixtures]
        self.assertEqual(len(ids), len(set(ids)))
        required = set(self.schema["required"])
        for item in self.fixtures:
            self.assertTrue(required.issubset(item.keys()))

    def test_assets_have_explicit_supported_network_identity(self):
        for item in self.fixtures:
            asset = item["asset"]
            self.assertIn(
                (asset["asset_id"], asset["symbol"], asset["network_id"]),
                NETWORKS,
            )

    def test_timestamps_are_utc_and_retrieval_is_not_event_time(self):
        for item in self.fixtures:
            self.assertRegex(item["retrieved_at_utc"], UTC_RE)
            if item["event_time_utc"] is not None:
                self.assertRegex(item["event_time_utc"], UTC_RE)

    def test_source_integrity_hash_shape(self):
        for item in self.fixtures:
            self.assertRegex(item["source"]["payload_sha256"], HASH_RE)

    def test_missing_amount_is_not_zero(self):
        item = next(x for x in self.fixtures if x["observation_id"] == "fixture-missing-amount")
        self.assertIsNone(item["movement"]["amount"])
        self.assertEqual(item["quality"]["status"], "PARTIAL")
        self.assertIn("amount_missing", item["quality"]["notes"])

    def test_duplicate_is_explicit_and_references_canonical_observation(self):
        item = next(x for x in self.fixtures if x["quality"]["status"] == "DUPLICATE")
        ids = {x["observation_id"] for x in self.fixtures}
        self.assertIn(item["quality"]["duplicate_of"], ids)
        self.assertNotEqual(item["observation_id"], item["quality"]["duplicate_of"])

    def test_conflicting_attributions_are_preserved_as_separate_claims(self):
        item = next(x for x in self.fixtures if x["observation_id"] == "fixture-conflicting-attribution")
        claims = item["attributions"]
        self.assertGreaterEqual(len(claims), 2)
        self.assertEqual({claim["claim_source"] for claim in claims}, {"vendor-a", "vendor-b"})
        self.assertTrue(all(claim["status"] in STATUSES for claim in claims))
        self.assertIn("DISPUTED", {claim["status"] for claim in claims})

    def test_provider_label_is_not_verified_identity(self):
        item = next(x for x in self.fixtures if x["observation_id"] == "fixture-exchange-label")
        self.assertEqual(item["attributions"][0]["status"], "PROVIDER_LABELLED")
        self.assertNotEqual(item["attributions"][0]["status"], "VERIFIED")

    def test_transfer_is_never_encoded_as_trade_or_buy_sell(self):
        for item in self.fixtures:
            if item["observation_type"] == "ON_CHAIN_TRANSACTION":
                self.assertEqual(item["movement"]["movement_type"], "TRANSFER")
                self.assertNotIn("trade", item)
                self.assertNotIn("side", item)
                self.assertNotIn("buy_sell", item)

    def test_exchange_inflow_is_a_metric_not_a_trade(self):
        item = next(x for x in self.fixtures if x["observation_type"] == "EXCHANGE_FLOW_METRIC")
        self.assertEqual(item["measurement"]["direction"], "IN")
        self.assertEqual(item["measurement"]["metric_name"], "exchange_inflow")
        self.assertNotIn("trade", item)
        self.assertNotIn("side", item)
        self.assertNotIn("buy_sell", item)

    def test_delayed_observation_preserves_both_times(self):
        item = next(x for x in self.fixtures if x["quality"]["status"] == "DELAYED")
        self.assertNotEqual(item["event_time_utc"], item["retrieved_at_utc"])
        self.assertIn("retrieved_24h_after_event", item["quality"]["notes"])

    def test_raw_payload_is_not_retained_by_default_fixture_policy(self):
        for item in self.fixtures:
            if item["retention"]["retention_classification"] in {"HASH_ONLY", "UNKNOWN_PENDING_TERMS"}:
                self.assertFalse(item["retention"]["raw_payload_retained"])


if __name__ == "__main__":
    unittest.main()
