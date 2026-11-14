import json
import unittest
from pathlib import Path

from iwfi.execution_attribution import (
    resolve_execution_participant,
    validate_execution_attributions,
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"

def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

class IntegratedActivityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observations = load("source-observations.json")
        cls.claims = load("entity-attribution-claims.json")
        cls.movements = load("movement-ledger.json")
        cls.executions = load("trade-executions.json")
        cls.actors = load("actor-registry.json")
        cls.execution_attributions = load("execution-participant-attributions.json")

    def test_exchange_inflow_remains_aggregate_measurement_not_movement_or_trade(self):
        flow = next(x for x in self.observations if x["observation_id"] == "fixture-exchange-inflow")
        self.assertEqual(flow["observation_type"], "EXCHANGE_FLOW_METRIC")
        self.assertIsNone(flow["movement"])
        self.assertNotIn("event_type", flow)
        self.assertNotIn("execution_id", flow)

    def test_movement_ledger_contains_transfers_only(self):
        for movement in self.movements:
            self.assertEqual(movement["transfer"]["movement_type"], "TRANSFER")
            self.assertNotIn("aggressor_side", movement)
            self.assertNotIn("participant_side", movement)
            self.assertNotIn("execution_id", movement)

    def test_trade_execution_records_are_individual_execution_evidence_only(self):
        for execution in self.executions:
            self.assertEqual(execution["event_type"], "TRADE_EXECUTION")
            self.assertEqual(execution["aggregation_level"], "INDIVIDUAL_EXECUTION")
            for evidence in execution["source_evidence"]:
                self.assertIn(evidence["evidence_type"], {
                    "VENUE_EXECUTION_RECORD",
                    "OFFICIAL_EXECUTION_DISCLOSURE",
                })
                self.assertEqual(evidence["granularity"], "INDIVIDUAL_EXECUTION")

    def test_confirmed_btc_trade_does_not_name_a_buyer_from_aggressor_side(self):
        execution = next(x for x in self.executions if x["asset_base"] == "BTC")
        self.assertEqual(execution["execution_status"], "EXECUTED")
        self.assertEqual(execution["aggressor_side"], "BUY")
        self.assertEqual(execution["participant_attribution_status"], "UNKNOWN")
        self.assertEqual(execution["participant_side"], "UNKNOWN")
        self.assertIsNone(execution["participant_actor_id"])
        result = resolve_execution_participant(
            {"contract_version": "1.0.0", "claims": []},
            execution,
            "2026-01-10T10:00:10Z",
        )
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["actor_id"])

    def test_eth_named_participant_requires_resolvable_execution_claim_and_actor(self):
        execution = next(x for x in self.executions if x["asset_base"] == "ETH")
        actor_ids = [x["actor_id"] for x in self.actors["actors"]]
        observation_ids = ["exec-evidence-eth"]
        self.assertEqual(
            validate_execution_attributions(
                self.execution_attributions,
                self.executions,
                actor_ids,
                observation_ids,
            ),
            [],
        )
        claim = self.execution_attributions["claims"][0]
        self.assertIn(claim["attribution_id"], execution["attribution_claim_ids"])
        result = resolve_execution_participant(
            self.execution_attributions,
            execution,
            "2026-02-11T12:00:00Z",
        )
        self.assertEqual(result["status"], "DIRECT")
        self.assertEqual(result["actor_id"], execution["participant_actor_id"])
        self.assertEqual(result["participant_side"], execution["participant_side"])

    def test_execution_identity_and_movement_identity_are_not_interchangeable(self):
        execution_ids = {x["execution_id"] for x in self.executions}
        movement_ids = {x["movement_id"] for x in self.movements}
        self.assertTrue(execution_ids.isdisjoint(movement_ids))

    def test_provider_label_is_not_promoted_to_verified_actor_identity(self):
        provider_claim = next(x for x in self.claims if x["claim_id"] == "claim-provider-label-001")
        self.assertEqual(provider_claim["epistemic_status"], "PROVIDER_LABELLED")
        self.assertEqual(provider_claim["predicate"], "LABELLED_AS")
        self.assertEqual(provider_claim["object"]["object_id"], "exchange")
        self.assertNotEqual(provider_claim["epistemic_status"], "VERIFIED")

    def test_conflicting_address_claims_remain_disputed(self):
        claim = next(x for x in self.claims if x["claim_id"] == "claim-conflict-003")
        self.assertEqual(claim["epistemic_status"], "DISPUTED")
        self.assertTrue(claim["counter_evidence"])
        self.assertNotEqual(claim["epistemic_status"], "VERIFIED")

if __name__ == "__main__":
    unittest.main()
