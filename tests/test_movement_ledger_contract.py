"""Schema and semantic invariants for the synthetic movement ledger."""
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT.parent / "schemas" / "movement-ledger.schema.json"
FIXTURE_PATH = ROOT / "fixtures" / "movement-ledger.json"


def resolve_temporal_status(event_time_utc, valid_from_utc, valid_to_utc, claim_found=True):
    """Resolve interval membership conservatively; boundaries are inclusive."""
    if not claim_found:
        return "CLAIM_NOT_FOUND"
    if event_time_utc is None:
        return "TIME_UNRESOLVED"
    try:
        event = datetime.fromisoformat(event_time_utc.replace("Z", "+00:00"))
        start = datetime.fromisoformat(valid_from_utc.replace("Z", "+00:00")) if valid_from_utc else None
        end = datetime.fromisoformat(valid_to_utc.replace("Z", "+00:00")) if valid_to_utc else None
    except (TypeError, ValueError):
        return "TIME_UNRESOLVED"
    if event.tzinfo is None or (start is not None and start.tzinfo is None) or (end is not None and end.tzinfo is None):
        return "TIME_UNRESOLVED"
    if start is not None and event < start:
        return "NOT_YET_VALID"
    if end is not None and event > end:
        return "EXPIRED_AT_EVENT_TIME"
    if start is None or end is None:
        return "TIME_UNRESOLVED"
    return "VALID_AT_EVENT_TIME"


class MovementLedgerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_schema_is_draft_2020_12(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["properties"]["contract_version"]["const"], "1.0.0")

    def test_all_synthetic_fixtures_validate(self):
        for item in self.fixtures:
            errors = list(self.validator.iter_errors(item))
            self.assertEqual(errors, [], "; ".join(error.message for error in errors))

    def test_fixture_ids_are_unique(self):
        ids = [item["movement_id"] for item in self.fixtures]
        self.assertEqual(len(ids), len(set(ids)))

    def test_supported_assets_have_consistent_network_and_unit(self):
        for item in self.fixtures:
            asset = item["asset"]
            if asset["asset_id"] == "bitcoin:btc":
                self.assertEqual((asset["symbol"], asset["network_id"], item["transfer"]["unit"]), ("BTC", "bitcoin-mainnet", "BTC"))
            else:
                self.assertEqual((asset["symbol"], asset["network_id"], item["transfer"]["unit"]), ("ETH", "eip155:1", "ETH"))

    def test_missing_amount_is_null_not_zero(self):
        item = next(x for x in self.fixtures if x["movement_id"] == "movement-eth-synthetic-002")
        self.assertIsNone(item["transfer"]["amount"])
        self.assertIn("amount_missing", item["limitations"])

    def test_transfer_is_not_trade_or_buy_sell(self):
        for item in self.fixtures:
            self.assertEqual(item["transfer"]["movement_type"], "TRANSFER")
            for forbidden in ("trade", "side", "buy_sell", "order", "ownership", "causal_driver"):
                self.assertNotIn(forbidden, item)
                self.assertNotIn(forbidden, item["transfer"])

    def test_provider_label_status_is_not_upgraded(self):
        item = self.fixtures[0]
        self.assertEqual(item["attribution_resolutions"][0]["epistemic_status"], "PROVIDER_LABELLED")

    def test_unknown_event_time_requires_unresolved_temporal_status(self):
        item = copy.deepcopy(self.fixtures[0])
        item["event_time_utc"] = None
        item["attribution_resolutions"][0]["temporal_status"] = "TIME_UNRESOLVED"
        self.assertTrue(self.validator.is_valid(item))
        item["attribution_resolutions"][0]["temporal_status"] = "VALID_AT_EVENT_TIME"
        self.assertFalse(self.validator.is_valid(item))

    def test_schema_rejects_trade_type(self):
        item = copy.deepcopy(self.fixtures[0])
        item["transfer"]["movement_type"] = "TRADE"
        self.assertFalse(self.validator.is_valid(item))

    def test_schema_rejects_mismatched_asset_unit(self):
        item = copy.deepcopy(self.fixtures[0])
        item["transfer"]["unit"] = "ETH"
        self.assertFalse(self.validator.is_valid(item))

    def test_schema_rejects_duplicate_source_observation_ids(self):
        item = copy.deepcopy(self.fixtures[0])
        item["source_observation_ids"].append(item["source_observation_ids"][0])
        self.assertFalse(self.validator.is_valid(item))

    def test_schema_rejects_non_utc_timestamp(self):
        item = copy.deepcopy(self.fixtures[0])
        item["recorded_at_utc"] = "2026-11-10T12:00:08+00:00"
        self.assertFalse(self.validator.is_valid(item))

    def test_schema_rejects_unrecognized_fields(self):
        item = copy.deepcopy(self.fixtures[0])
        item["confidence"] = 0.99
        self.assertFalse(self.validator.is_valid(item))

    def test_temporal_resolver_covers_validity_states(self):
        event = "2026-06-01T00:00:00Z"
        self.assertEqual(resolve_temporal_status(event, "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"), "VALID_AT_EVENT_TIME")
        self.assertEqual(resolve_temporal_status(event, "2026-07-01T00:00:00Z", None), "NOT_YET_VALID")
        self.assertEqual(resolve_temporal_status(event, "2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z"), "EXPIRED_AT_EVENT_TIME")
        self.assertEqual(resolve_temporal_status(None, "2025-01-01T00:00:00Z", None), "TIME_UNRESOLVED")
        self.assertEqual(resolve_temporal_status(event, None, None), "TIME_UNRESOLVED")
        self.assertEqual(resolve_temporal_status(event, None, None, claim_found=False), "CLAIM_NOT_FOUND")

    def test_temporal_boundaries_are_inclusive(self):
        instant = "2026-06-01T00:00:00Z"
        self.assertEqual(resolve_temporal_status(instant, instant, instant), "VALID_AT_EVENT_TIME")

    def test_invalid_timezone_or_timestamp_is_unresolved(self):
        self.assertEqual(resolve_temporal_status("not-a-time", None, None), "TIME_UNRESOLVED")
        self.assertEqual(resolve_temporal_status("2026-06-01T00:00:00", None, "2026-07-01T00:00:00Z"), "TIME_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
