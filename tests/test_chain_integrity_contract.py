"""Schema and invariant tests for the proposed chain-integrity evidence contract."""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent


class ChainIntegrityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT.parent / "schemas" / "chain-integrity-observation.schema.json").read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())
        cls.scenarios = json.loads((ROOT / "fixtures" / "chain-integrity-scenarios.json").read_text(encoding="utf-8"))

    def test_scenarios_have_unique_ids_and_supported_assessments(self):
        ids = [item["scenario_id"] for item in self.scenarios]
        self.assertEqual(len(ids), len(set(ids)))
        allowed = {"OBSERVED", "INCLUDED", "CANONICALITY_UNRESOLVED", "NOT_CANONICAL", "REOBSERVED", "FINALIZED", "UNKNOWN"}
        for scenario in self.scenarios:
            self.assertIn(scenario["expected_assessment"], allowed)

    def test_all_fixture_observations_validate(self):
        for scenario in self.scenarios:
            for index, observation in enumerate(scenario["observations"]):
                record = {
                    "observation_id": scenario["scenario_id"] + "-" + str(index),
                    "network_id": scenario["network_id"],
                    "source": {"kind": "SELF_HOSTED_NODE", "source_id": "fixture-node", "method": "synthetic-fixture"},
                    "transaction_id": observation["transaction_id"],
                    "observation_kind": observation["observation_kind"],
                    "observed_at_utc": "2026-11-13T12:00:00Z",
                    "inclusion": observation.get("inclusion"),
                    "source_asserted_chain_status": observation.get("source_asserted_chain_status"),
                    "source_asserted_head_tag": observation.get("source_asserted_head_tag"),
                    "event_locator": None,
                    "evidence_reference": "synthetic-fixture",
                }
                self.assertEqual(list(self.validator.iter_errors(record)), [], scenario["scenario_id"])

    def test_mempool_observation_cannot_claim_inclusion(self):
        record = {"observation_id": "m", "network_id": "bitcoin-mainnet", "source": {"kind": "SELF_HOSTED_NODE", "source_id": "n", "method": "getmempoolentry"}, "transaction_id": "a" * 64, "observation_kind": "MEMPOOL_SEEN", "observed_at_utc": "2026-11-13T12:00:00Z", "inclusion": {"block_height": 1, "block_hash": "b" * 64}}
        self.assertTrue(list(self.validator.iter_errors(record)))

    def test_block_inclusion_requires_block_identity(self):
        record = {"observation_id": "i", "network_id": "bitcoin-mainnet", "source": {"kind": "SELF_HOSTED_NODE", "source_id": "n", "method": "getblock"}, "transaction_id": "a" * 64, "observation_kind": "BLOCK_INCLUDED", "observed_at_utc": "2026-11-13T12:00:00Z"}
        self.assertTrue(list(self.validator.iter_errors(record)))

    def test_network_specific_transaction_hash_formats(self):
        record = {"observation_id": "e", "network_id": "eip155:1", "source": {"kind": "THIRD_PARTY_PROVIDER", "source_id": "p", "method": "receipt"}, "transaction_id": "a" * 64, "observation_kind": "MEMPOOL_SEEN", "observed_at_utc": "2026-11-13T12:00:00Z", "inclusion": None}
        self.assertTrue(list(self.validator.iter_errors(record)))

    def test_conflicting_views_remain_unresolved_in_fixture(self):
        scenario = next(x for x in self.scenarios if x["scenario_id"] == "eth_provider_conflict")
        self.assertEqual(scenario["expected_assessment"], "CANONICALITY_UNRESOLVED")
        hashes = {x["inclusion"]["block_hash"] for x in scenario["observations"]}
        self.assertEqual(len(hashes), 2)

    def test_reinclusion_is_a_new_inclusion_observation(self):
        scenario = next(x for x in self.scenarios if x["scenario_id"] == "btc_reincluded_new_block")
        self.assertEqual(scenario["expected_inclusion_count"], 2)
        self.assertEqual(len({x["inclusion"]["block_hash"] for x in scenario["observations"]}), 2)
        self.assertEqual(len({x["transaction_id"] for x in scenario["observations"]}), 1)

    def test_bitcoin_fixture_never_claims_protocol_finality(self):
        for scenario in self.scenarios:
            if scenario["network_id"] == "bitcoin-mainnet":
                self.assertNotEqual(scenario["expected_assessment"], "FINALIZED")

    def test_bitcoin_schema_rejects_finality_checkpoint(self):
        record = {"observation_id": "b", "network_id": "bitcoin-mainnet", "source": {"kind": "SELF_HOSTED_NODE", "source_id": "n", "method": "getblock"}, "transaction_id": "a" * 64, "observation_kind": "FINALITY_CHECKPOINT", "observed_at_utc": "2026-11-13T12:00:00Z", "inclusion": {"block_height": 1, "block_hash": "b" * 64}, "source_asserted_head_tag": "finalized"}
        self.assertTrue(list(self.validator.iter_errors(record)))

    def test_eth_finalized_assessment_requires_finalized_tag_evidence(self):
        scenario = next(x for x in self.scenarios if x["expected_assessment"] == "FINALIZED")
        checkpoint = next(x for x in scenario["observations"] if x["observation_kind"] == "FINALITY_CHECKPOINT")
        inclusion = next(x for x in scenario["observations"] if x["observation_kind"] == "BLOCK_INCLUDED")
        self.assertEqual(checkpoint.get("source_asserted_head_tag"), "finalized")
        self.assertGreaterEqual(checkpoint["inclusion"]["block_height"], inclusion["inclusion"]["block_height"])


if __name__ == "__main__":
    unittest.main()
