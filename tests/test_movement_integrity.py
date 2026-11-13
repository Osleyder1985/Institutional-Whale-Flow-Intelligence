"""Cross-contract integrity tests using only existing synthetic fixtures."""
import copy
import json
import unittest
from pathlib import Path

from iwfi.movement_integrity import resolve_temporal_status, validate_movement_integrity

ROOT = Path(__file__).resolve().parent


class MovementIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.movements = json.loads((ROOT / "fixtures" / "movement-ledger.json").read_text(encoding="utf-8"))
        cls.observations = json.loads((ROOT / "fixtures" / "movement-integrity-source-observations.json").read_text(encoding="utf-8"))
        cls.claims = json.loads((ROOT / "fixtures" / "entity-attribution-claims.json").read_text(encoding="utf-8"))

    def test_integrity_source_fixtures_validate_against_canonical_schema(self):
        from jsonschema import Draft202012Validator, FormatChecker
        schema = json.loads((ROOT.parent / "schemas" / "source-observation.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for observation in self.observations:
            self.assertEqual(list(validator.iter_errors(observation)), [])

    def test_claim_fixtures_validate_against_canonical_schema(self):
        from jsonschema import Draft202012Validator, FormatChecker
        schema = json.loads((ROOT.parent / "schemas" / "entity-attribution-claim.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for claim in self.claims:
            self.assertEqual(list(validator.iter_errors(claim)), [])

    def test_btc_and_eth_movements_resolve_against_source_observations(self):
        for movement in self.movements:
            self.assertEqual(validate_movement_integrity(movement, self.observations, self.claims), [])

    def test_duplicate_observation_ids_are_rejected_independent_of_input_order(self):
        duplicate = copy.deepcopy(self.observations[0])
        duplicate["observation_id"] = self.observations[0]["observation_id"]
        forward = self.observations + [duplicate]
        reverse = [duplicate] + self.observations
        errors_forward = validate_movement_integrity(self.movements[0], forward, self.claims)
        errors_reverse = validate_movement_integrity(self.movements[0], reverse, self.claims)
        self.assertEqual(errors_forward, errors_reverse)
        self.assertIn(f"duplicate observation_id: {duplicate['observation_id']}", errors_forward)

    def test_duplicate_claim_ids_are_rejected_independent_of_input_order(self):
        duplicate = copy.deepcopy(self.claims[0])
        duplicate["claim_id"] = self.claims[0]["claim_id"]
        forward = self.claims + [duplicate]
        reverse = [duplicate] + self.claims
        errors_forward = validate_movement_integrity(self.movements[0], self.observations, forward)
        errors_reverse = validate_movement_integrity(self.movements[0], self.observations, reverse)
        self.assertEqual(errors_forward, errors_reverse)
        self.assertIn(f"duplicate claim_id: {duplicate['claim_id']}", errors_forward)

    def test_missing_source_observation_is_rejected(self):
        movement = copy.deepcopy(self.movements[0])
        movement["source_observation_ids"] = ["not-present"]
        self.assertIn("source observation not found: not-present", validate_movement_integrity(movement, self.observations, self.claims))

    def test_aggregate_exchange_flow_cannot_back_a_transfer(self):
        movement = copy.deepcopy(self.movements[0])
        movement["source_observation_ids"] = ["fixture-exchange-inflow"]
        errors = validate_movement_integrity(movement, self.observations, self.claims)
        self.assertTrue(any("not ON_CHAIN_TRANSACTION" in error for error in errors))

    def test_source_event_locator_mismatch_is_rejected(self):
        movement = copy.deepcopy(self.movements[0])
        movement["transfer"]["event_locator"]["value"] = "9"
        self.assertTrue(any("event_locator mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_source_transaction_mismatch_is_rejected(self):
        movement = copy.deepcopy(self.movements[0])
        movement["transfer"]["transaction_id"] = "different-tx"
        self.assertTrue(any("transaction_id mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_source_asset_network_mismatch_is_rejected(self):
        movement = copy.deepcopy(self.movements[0])
        movement["asset"]["network_id"] = "eip155:1"
        self.assertTrue(any("asset/network mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_known_source_amount_cannot_be_dropped(self):
        movement = copy.deepcopy(self.movements[0])
        movement["transfer"]["amount"] = None
        self.assertTrue(any("known source amount omitted" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_known_source_event_time_cannot_be_dropped(self):
        movement = copy.deepcopy(self.movements[0])
        movement["event_time_utc"] = None
        self.assertTrue(any("known source event_time omitted" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_source_confirmation_status_mismatch_is_rejected(self):
        movement = copy.deepcopy(self.movements[0])
        movement["transfer"]["confirmation_status"] = "PENDING"
        self.assertTrue(any("confirmation_status mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_source_unit_mismatch_is_rejected(self):
        movement = copy.deepcopy(self.movements[0])
        movement["transfer"]["unit"] = "ETH"
        self.assertTrue(any("unit mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_unknown_source_quality_is_rejected_fail_closed(self):
        observations = copy.deepcopy(self.observations)
        observations[0]["quality"]["status"] = "UNRECOGNIZED"
        errors = validate_movement_integrity(self.movements[0], observations, self.claims)
        self.assertTrue(any("quality is not admissible" in error for error in errors))

    def test_claim_subject_and_predicate_must_match(self):
        movement = copy.deepcopy(self.movements[0])
        movement["attribution_resolutions"][0]["address"] = "bc1qsource"
        self.assertTrue(any("claim subject/address mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_claim_network_must_match_asset_network(self):
        movement = copy.deepcopy(self.movements[0])
        movement["asset"]["network_id"] = "eip155:1"
        errors = validate_movement_integrity(movement, self.observations, self.claims)
        self.assertTrue(any("claim network mismatch" in error for error in errors))

    def test_claim_temporal_status_must_match_claim_interval(self):
        movement = copy.deepcopy(self.movements[0])
        movement["attribution_resolutions"][0]["temporal_status"] = "VALID_AT_EVENT_TIME"
        self.assertTrue(any("temporal_status mismatch" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_unknown_claim_requires_claim_not_found_status(self):
        movement = copy.deepcopy(self.movements[0])
        movement["attribution_resolutions"][0]["claim_id"] = "absent-claim"
        self.assertTrue(any("missing claim must use CLAIM_NOT_FOUND" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_temporal_interval_requires_both_bounds_for_valid_status(self):
        self.assertEqual(resolve_temporal_status("2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", None), "TIME_UNRESOLVED")
        self.assertEqual(resolve_temporal_status("2026-06-01T00:00:00Z", "2026-07-01T00:00:00Z", None), "NOT_YET_VALID")
        self.assertEqual(resolve_temporal_status("2026-06-01T00:00:00Z", "2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z"), "EXPIRED_AT_EVENT_TIME")
        self.assertEqual(resolve_temporal_status("2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"), "VALID_AT_EVENT_TIME")

    def test_temporal_interval_with_reversed_bounds_is_unresolved(self):
        self.assertEqual(resolve_temporal_status("2026-06-01T00:00:00Z", "2026-12-01T00:00:00Z", "2026-01-01T00:00:00Z"), "TIME_UNRESOLVED")

    def test_unsupported_amount_cannot_be_added_when_all_sources_are_missing(self):
        movement = copy.deepcopy(self.movements[1])
        movement["transfer"]["amount"] = "0.5"
        self.assertTrue(any("amount has no supporting source value" in error for error in validate_movement_integrity(movement, self.observations, self.claims)))

    def test_invalid_or_duplicate_source_quality_is_rejected(self):
        observations = copy.deepcopy(self.observations)
        observations[0]["quality"]["status"] = "DUPLICATE"
        errors = validate_movement_integrity(self.movements[0], observations, self.claims)
        self.assertTrue(any("quality is not admissible" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
