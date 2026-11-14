import unittest

from iwfi.typed_evidence_provenance import (
    resolve_actor_evidence_as_of,\n    resolve_actor_registry_evidence_as_of,
    resolve_typed_evidence_refs,
)


CUTOFF = "2026-11-10T00:00:00Z"
EVENT = "2026-11-09T12:00:00Z"


def snapshots():
    return {
        "SOURCE_OBSERVATION": {
            "status": "COMPLETE",
            "records": [
                {"observation_id": "obs-btc-1", "retrieved_at_utc": "2026-11-09T13:00:00Z",
                 "event_time_utc": EVENT, "observation_type": "ON_CHAIN_TRANSACTION"},
                {"observation_id": "obs-eth-1", "retrieved_at_utc": "2026-11-09T13:00:00Z",
                 "event_time_utc": EVENT, "observation_type": "PUBLIC_FILING"},
            ],
        },
        "ATTRIBUTION_CLAIM": {
            "status": "COMPLETE",
            "records": [
                {"claim_id": "claim-btc-disputed", "known_at_utc": "2026-11-09T14:00:00Z",
                 "recorded_at_utc": "2026-11-09T14:01:00Z", "valid_from_utc": EVENT,
                 "valid_to_utc": None, "epistemic_status": "DISPUTED",
                 "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}]},
                {"claim_id": "claim-eth-inferred", "known_at_utc": "2026-11-09T14:00:00Z",
                 "recorded_at_utc": "2026-11-09T14:01:00Z", "valid_from_utc": EVENT,
                 "valid_to_utc": None, "epistemic_status": "INFERRED",
                 "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth-1"}]},
            ],
        },
    }


class TypedEvidenceProvenanceTests(unittest.TestCase):
    def test_btc_source_observation_resolves(self):
        result = resolve_typed_evidence_refs(
            [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
            snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["status"], "RESOLVED")

    def test_eth_attribution_claim_keeps_inferred_status(self):
        result = resolve_typed_evidence_refs(
            [{"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-eth-inferred"}],
            snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["resolved"][0]["epistemic_status"], "INFERRED")

    def test_disputed_claim_is_not_upgraded(self):
        result = resolve_typed_evidence_refs(
            [{"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-btc-disputed"}],
            snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["resolved"][0]["epistemic_status"], "DISPUTED")

    def test_missing_reference_in_complete_snapshot_fails_closed(self):
        result = resolve_typed_evidence_refs(
            [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "missing"}],
            snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["rejected"][0]["reason"], "MISSING_FROM_COMPLETE_SNAPSHOT")

    def test_partial_snapshot_does_not_claim_nonexistence(self):
        partial = snapshots()
        partial["SOURCE_OBSERVATION"] = {"status": "PARTIAL", "records": []}
        result = resolve_typed_evidence_refs(
            [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
            partial, CUTOFF, EVENT)
        self.assertEqual(result["rejected"][0]["reason"], "NOT_FOUND_IN_PARTIAL_SNAPSHOT")

    def test_duplicate_ids_are_ambiguous(self):
        data = snapshots()
        data["SOURCE_OBSERVATION"]["records"].append(data["SOURCE_OBSERVATION"]["records"][0])
        result = resolve_typed_evidence_refs(
            [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
            data, CUTOFF, EVENT)
        self.assertEqual(result["rejected"][0]["reason"], "AMBIGUOUS_DUPLICATE_ID")

    def test_future_retrieval_is_excluded_even_if_event_is_old(self):
        data = snapshots()
        data["SOURCE_OBSERVATION"]["records"][0]["retrieved_at_utc"] = "2026-11-11T00:00:00Z"
        result = resolve_typed_evidence_refs(
            [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
            data, CUTOFF, EVENT)
        self.assertEqual(result["rejected"][0]["reason"], "AFTER_KNOWLEDGE_CUTOFF")

    def test_future_recorded_claim_is_excluded(self):
        data = snapshots()
        data["ATTRIBUTION_CLAIM"]["records"][1]["recorded_at_utc"] = "2026-11-11T00:00:00Z"
        result = resolve_typed_evidence_refs(
            [{"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-eth-inferred"}],
            data, CUTOFF, EVENT)
        self.assertEqual(result["rejected"][0]["reason"], "AFTER_KNOWLEDGE_CUTOFF")

    def test_claim_cannot_recursively_reference_another_claim(self):
        data = snapshots()
        data["ATTRIBUTION_CLAIM"]["records"][1]["evidence_refs"] = [
            {"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-btc-disputed"}]
        result = resolve_typed_evidence_refs(
            [{"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-eth-inferred"}],
            data, CUTOFF, EVENT)
        self.assertEqual(result["rejected"][0]["reason"], "CIRCULAR_OR_UNSUPPORTED_CLAIM_REFERENCE")

    def test_supporting_and_counter_evidence_remain_separate(self):
        actor = {"identity_status": "DISPUTED",
                 "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
                 "counter_evidence_refs": [{"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-btc-disputed"}]}
        result = resolve_actor_evidence_as_of(actor, snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["identity_status"], "DISPUTED")
        self.assertEqual(len(result["supporting"]["resolved"]), 1)
        self.assertEqual(result["counter"]["resolved"][0]["epistemic_status"], "DISPUTED")

    def test_transfer_cannot_prove_beneficial_ownership(self):
        result = resolve_typed_evidence_refs(
            [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
            snapshots(), CUTOFF, EVENT, predicate="BENEFICIAL_OWNER")
        self.assertEqual(result["rejected"][0]["reason"],
                         "TRANSFER_DOES_NOT_PROVE_OWNERSHIP_OR_EXECUTION_SIDE")

    def test_actor_registry_v12_integrates_actor_alias_classification_relationship_refs(self):
        registry = {"contract_version": "1.2.0", "actors": [
            {"known_at_utc": "2026-11-09T10:00:00Z", "recorded_at_utc": "2026-11-09T10:01:00Z",
             "valid_from_utc": EVENT, "valid_to_utc": None,
             "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}],
             "counter_evidence_refs": [],
             "aliases": [{"known_at_utc": "2026-11-09T10:00:00Z", "recorded_at_utc": "2026-11-09T10:01:00Z",
                          "valid_from_utc": EVENT, "valid_to_utc": None,
                          "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-1"}]}],
             "classifications": []}],
            "relationships": []}
        result = resolve_actor_registry_evidence_as_of(registry, snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(len(result["records"]), 2)

    def test_wrong_reference_type_is_rejected(self):
        result = resolve_typed_evidence_refs(
            [{"ref_type": "WALLET", "ref_id": "obs-btc-1"}],
            snapshots(), CUTOFF, EVENT)
        self.assertEqual(result["rejected"][0]["reason"], "INVALID_REFERENCE")


if __name__ == "__main__":
    unittest.main()
