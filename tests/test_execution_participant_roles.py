import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from iwfi.execution_participant_roles import (
    resolve_execution_participants,
    validate_execution_participant_role_links,
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
        cls.trade_v11 = json.loads((FIXTURES / "trade-execution-v1.1.json").read_text(encoding="utf-8"))
        cls.trade_v11_btc = json.loads((FIXTURES / "trade-execution-btc-v1.1.json").read_text(encoding="utf-8"))
        cls.trade_v11_schema = json.loads((ROOT.parent / "schemas" / "trade-execution-v1.1.schema.json").read_text(encoding="utf-8"))
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
            self.registry, self.trade_v11, "2026-02-11T12:30:00Z", self.actor_ids, self.observation_ids
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
            self.registry, self.trade_v11, "2026-02-11T12:30:00Z", self.actor_ids, self.observation_ids
        )
        by_role = {item["participant_role"]: item for item in result["participants"]}
        self.assertEqual(by_role["CUSTODIAN"]["status"], "DIRECT")
        self.assertEqual(by_role["BENEFICIAL_OWNER"]["status"], "UNKNOWN")
        self.assertIsNone(by_role["BENEFICIAL_OWNER"]["actor_id"])

    def test_fund_and_asset_manager_remain_separate_actors(self):
        result = resolve_execution_participants(
            self.registry, self.trade_v11, "2026-02-11T12:30:00Z", self.actor_ids, self.observation_ids
        )
        by_role = {item["participant_role"]: item for item in result["participants"]}
        self.assertNotEqual(by_role["FUND"]["actor_id"], by_role["ASSET_MANAGER"]["actor_id"])

    def test_aggressor_side_alone_does_not_create_participant_claim(self):
        result = resolve_execution_participants(
            self.registry, self.trade_v11_btc, "2026-01-10T10:00:10Z", self.actor_ids, self.observation_ids
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
        execution = copy.deepcopy(self.trade_v11)
        execution["participant_role_claim_ids"].append("claim-eth-buyer-conflict")
        result = resolve_execution_participants(
            registry, execution, "2026-02-11T12:30:00Z", self.actor_ids, self.observation_ids + ["obs-eth-buyer-conflict"]
        )
        buyer = next(item for item in result["participants"] if item["participant_role"] == "BUYER")
        self.assertEqual(buyer["status"], "DISPUTED")
        self.assertIsNone(buyer["actor_id"])

    def test_claim_known_after_cutoff_is_not_visible(self):
        result = resolve_execution_participants(
            self.registry, self.trade_v11, "2026-02-11T11:59:59Z", self.actor_ids, self.observation_ids
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
        registry["claims"][0]["execution_id"] = "synthetic-movement-transfer-001"
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
            registry, self.trade_v11, "2026-02-11T12:30:00Z", self.actor_ids, self.observation_ids
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])


    def test_unknown_buyer_identity_can_preserve_buyer_side_without_naming_actor(self):
        registry = {"contract_version": "1.1.0", "claims": [{
            "contract_version": "1.1.0",
            "claim_id": "claim-btc-buyer-identity-unknown",
            "execution_id": "synthetic-btc-trade-aggressor-only",
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
        execution = copy.deepcopy(self.trade_v11_btc)
        execution["participant_role_claim_ids"] = ["claim-btc-buyer-identity-unknown"]
        result = resolve_execution_participants(
            registry, execution, "2026-01-10T10:00:10Z", self.actor_ids, self.observation_ids
        )
        buyer = result["participants"][0]
        self.assertEqual(buyer["participant_role"], "BUYER")
        self.assertEqual(buyer["participant_side"], "BUY")
        self.assertEqual(buyer["status"], "UNKNOWN")
        self.assertIsNone(buyer["actor_id"])


    def test_recorded_after_cutoff_is_not_visible_even_if_known_at_is_earlier(self):
        result = resolve_execution_participants(
            self.registry, self.trade_v11, "2026-02-11T12:00:01Z",
            self.actor_ids, self.observation_ids
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["participants"], [])

    def test_invalid_actor_reference_causes_resolver_abstention(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["actor_id"] = "actor-not-in-registry"
        result = resolve_execution_participants(
            registry, self.trade_v11, "2026-02-11T12:30:00Z",
            self.actor_ids, self.observation_ids
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])

    def test_invalid_evidence_observation_causes_resolver_abstention(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["source_observation_ids"] = ["observation-not-in-ledger"]
        registry["claims"][0]["supporting_evidence"][0]["observation_id"] = "observation-not-in-ledger"
        result = resolve_execution_participants(
            registry, self.trade_v11, "2026-02-11T12:30:00Z",
            self.actor_ids, self.observation_ids
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])

    def test_unknown_identity_does_not_conflict_with_same_known_role_side(self):
        registry = copy.deepcopy(self.registry)
        unknown_buyer = {
            "contract_version": "1.1.0",
            "claim_id": "claim-eth-buyer-identity-unknown",
            "execution_id": "synthetic-eth-trade-multi-role",
            "actor_id": None,
            "candidate_actor_ids": [],
            "participant_role": "BUYER",
            "participant_side": "BUY",
            "epistemic_status": "UNKNOWN",
            "attribution_method": "NONE",
            "recorded_at_utc": "2026-02-11T12:00:03Z",
            "known_at_utc": "2026-02-11T12:00:00Z",
            "valid_from_utc": None,
            "valid_to_utc": None,
            "source_observation_ids": [],
            "supporting_evidence": [],
            "counter_evidence": []
        }
        registry["claims"].append(unknown_buyer)
        result = resolve_execution_participants(
            registry, self.trade_v11, "2026-02-11T12:30:00Z",
            self.actor_ids, self.observation_ids
        )
        buyer = next(item for item in result["participants"] if item["participant_role"] == "BUYER")
        self.assertEqual(buyer["status"], "DIRECT")
        self.assertEqual(buyer["actor_id"], "synthetic-eth-buyer-a")
        self.assertEqual(buyer["participant_side"], "BUY")


    def test_resolver_rejects_invalid_attribution_method(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["attribution_method"] = "NONE"
        result = resolve_execution_participants(
            registry, self.trade_v11, "2026-02-11T12:30:00Z",
            self.actor_ids, self.observation_ids
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])

    def test_resolver_rejects_malformed_evidence_record(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["supporting_evidence"][0]["record_ref"] = "   "
        result = resolve_execution_participants(
            registry, self.trade_v11, "2026-02-11T12:30:00Z",
            self.actor_ids, self.observation_ids
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])

    def test_schema_rejects_whitespace_only_actor_identifier(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["actor_id"] = "   "
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        self.assertTrue(list(validator.iter_errors(registry)))


    def test_trade_execution_v11_schema_and_role_claim_links_validate(self):
        Draft202012Validator.check_schema(self.trade_v11_schema)
        validator = Draft202012Validator(self.trade_v11_schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(self.trade_v11)), [])
        self.assertEqual(
            validate_execution_participant_role_links(
                self.trade_v11, self.registry, self.actor_ids, self.observation_ids
            ),
            []
        )

    def test_trade_execution_v11_rejects_missing_role_claim_reference(self):
        execution = copy.deepcopy(self.trade_v11)
        execution["participant_role_claim_ids"].pop()
        errors = validate_execution_participant_role_links(
            execution, self.registry, self.actor_ids, self.observation_ids
        )
        self.assertTrue(any("references incomplete" in item for item in errors))

    def test_trade_execution_v11_rejects_legacy_singular_attribution(self):
        execution = copy.deepcopy(self.trade_v11)
        execution["participant_actor_id"] = "synthetic-eth-buyer-a"
        errors = validate_execution_participant_role_links(
            execution, self.registry, self.actor_ids, self.observation_ids
        )
        self.assertTrue(any("legacy singular attribution" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
