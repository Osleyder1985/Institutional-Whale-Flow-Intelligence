import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from iwfi.execution_participant_roles import (
    resolve_execution_participants,
    validate_execution_participant_roles,
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


class ExecutionParticipantRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((FIXTURES / "execution-participant-role-claims.json").read_text(encoding="utf-8"))
        cls.trades = json.loads((FIXTURES / "execution-participant-role-trades.json").read_text(encoding="utf-8"))
        cls.actors = json.loads((FIXTURES / "execution-participant-role-actors.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT.parent / "schemas" / "execution-participant-role-claim.schema.json").read_text(encoding="utf-8"))
        cls.actor_ids = [item["actor_id"] for item in cls.actors["actors"]]
        cls.observation_ids = [
            "obs-eth-buyer", "obs-eth-broker", "obs-eth-venue",
            "obs-eth-custodian", "obs-eth-fund", "obs-eth-manager",
            "obs-eth-beneficial-owner-unknown",
        ]

    def test_schema_and_fixtures_validate(self):
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(self.registry)), [])
        self.assertEqual(
            validate_execution_participant_roles(self.registry, self.trades, self.actor_ids, self.observation_ids),
            [],
        )

    def test_multiple_distinct_roles_coexist_for_one_execution(self):
        result = resolve_execution_participants(
            self.registry, self.trades[1], "2026-02-11T12:30:00Z"
        )
        self.assertEqual(result["status"], "RESOLVED")
        by_role = {item["participant_role"]: item for item in result["participants"]}
        self.assertEqual(by_role["BUYER"]["actor_id"], "synthetic-eth-buyer-a")
        self.assertEqual(by_role["BROKER"]["actor_id"], "synthetic-eth-broker")
        self.assertEqual(by_role["EXECUTING_VENUE"]["actor_id"], "synthetic-eth-venue")
        self.assertEqual(by_role["CUSTODIAN"]["actor_id"], "synthetic-eth-custodian")
        self.assertEqual(by_role["FUND"]["actor_id"], "synthetic-eth-fund")
        self.assertEqual(by_role["ASSET_MANAGER"]["actor_id"], "synthetic-eth-manager")

    def test_custodian_does_not_imply_beneficial_owner(self):
        result = resolve_execution_participants(
            self.registry, self.trades[1], "2026-02-11T12:30:00Z"
        )
        by_role = {item["participant_role"]: item for item in result["participants"]}
        self.assertEqual(by_role["CUSTODIAN"]["status"], "DIRECT")
        self.assertEqual(by_role["BENEFICIAL_OWNER"]["status"], "UNKNOWN")
        self.assertIsNone(by_role["BENEFICIAL_OWNER"]["actor_id"])

    def test_fund_and_asset_manager_remain_separate_actors(self):
        result = resolve_execution_participants(
            self.registry, self.trades[1], "2026-02-11T12:30:00Z"
        )
        by_role = {item["participant_role"]: item for item in result["participants"]}
        self.assertNotEqual(by_role["FUND"]["actor_id"], by_role["ASSET_MANAGER"]["actor_id"])

    def test_aggressor_side_alone_does_not_create_participant_claim(self):
        result = resolve_execution_participants(
            self.registry, self.trades[0], "2026-01-10T10:00:10Z"
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["participants"], [])

    def test_conflicting_actors_for_same_role_resolve_to_disputed(self):
        registry = copy.deepcopy(self.registry)
        conflict = copy.deepcopy(registry["claims"][0])
        conflict["claim_id"] = "claim-eth-buyer-conflict"
        conflict["actor_id"] = "synthetic-eth-buyer-b"
        conflict["source_observation_ids"] = ["obs-eth-buyer-conflict"]
        conflict["supporting_evidence"][0]["observation_id"] = "obs-eth-buyer-conflict"
        conflict["supporting_evidence"][0]["record_ref"] = "synthetic:buyer-conflict"
        registry["claims"].append(conflict)
        result = resolve_execution_participants(
            registry, self.trades[1], "2026-02-11T12:30:00Z"
        )
        buyer = next(item for item in result["participants"] if item["participant_role"] == "BUYER")
        self.assertEqual(buyer["status"], "DISPUTED")
        self.assertIsNone(buyer["actor_id"])

    def test_claim_known_after_cutoff_is_not_visible(self):
        result = resolve_execution_participants(
            self.registry, self.trades[1], "2026-02-11T11:59:59Z"
        )
        self.assertEqual(result["participants"], [])

    def test_unknown_actor_is_not_promoted_from_aggressor_side(self):
        registry = copy.deepcopy(self.registry)
        claim = registry["claims"][-1]
        self.assertEqual(claim["epistemic_status"], "UNKNOWN")
        self.assertIsNone(claim["actor_id"])
        self.assertEqual(claim["participant_role"], "BENEFICIAL_OWNER")
        self.assertEqual(claim["participant_side"], "UNKNOWN")

    def test_missing_source_observation_reference_is_rejected(self):
        errors = validate_execution_participant_roles(
            self.registry, self.trades, self.actor_ids, self.observation_ids[:-1]
        )
        self.assertTrue(any("source observation not found" in item for item in errors))

    def test_transfer_id_cannot_be_used_as_trade_reference(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["trade_id"] = "synthetic-movement-transfer-001"
        errors = validate_execution_participant_roles(
            registry, self.trades, self.actor_ids, self.observation_ids
        )
        self.assertTrue(any("trade not found" in item for item in errors))

    def test_role_and_side_mismatch_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["participant_side"] = "SELL"
        errors = validate_execution_participant_roles(
            registry, self.trades, self.actor_ids, self.observation_ids
        )
        self.assertTrue(any("incompatible" in item for item in errors))

    def test_malformed_temporal_claim_causes_resolver_abstention(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["known_at_utc"] = "not-a-time"
        result = resolve_execution_participants(
            registry, self.trades[1], "2026-02-11T12:30:00Z"
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])


    def test_unknown_buyer_identity_can_preserve_buyer_side_without_naming_actor(self):
        registry = {"contract_version": "1.1.0", "claims": [{
            "contract_version": "1.1.0",
            "claim_id": "claim-btc-buyer-identity-unknown",
            "trade_id": "synthetic-btc-trade-aggressor-only",
            "actor_id": None,
            "candidate_actor_ids": [],
            "participant_role": "BUYER",
            "participant_side": "BUY",
            "epistemic_status": "UNKNOWN",
            "attribution_method": "NONE",
            "recorded_at_utc": "2026-01-10T10:00:05Z",
            "known_at_utc": "2026-01-10T10:00:04Z",
            "valid_from_utc": None,
            "valid_to_utc": None,
            "source_observation_ids": [],
            "supporting_evidence": [],
            "counter_evidence": []
        }]}
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(registry)), [])
        errors = validate_execution_participant_roles(
            registry, self.trades, self.actor_ids, self.observation_ids
        )
        self.assertEqual(errors, [])
        result = resolve_execution_participants(
            registry, self.trades[0], "2026-01-10T10:00:10Z"
        )
        buyer = result["participants"][0]
        self.assertEqual(buyer["participant_role"], "BUYER")
        self.assertEqual(buyer["participant_side"], "BUY")
        self.assertEqual(buyer["status"], "UNKNOWN")
        self.assertIsNone(buyer["actor_id"])


if __name__ == "__main__":
    unittest.main()
