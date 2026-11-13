"""Deterministic observation-resolution policy tests."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from iwfi.observation_resolution import (
    classify_observation_pair,
    resolve_observations,
)

ROOT = Path(__file__).resolve().parent


class ObservationResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(
            (ROOT / "fixtures" / "observation-resolution.json").read_text(encoding="utf-8")
        )

    def test_resolution_fixtures_validate_against_source_observation_schema(self):
        schema = json.loads((ROOT.parent / "schemas" / "source-observation.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for fixture in self.fixtures:
            self.assertEqual(list(validator.iter_errors(fixture)), [])

    def test_policy_document_covers_provider_duplicate_resolution(self):
        document = (ROOT.parent / "docs" / "data-model" / "observation-resolution-policy.md").read_text(encoding="utf-8")
        section_numbers = [
            line.split(".")[0].removeprefix("## ")
            for line in document.splitlines()
            if line.startswith("## ")
        ]
        self.assertEqual(section_numbers, [str(number) for number in range(1, 13)])
        self.assertIn("quality.duplicate_of", document)
        self.assertIn("RESOLVED_WITH_RELATION_CONFLICTS", document)
        self.assertIn("SOURCE_RECORD_REPEAT_CONTRADICTS_EVENT_IDENTITY", document)
        self.assertIn("It never overrides transaction/event identity.", document)
        self.assertNotIn("\\n-", document)

    def by_id(self, identifier):
        return copy.deepcopy(next(item for item in self.fixtures if item["observation_id"] == identifier))

    def test_same_btc_event_from_two_providers_is_one_strong_event(self):
        result = resolve_observations([self.by_id("btc-vout-provider-a"), self.by_id("btc-vout-provider-b")])
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(event["identity_status"], "RESOLVED")
        self.assertEqual(event["analytical_eligibility"], "ELIGIBLE")
        self.assertEqual(len(event["observation_ids"]), 2)
        self.assertEqual(result["links"][0]["match_class"], "STRONG_MATCH")

    def test_provider_declared_duplicate_is_preserved_as_a_separate_relation(self):
        original = self.by_id("btc-vout-provider-a")
        duplicate = copy.deepcopy(original)
        duplicate["observation_id"] = "btc-declared-duplicate"
        duplicate["source"]["record_id"] = None
        duplicate["quality"]["status"] = "DUPLICATE"
        duplicate["quality"]["duplicate_of"] = original["observation_id"]
        result = resolve_observations([original, duplicate])
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["observation_ids"], [original["observation_id"]])
        self.assertEqual(result["events"][0]["excluded_observation_ids"], [duplicate["observation_id"]])
        self.assertEqual(result["links"][0]["match_class"], "STRONG_MATCH")
        self.assertEqual(
            result["links"][0]["provider_duplicate_relation"],
            "LEFT_DECLARED_DUPLICATE_OF_RIGHT",
        )
        self.assertIn(
            "PROVIDER_DUPLICATE_CONSISTENT_WITH_EVENT_IDENTITY",
            result["links"][0]["reasons"],
        )

    def test_duplicate_same_event_with_conflicting_fields_blocks_eligibility(self):
        original = self.by_id("btc-vout-provider-a")
        duplicate = copy.deepcopy(original)
        duplicate["observation_id"] = "btc-duplicate-conflicting-amount"
        duplicate["quality"] = {"status": "DUPLICATE", "duplicate_of": original["observation_id"]}
        duplicate["movement"]["amount"] = "2"
        result = resolve_observations([original, duplicate])
        event = result["events"][0]
        self.assertEqual(event["resolution_status"], "CONTRADICTORY")
        self.assertEqual(event["analytical_eligibility"], "INELIGIBLE")
        self.assertEqual(event["relationship_conflicts"][0]["field_conflicts"], ["amount"])
        self.assertIn("CONTRADICTORY_DUPLICATE_OR_SOURCE_REPEAT_RELATION", event["eligibility_reasons"])
        self.assertEqual(result["status"], "RESOLVED_WITH_RELATION_CONFLICTS")

    def test_exact_provider_repeat_with_conflicting_fields_is_a_relation_conflict(self):
        original = self.by_id("btc-vout-provider-a")
        repeated = copy.deepcopy(original)
        repeated["observation_id"] = "btc-same-record-conflicting-amount"
        repeated["movement"]["amount"] = "2"
        result = resolve_observations([original, repeated])
        self.assertEqual(result["events"][0]["resolution_status"], "CONTRADICTORY")
        self.assertIn("SOURCE_RECORD_REPEAT_CONTRADICTS_EVENT_FIELDS", result["links"][0]["reasons"])
        self.assertEqual(result["status"], "RESOLVED_WITH_RELATION_CONFLICTS")

    def test_provider_duplicate_claim_cannot_override_distinct_event_identity(self):
        original = self.by_id("btc-vout-provider-a")
        duplicate = copy.deepcopy(original)
        duplicate["observation_id"] = "btc-false-duplicate-claim"
        duplicate["source"]["record_id"] = None
        duplicate["source"]["payload_sha256"] = "f" * 64
        duplicate["movement"]["event_locator"]["value"] = "1"
        duplicate["quality"]["status"] = "DUPLICATE"
        duplicate["quality"]["duplicate_of"] = original["observation_id"]
        result = resolve_observations([original, duplicate])
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["status"], "RESOLVED_WITH_RELATION_CONFLICTS")
        self.assertEqual(result["links"][0]["match_class"], "NO_MATCH")
        self.assertIn(
            "PROVIDER_DUPLICATE_CONTRADICTS_EVENT_IDENTITY",
            result["links"][0]["reasons"],
        )
        self.assertTrue(all(event["analytical_eligibility"] == "INELIGIBLE" for event in result["events"]))
        self.assertTrue(all(event["resolution_status"] == "CONTRADICTORY" for event in result["events"]))
        self.assertTrue(all(
            "CONTRADICTORY_EVENT_IDENTITY_RELATION" in event["eligibility_reasons"]
            for event in result["events"]
        ))
        self.assertTrue(any(event["excluded_observation_ids"] == ["btc-false-duplicate-claim"] for event in result["events"]))
        self.assertEqual(len({event["event_id"] for event in result["events"]}), 2)

    def test_provider_duplicate_claim_across_networks_is_a_visible_conflict(self):
        btc = self.by_id("btc-vout-provider-a")
        eth = self.by_id("eth-log-provider-a")
        eth["quality"]["status"] = "DUPLICATE"
        eth["quality"]["duplicate_of"] = btc["observation_id"]
        result = resolve_observations([btc, eth])
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["status"], "RESOLVED_WITH_RELATION_CONFLICTS")
        self.assertEqual(result["links"][0]["match_class"], "NO_MATCH")
        self.assertIn("DIFFERENT_NETWORK", result["links"][0]["reasons"])
        self.assertIn(
            "PROVIDER_DUPLICATE_CONTRADICTS_EVENT_IDENTITY",
            result["links"][0]["reasons"],
        )
        self.assertTrue(all(event["analytical_eligibility"] == "INELIGIBLE" for event in result["events"]))
        self.assertTrue(all(event["resolution_status"] == "CONTRADICTORY" for event in result["events"]))

    def test_duplicate_reference_requires_duplicate_quality_status(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["quality"]["duplicate_of"] = "canonical-observation"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "duplicate_of requires DUPLICATE quality status: btc-vout-provider-a",
            result["errors"],
        )

    def test_duplicate_quality_requires_non_self_duplicate_reference(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["quality"]["status"] = "DUPLICATE"
        observation["quality"]["duplicate_of"] = observation["observation_id"]
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "observation cannot be duplicate of itself: btc-vout-provider-a",
            result["errors"],
        )

    def test_same_provider_record_repeat_is_not_a_second_event(self):
        first = self.by_id("btc-vout-provider-a")
        repeated = copy.deepcopy(first)
        repeated["observation_id"] = "btc-vout-provider-a-repeat"
        result = resolve_observations([first, repeated])
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["links"][0]["source_record_relation"], "EXACT_REPEAT")

    def test_same_transaction_can_contain_distinct_transfer_events(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-second-vout")
        link = classify_observation_pair(first, second)
        self.assertEqual(link["match_class"], "NO_MATCH")
        self.assertIn("DIFFERENT_EVENT_LOCATOR", link["reasons"])
        self.assertEqual(len(resolve_observations([first, second])["events"]), 2)

    def test_eth_transaction_can_contain_distinct_internal_trace_events(self):
        first = self.by_id("eth-log-provider-a")
        second = copy.deepcopy(first)
        second["observation_id"] = "eth-second-log"
        second["movement"]["event_locator"] = {"kind": "EVM_TRACE_PATH", "value": "0/6"}
        second["source"]["payload_sha256"] = "f" * 64
        result = resolve_observations([first, second])
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["links"][0]["match_class"], "NO_MATCH")
        self.assertEqual(result["links"][0]["source_record_relation"], "SAME_RECORD_DIFFERENT_PAYLOAD")
        self.assertIn("DIFFERENT_EVENT_LOCATOR", result["links"][0]["reasons"])

    def test_eth_provider_trace_paths_normalize_to_one_native_transfer(self):
        first = self.by_id("eth-log-provider-a")
        second = self.by_id("eth-log-provider-b")
        result = resolve_observations([first, second])
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["event_locator"], {"kind": "EVM_TRACE_PATH", "value": "0/5"})
        self.assertEqual(result["links"][0]["match_class"], "STRONG_MATCH")

    def test_same_transaction_hash_on_different_networks_is_not_a_match(self):
        btc = self.by_id("btc-vout-provider-a")
        eth = self.by_id("eth-log-provider-a")
        eth["movement"]["transaction_id"] = "0x" + btc["movement"]["transaction_id"]
        link = classify_observation_pair(btc, eth)
        self.assertEqual(link["match_class"], "NO_MATCH")
        self.assertIn("DIFFERENT_NETWORK", link["reasons"])

    def test_different_transactions_are_not_merged_by_amount_addresses_or_time(self):
        first = self.by_id("btc-vout-provider-a")
        second = copy.deepcopy(first)
        second["observation_id"] = "different-tx-same-facts"
        second["movement"]["transaction_id"] = "f" * 64
        self.assertEqual(classify_observation_pair(first, second)["match_class"], "NO_MATCH")
        self.assertEqual(len(resolve_observations([first, second])["events"]), 2)

    def test_invalid_event_time_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["event_time_utc"] = "2026-02-30T10:00:00Z"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("invalid event_time_utc: btc-vout-provider-a", result["errors"])

    def test_non_ascii_numeric_locator_is_rejected(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["event_locator"]["value"] = "٠"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("invalid event_locator for observation: btc-vout-provider-a", result["errors"])

    def test_very_long_numeric_locator_normalizes_without_integer_conversion(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["event_locator"]["value"] = "0" * 5000 + "1"
        event = resolve_observations([observation])["events"][0]
        self.assertEqual(event["event_locator"]["value"], "1")

    def test_invalid_transaction_hash_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["transaction_id"] = "not-a-real-txid"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("invalid transaction_id for network: btc-vout-provider-a", result["errors"])

    def test_ethereum_transaction_hash_with_or_without_prefix_has_same_identity(self):
        first = self.by_id("eth-log-provider-a")
        second = self.by_id("eth-log-provider-b")
        first["movement"]["transaction_id"] = first["movement"]["transaction_id"][2:]
        result = resolve_observations([first, second])
        self.assertEqual(len(result["events"]), 1)

    def test_missing_hash_and_locator_produce_candidate_not_merge(self):
        first = self.by_id("btc-vout-provider-a")
        second = copy.deepcopy(first)
        second["observation_id"] = "partial-no-identity"
        second["movement"]["transaction_id"] = None
        second["movement"].pop("event_locator")
        link = classify_observation_pair(first, second)
        self.assertEqual(link["match_class"], "CANDIDATE")
        self.assertEqual(resolve_observations([first, second])["events"][0]["observation_ids"], ["btc-vout-provider-a"])

    def test_distinct_transactions_without_event_groups_are_not_reported_as_candidates(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-second-vout")
        first["movement"].pop("event_locator")
        second["movement"].pop("event_locator")
        second["movement"]["transaction_id"] = "e" * 64
        result = resolve_observations([first, second])
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(result["events"], [])
        self.assertEqual(result["links"][0]["match_class"], "NO_MATCH")

    def test_missing_transaction_with_fewer_than_three_shared_fields_is_insufficient(self):
        first = self.by_id("btc-vout-provider-a")
        second = copy.deepcopy(first)
        second["observation_id"] = "too-few-shared-fields"
        second["movement"]["transaction_id"] = None
        second["movement"].pop("event_locator")
        second["movement"]["amount"] = "999"
        second["movement"]["from_address"] = "bc1qdifferent"
        second["movement"]["to_address"] = "bc1qother"
        second["event_time_utc"] = "2026-11-10T10:00:01Z"
        self.assertEqual(classify_observation_pair(first, second)["match_class"], "NO_MATCH")
        self.assertEqual(resolve_observations([first, second])["status"], "RESOLVED")

    def test_same_transaction_without_locator_remains_candidate(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-vout-provider-b")
        first["movement"].pop("event_locator")
        second["movement"].pop("event_locator")
        self.assertEqual(classify_observation_pair(first, second)["match_class"], "CANDIDATE")
        self.assertEqual(len(resolve_observations([first, second])["events"]), 0)

    def test_complementary_observations_resolve_missing_field_only_after_strong_identity(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-vout-provider-b")
        first["movement"]["amount"] = None
        result = resolve_observations([first, second])
        event = result["events"][0]
        self.assertEqual(event["resolved_fields"]["amount"], "1")
        self.assertNotIn("amount", event["missing_required_fields"])
        self.assertEqual(event["analytical_eligibility"], "ELIGIBLE")

    def test_event_locator_numeric_values_are_canonicalized(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-vout-provider-b")
        event = resolve_observations([first, second])["events"][0]
        self.assertEqual(event["resolved_fields"]["event_locator"], {"kind": "UTXO_VOUT", "value": "0"})

    def test_decimal_formatting_differences_are_not_conflicts(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-vout-provider-b")
        first["movement"]["amount"] = "1.0"
        second["movement"]["amount"] = "1.000000"
        event = resolve_observations([first, second])["events"][0]
        self.assertEqual(event["field_conflicts"], [])

    def test_large_decimal_precision_is_preserved_exactly(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["amount"] = "123456789012345678901234567890123456789.000"
        event = resolve_observations([observation])["events"][0]
        self.assertEqual(
            event["resolved_fields"]["amount"],
            "123456789012345678901234567890123456789",
        )
        self.assertEqual(event["analytical_eligibility"], "ELIGIBLE")

    def test_negative_amount_is_invalid_and_ineligible(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["amount"] = "-1"
        event = resolve_observations([observation])["events"][0]
        self.assertEqual(event["resolution_status"], "INVALID")
        self.assertIsNone(event["resolved_fields"]["amount"])
        self.assertEqual(event["analytical_eligibility"], "INELIGIBLE")

    def test_contract_log_index_is_rejected_for_native_eth_asset(self):
        observation = self.by_id("eth-log-provider-a")
        observation["movement"]["event_locator"] = {"kind": "EVM_LOG_INDEX", "value": "5"}
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "invalid event_locator for observation: eth-log-provider-a",
            result["errors"],
        )

    def test_invalid_event_locator_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["event_locator"] = {"kind": "EVM_LOG_INDEX", "value": "1"}
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "invalid event_locator for observation: btc-vout-provider-a",
            result["errors"],
        )

    def test_conflicting_amounts_are_preserved_and_block_eligibility(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-vout-provider-b")
        second["movement"]["amount"] = "2.0"
        event = resolve_observations([first, second])["events"][0]
        self.assertEqual(event["resolution_status"], "CONTRADICTORY")
        self.assertEqual(event["resolved_fields"]["amount"], None)
        self.assertIn("amount", event["field_conflicts"])
        self.assertEqual(event["analytical_eligibility"], "INELIGIBLE")
        self.assertEqual(len(event["field_evidence"]["amount"]), 2)

    def test_unconfirmed_transfer_is_not_analytically_eligible(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["confirmation_status"] = "UNKNOWN"
        event = resolve_observations([observation])["events"][0]
        self.assertEqual(event["resolution_status"], "COMPLETE")
        self.assertEqual(event["analytical_eligibility"], "INELIGIBLE")
        self.assertIn("CONFIRMATION_NOT_CONFIRMED", event["eligibility_reasons"])

    def test_missing_source_integrity_hash_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["source"]["payload_sha256"] = None
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "invalid source payload_sha256: btc-vout-provider-a",
            result["errors"],
        )

    def test_unknown_quality_status_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["quality"]["status"] = "UNRECOGNIZED"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "invalid quality status: btc-vout-provider-a",
            result["errors"],
        )

    def test_conflicting_origin_destination_and_event_time_are_reported_by_field(self):
        mutations = (
            ("from_address", lambda item: item["movement"].__setitem__("from_address", "bc1qother-source")),
            ("to_address", lambda item: item["movement"].__setitem__("to_address", "bc1qother-destination")),
            ("event_time_utc", lambda item: item.__setitem__("event_time_utc", "2026-11-10T10:00:01Z")),
        )
        for field, mutate in mutations:
            with self.subTest(field=field):
                first = self.by_id("btc-vout-provider-a")
                second = self.by_id("btc-vout-provider-b")
                mutate(second)
                event = resolve_observations([first, second])["events"][0]
                self.assertIn(field, event["field_conflicts"])
                self.assertEqual(event["analytical_eligibility"], "INELIGIBLE")

    def test_invalid_asset_network_combination_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["asset"]["asset_id"] = "ethereum:eth"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "invalid asset/network identity: btc-vout-provider-a",
            result["errors"],
        )

    def test_exact_provider_record_repeat_cannot_claim_distinct_event_identities(self):
        original = self.by_id("btc-vout-provider-a")
        repeated = copy.deepcopy(original)
        repeated["observation_id"] = "btc-same-record-different-event"
        repeated["movement"]["event_locator"]["value"] = "1"
        result = resolve_observations([original, repeated])
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["links"][0]["match_class"], "NO_MATCH")
        self.assertEqual(result["links"][0]["source_record_relation"], "EXACT_REPEAT")
        self.assertIn(
            "SOURCE_RECORD_REPEAT_CONTRADICTS_EVENT_IDENTITY",
            result["links"][0]["reasons"],
        )
        self.assertEqual(result["status"], "RESOLVED_WITH_RELATION_CONFLICTS")
        self.assertTrue(all(event["analytical_eligibility"] == "INELIGIBLE" for event in result["events"]))
        self.assertTrue(all(event["resolution_status"] == "CONTRADICTORY" for event in result["events"]))
        self.assertTrue(all(
            "CONTRADICTORY_EVENT_IDENTITY_RELATION" in event["eligibility_reasons"]
            for event in result["events"]
        ))

    def test_same_provider_record_with_changed_payload_is_a_revision_not_repeat(self):
        first = self.by_id("btc-vout-provider-a")
        revised = copy.deepcopy(first)
        revised["observation_id"] = "btc-vout-provider-a-revision"
        revised["source"]["payload_sha256"] = "f" * 64
        link = classify_observation_pair(first, revised)
        self.assertEqual(link["match_class"], "STRONG_MATCH")
        self.assertEqual(link["source_record_relation"], "SAME_RECORD_DIFFERENT_PAYLOAD")
        self.assertIn("SAME_PROVIDER_RECORD_WITH_CHANGED_PAYLOAD", link["reasons"])
        self.assertEqual(len(resolve_observations([first, revised])["events"]), 1)

    def test_missing_is_not_zero_and_remains_missing_without_support(self):
        first = self.by_id("btc-vout-provider-a")
        first["movement"]["amount"] = None
        event = resolve_observations([first])["events"][0]
        self.assertIsNone(event["resolved_fields"]["amount"])
        self.assertIn("amount", event["missing_required_fields"])
        self.assertNotEqual(event["resolved_fields"]["amount"], "0")

    def test_fragmented_transfers_are_separate_events(self):
        six_hundred = self.by_id("btc-vout-provider-a")
        four_hundred = self.by_id("btc-second-vout")
        six_hundred["movement"]["amount"] = "600"
        four_hundred["movement"]["amount"] = "400"
        result = resolve_observations([six_hundred, four_hundred])
        self.assertEqual(len(result["events"]), 2)
        self.assertTrue(all(event["analytical_eligibility"] == "ELIGIBLE" for event in result["events"]))

    def test_fan_in_and_fan_out_remain_individual_events(self):
        first = self.by_id("btc-vout-provider-a")
        second = self.by_id("btc-second-vout")
        second["movement"]["to_address"] = "bc1qother-destination"
        result = resolve_observations([first, second])
        self.assertEqual(len(result["events"]), 2)

    def test_unrelated_observations_do_not_create_exhaustive_no_match_links(self):
        observations = []
        for index in range(25):
            item = self.by_id("btc-vout-provider-a")
            item["observation_id"] = f"independent-{index:02d}"
            item["source"]["record_id"] = f"record-{index:02d}"
            item["source"]["payload_sha256"] = f"{index + 1:064x}"
            item["event_time_utc"] = f"2026-11-10T10:{index:02d}:00Z"
            item["movement"]["transaction_id"] = f"{index + 1:064x}"
            item["movement"]["amount"] = str(index + 1)
            item["movement"]["from_address"] = f"bc1qsource{index:02d}"
            item["movement"]["to_address"] = f"bc1qdestination{index:02d}"
            item["movement"]["event_locator"] = {"kind": "UTXO_VOUT", "value": "0"}
            observations.append(item)
        result = resolve_observations(observations)
        self.assertEqual(len(result["events"]), 25)
        self.assertEqual(result["links"], [])

    def test_order_independence_and_idempotence(self):
        observations = [self.by_id("btc-vout-provider-a"), self.by_id("btc-vout-provider-b"), self.by_id("btc-second-vout")]
        forward = resolve_observations(observations)
        reverse = resolve_observations(list(reversed(observations)))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward["decision_id"], reverse["decision_id"])
        self.assertEqual(forward["input_fingerprint"], reverse["input_fingerprint"])

    def test_correction_creates_new_decision_and_links_supersession(self):
        original = [self.by_id("btc-vout-provider-a")]
        first = resolve_observations(original)
        corrected = copy.deepcopy(original)
        corrected[0]["movement"]["amount"] = "1.25"
        second = resolve_observations(corrected, supersedes_decision_id=first["decision_id"])
        self.assertNotEqual(first["decision_id"], second["decision_id"])
        self.assertEqual(second["supersedes_decision_id"], first["decision_id"])
        self.assertEqual(first["events"][0]["resolved_fields"]["amount"], "1")
        self.assertEqual(second["events"][0]["resolved_fields"]["amount"], "1.25")

    def test_supersession_context_changes_decision_identity(self):
        observations = [self.by_id("btc-vout-provider-a")]
        base = resolve_observations(observations)
        first = resolve_observations(observations, supersedes_decision_id="decision-prior-a")
        repeated = resolve_observations(observations, supersedes_decision_id="decision-prior-a")
        other = resolve_observations(observations, supersedes_decision_id="decision-prior-b")
        self.assertEqual(first["input_fingerprint"], other["input_fingerprint"])
        self.assertEqual(first["decision_id"], repeated["decision_id"])
        self.assertNotEqual(first["decision_id"], other["decision_id"])
        self.assertNotEqual(base["decision_id"], first["decision_id"])

    def test_invalid_supersession_reference_fails_closed(self):
        result = resolve_observations(
            [self.by_id("btc-vout-provider-a")],
            supersedes_decision_id=" ",
        )
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "supersedes_decision_id must be null or a non-empty string",
            result["errors"],
        )

    def test_invalid_duplicate_input_fingerprint_is_order_independent(self):
        first = self.by_id("btc-vout-provider-a")
        second = copy.deepcopy(first)
        second["movement"]["amount"] = "2"
        forward = resolve_observations([first, second])
        reverse = resolve_observations([second, first])
        self.assertEqual(forward["input_fingerprint"], reverse["input_fingerprint"])
        self.assertEqual(forward["decision_id"], reverse["decision_id"])

    def test_duplicate_observation_ids_fail_closed(self):
        first = self.by_id("btc-vout-provider-a")
        duplicate = copy.deepcopy(first)
        result = resolve_observations([first, duplicate])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("duplicate observation_id: btc-vout-provider-a", result["errors"])
        self.assertEqual(result["events"], [])

    def test_aggregate_flow_metrics_are_rejected_as_transfer_evidence(self):
        metric = self.by_id("btc-vout-provider-a")
        metric["observation_type"] = "EXCHANGE_FLOW_METRIC"
        result = resolve_observations([metric])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("observation is not ON_CHAIN_TRANSACTION: btc-vout-provider-a", result["errors"])


    def test_delayed_observation_is_historical_evidence_not_a_realtime_assertion(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["quality"]["status"] = "DELAYED"
        event = resolve_observations([observation])["events"][0]
        self.assertEqual(event["analytical_eligibility"], "ELIGIBLE")
        self.assertEqual(
            event["field_evidence"]["amount"][0]["evidence"][0]["quality_status"],
            "DELAYED",
        )

    def test_duplicate_observation_is_excluded_from_event_evidence(self):
        original = self.by_id("btc-vout-provider-a")
        duplicate = copy.deepcopy(original)
        duplicate["observation_id"] = "btc-vout-provider-a-duplicate"
        duplicate["quality"] = {"status": "DUPLICATE", "duplicate_of": original["observation_id"]}
        result = resolve_observations([original, duplicate])
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(event["observation_ids"], [original["observation_id"]])
        self.assertEqual(event["excluded_observation_ids"], [duplicate["observation_id"]])
        self.assertEqual(event["analytical_eligibility"], "ELIGIBLE")
        self.assertEqual(
            event["field_evidence"]["amount"][0]["evidence"][0]["observation_id"],
            original["observation_id"],
        )

    def test_duplicate_observation_alone_cannot_create_an_event(self):
        duplicate = self.by_id("btc-vout-provider-a")
        duplicate["quality"] = {"status": "DUPLICATE", "duplicate_of": "not-in-input"}
        result = resolve_observations([duplicate])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["status"], "CANDIDATES_ONLY" if result["links"] else "INSUFFICIENT_EVIDENCE")

    def test_valid_and_delayed_sources_can_complement_historical_event(self):
        valid = self.by_id("btc-vout-provider-a")
        delayed = self.by_id("btc-vout-provider-b")
        delayed["quality"]["status"] = "DELAYED"
        valid["movement"]["amount"] = None
        event = resolve_observations([valid, delayed])["events"][0]
        self.assertEqual(event["resolved_fields"]["amount"], "1")
        self.assertEqual(event["analytical_eligibility"], "ELIGIBLE")
        self.assertEqual(
            {entry["quality_status"] for entry in event["field_evidence"]["from_address"][0]["evidence"]},
            {"VALID", "DELAYED"},
        )

    def test_noncanonical_decimal_amount_is_invalid_and_ineligible(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["amount"] = "1e3"
        event = resolve_observations([observation])["events"][0]
        self.assertEqual(event["resolution_status"], "INVALID")
        self.assertIsNone(event["resolved_fields"]["amount"])
        self.assertEqual(event["analytical_eligibility"], "INELIGIBLE")

    def test_invalid_decimal_does_not_count_toward_candidate_threshold(self):
        first = self.by_id("btc-vout-provider-a")
        second = copy.deepcopy(first)
        second["observation_id"] = "partial-invalid-decimal"
        first["movement"]["transaction_id"] = None
        second["movement"]["transaction_id"] = None
        first["movement"].pop("event_locator")
        second["movement"].pop("event_locator")
        first["movement"]["amount"] = "1e3"
        second["movement"]["amount"] = "1e3"
        second["movement"]["from_address"] = "bc1qdifferent-source"
        second["movement"]["to_address"] = "bc1qdifferent-destination"
        second["event_time_utc"] = "2026-11-10T11:00:00Z"
        result = resolve_observations([first, second])
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["links"][0]["match_class"], "NO_MATCH")
        self.assertIn("INSUFFICIENT_SHARED_EVIDENCE", result["links"][0]["reasons"])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")

    def test_asset_symbol_mismatch_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["asset"]["symbol"] = "ETH"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("invalid asset symbol for network: btc-vout-provider-a", result["errors"])

    def test_transfer_unit_mismatch_fails_closed(self):
        observation = self.by_id("btc-vout-provider-a")
        observation["movement"]["unit"] = "ETH"
        result = resolve_observations([observation])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("invalid movement unit for asset: btc-vout-provider-a", result["errors"])


if __name__ == "__main__":
    unittest.main()
