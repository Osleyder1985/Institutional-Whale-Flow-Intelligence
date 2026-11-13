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


    def _record(self, observation_id, kind, tx="a" * 64, height=100, block="b" * 64, status="UNKNOWN", network="bitcoin-mainnet", source="node-a", tag=None):
        return {
            "observation_id": observation_id,
            "network_id": network,
            "transaction_id": tx if network == "bitcoin-mainnet" else "0x" + tx[-64:],
            "source": {"kind": "SELF_HOSTED_NODE", "source_id": source, "method": "fixture"},
            "observation_kind": kind,
            "observed_at_utc": "2026-11-13T12:00:00Z",
            "inclusion": None if kind == "MEMPOOL_SEEN" else {"block_height": height, "block_hash": block if network == "bitcoin-mainnet" else "0x" + block[-64:], "transaction_index": 0},
            "source_asserted_chain_status": status,
            "source_asserted_head_tag": tag,
        }

    def test_assessment_is_deterministic_and_input_order_invariant(self):
        from iwfi.chain_integrity import assess_chain_observations
        records = [self._record("a", "BLOCK_INCLUDED"), self._record("b", "BLOCK_STATUS", status="ACTIVE")]
        self.assertEqual(assess_chain_observations(records), assess_chain_observations(list(reversed(records))))

    def test_assessment_is_idempotent_for_identical_evidence(self):
        from iwfi.chain_integrity import assess_chain_observations
        records = [self._record("a", "BLOCK_INCLUDED")]
        self.assertEqual(assess_chain_observations(records), assess_chain_observations(records))

    def test_mempool_only_is_observed_not_included(self):
        from iwfi.chain_integrity import assess_chain_observations
        result = assess_chain_observations([self._record("a", "MEMPOOL_SEEN")])
        self.assertEqual(result["status"], "OBSERVED")

    def test_positive_non_active_block_evidence_marks_that_inclusion_noncanonical(self):
        from iwfi.chain_integrity import assess_chain_observations
        result = assess_chain_observations([self._record("a", "BLOCK_INCLUDED", status="NOT_ACTIVE")])
        self.assertEqual(result["status"], "NOT_CANONICAL")

    def test_old_non_active_then_new_active_inclusion_is_reobserved(self):
        from iwfi.chain_integrity import assess_chain_observations
        old = self._record("old", "BLOCK_INCLUDED", block="b" * 64, status="NOT_ACTIVE")
        new = self._record("new", "BLOCK_INCLUDED", block="c" * 64, status="ACTIVE")
        new["observed_at_utc"] = "2026-11-13T12:01:00Z"
        records = [old, new]
        self.assertEqual(assess_chain_observations(records)["status"], "REOBSERVED")

    def test_conflicting_sources_for_same_block_remain_unresolved(self):
        from iwfi.chain_integrity import assess_chain_observations
        records = [
            self._record("a", "BLOCK_INCLUDED", status="ACTIVE", source="node-a"),
            self._record("b", "BLOCK_STATUS", status="NOT_ACTIVE", source="node-b"),
        ]
        self.assertEqual(assess_chain_observations(records)["status"], "CANONICALITY_UNRESOLVED")

    def test_eth_finalized_requires_same_source_checkpoint_covering_block(self):
        from iwfi.chain_integrity import assess_chain_observations
        tx = "a" * 64
        inclusion = self._record("included", "BLOCK_INCLUDED", tx=tx, network="eip155:1", height=100, block="b" * 64, status="ACTIVE", source="eth-node")
        checkpoint = self._record("checkpoint", "FINALITY_CHECKPOINT", tx=tx, network="eip155:1", height=101, block="c" * 64, source="eth-node", tag="finalized")
        self.assertEqual(assess_chain_observations([inclusion, checkpoint])["status"], "FINALIZED")
        checkpoint["inclusion"]["block_height"] = 99
        self.assertEqual(assess_chain_observations([inclusion, checkpoint])["status"], "INCLUDED")

    def test_bitcoin_never_receives_finalized_assessment(self):
        from iwfi.chain_integrity import assess_chain_observations
        records = [self._record("a", "BLOCK_INCLUDED", status="ACTIVE")]
        records.append(self._record("f", "FINALITY_CHECKPOINT", tag="finalized"))
        self.assertNotEqual(assess_chain_observations(records)["status"], "FINALIZED")

    def test_invalid_mixed_transaction_evidence_is_rejected(self):
        from iwfi.chain_integrity import assess_chain_observations
        records = [self._record("a", "BLOCK_INCLUDED"), self._record("b", "BLOCK_INCLUDED", tx="d" * 64)]
        with self.assertRaises(ValueError):
            assess_chain_observations(records)

    def test_assessment_does_not_mutate_observations(self):
        from copy import deepcopy
        from iwfi.chain_integrity import assess_chain_observations
        records = [self._record("a", "BLOCK_INCLUDED")]
        before = deepcopy(records)
        assess_chain_observations(records)
        self.assertEqual(records, before)


if __name__ == "__main__":
    unittest.main()
