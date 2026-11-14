"""Contract tests for evidence-gated entity flow aggregation."""
import unittest

from iwfi.entity_flow_analytics import aggregate_entity_flows


START = "2026-11-01T00:00:00Z"
END = "2026-11-03T00:00:00Z"
CUTOFF = "2026-11-03T00:00:00Z"
EVENT = "2026-11-02T12:00:00Z"


def claim(claim_id, address, entity, *, network="bitcoin-mainnet",
          predicate="CONTROLLED_BY", epistemic="VERIFIED",
          review_status="REVIEWED", valid_from="2026-01-01T00:00:00Z",
          valid_to="2026-12-31T23:59:59Z", recorded="2026-11-01T00:00:00Z",
          counter=None):
    return {
        "contract_version": "1.0.0",
        "claim_id": claim_id,
        "subject": {"subject_type": "ADDRESS", "subject_id": address, "network_id": network},
        "predicate": predicate,
        "object": {"object_type": "ENTITY", "object_id": entity, "network_id": None},
        "epistemic_status": epistemic,
        "claim_source": {"provider": "test-source", "endpoint": "reviewed-claims",
                         "record_id": claim_id, "observation_ids": []},
        "supporting_evidence": [{"evidence_type": "OFFICIAL_PUBLICATION",
                                 "evidence_ref": "public-record:" + claim_id,
                                 "source": "test-source", "observation_id": None}],
        "counter_evidence": counter or [],
        "recorded_at_utc": recorded,
        "valid_from_utc": valid_from,
        "valid_to_utc": valid_to,
        "supersedes_claim_id": None,
        "review_status": review_status,
        "rationale": "Test-only evidence contract.",
        "review": {"reviewer_id": "test-reviewer", "reviewed_at_utc": recorded},
    }


def movement(movement_id, source, target, amount="2.5"):
    return {
        "contract_version": "1.0.0",
        "movement_id": movement_id,
        "asset": {"asset_id": "bitcoin:btc", "symbol": "BTC",
                  "network_id": "bitcoin-mainnet"},
        "event_time_utc": EVENT,
        "recorded_at_utc": "2026-11-02T12:00:05Z",
        "transfer": {"movement_type": "TRANSFER", "amount": amount, "unit": "BTC",
                     "from_address": source, "to_address": target,
                     "transaction_id": "a" * 64, "confirmation_status": "CONFIRMED",
                     "event_locator": {"kind": "UTXO_VOUT", "value": "0"}},
        "source_observation_ids": ["test-observation-" + movement_id],
        "attribution_resolutions": [],
        "quality_status": "VALID",
        "limitations": [],
    }


def run_aggregation(movements, claims):
    return aggregate_entity_flows(movements, claims, START, END, CUTOFF)


class EntityFlowAnalyticsTests(unittest.TestCase):
    def test_same_entity_transfer_is_internal_and_not_external_flow(self):
        claims = [
            claim("claim-a", "bc1qsource", "entity-1"),
            claim("claim-b", "bc1qtarget", "entity-1"),
        ]
        result = run_aggregation([movement("move-1", "bc1qsource", "bc1qtarget")], claims)
        entity = result["entities"][0]
        self.assertEqual(entity["entity_id"], "entity-1")
        self.assertEqual(entity["external_net"], 0)
        self.assertEqual(entity["external_incoming"], 0)
        self.assertEqual(entity["external_outgoing"], 0)
        self.assertEqual(entity["internal_transfer_volume"], 2.5)
        self.assertEqual(entity["internal_transfer_count"], 1)

    def test_transfer_between_entities_counts_once_for_each_entity_side(self):
        claims = [
            claim("claim-a", "bc1qsource", "entity-a"),
            claim("claim-b", "bc1qtarget", "entity-b"),
        ]
        result = run_aggregation([movement("move-1", "bc1qsource", "bc1qtarget")], claims)
        by_id = {row["entity_id"]: row for row in result["entities"]}
        self.assertEqual(by_id["entity-a"]["external_net"], -2.5)
        self.assertEqual(by_id["entity-b"]["external_net"], 2.5)
        self.assertEqual(by_id["entity-a"]["external_outgoing_count"], 1)
        self.assertEqual(by_id["entity-b"]["external_incoming_count"], 1)

    def test_unattributed_counterparty_is_not_guessed(self):
        claims = [claim("claim-a", "bc1qsource", "entity-a")]
        result = run_aggregation([movement("move-1", "bc1qsource", "bc1qunknown")], claims)
        entity = result["entities"][0]
        self.assertEqual(entity["external_net"], -2.5)
        self.assertEqual(entity["unknown_counterparty_outgoing"], 2.5)
        self.assertEqual(result["statistics"]["unknown_endpoints"], 1)

    def test_conflicting_verified_entity_claims_block_attribution(self):
        claims = [
            claim("claim-a", "bc1qsource", "entity-a"),
            claim("claim-b", "bc1qsource", "entity-b"),
        ]
        result = run_aggregation([movement("move-1", "bc1qsource", "bc1qunknown")], claims)
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["conflicted_endpoints"], 1)

    def test_provider_label_does_not_become_entity_control(self):
        claims = [
            claim("claim-a", "bc1qsource", "entity-a",
                  predicate="LABELLED_AS", epistemic="PROVIDER_LABELLED")
        ]
        result = run_aggregation([movement("move-1", "bc1qsource", "bc1qunknown")], claims)
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["unknown_endpoints"], 2)

    def test_claim_recorded_after_cutoff_is_not_used(self):
        claims = [claim("claim-a", "bc1qsource", "entity-a",
                        recorded="2026-11-03T00:00:01Z")]
        result = run_aggregation([movement("move-1", "bc1qsource", "bc1qunknown")], claims)
        self.assertEqual(result["entities"], [])

    def test_duplicate_movement_ids_fail_closed(self):
        item = movement("move-1", "bc1qsource", "bc1qunknown")
        with self.assertRaisesRegex(ValueError, "duplicate movement_id"):
            run_aggregation([item, item], [claim("claim-a", "bc1qsource", "entity-a")])

    def test_unconfirmed_and_quarantined_movements_are_excluded(self):
        item = movement("move-1", "bc1qsource", "bc1qunknown")
        item["transfer"]["confirmation_status"] = "PENDING"
        item["quality_status"] = "QUARANTINED"
        result = run_aggregation([item], [claim("claim-a", "bc1qsource", "entity-a")])
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["excluded"]["quality"], 1)


if __name__ == "__main__":
    unittest.main()
