import json
import unittest

from iwfi.evidence_snapshot_provenance import build_snapshot_descriptor
from iwfi.attribution_reconstruction import build_attribution_reconstruction_manifest
from iwfi.verified_actor_registry_reconstruction import reconstruct_actor_registry_as_of


CUTOFF = "2026-11-12T12:00:00Z"
EVENT = "2026-11-12T09:00:00Z"


def make_snapshot(snapshot_id, source_id, record_type, records):
    payload = json.dumps({
        "record_type": record_type,
        "coverage_status": "COMPLETE",
        "records": records,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    descriptor = build_snapshot_descriptor(
        source_id=source_id, source_snapshot_id=snapshot_id,
        retrieved_at_utc="2026-11-12T10:00:00Z", published_at_utc=None,
        media_type="application/json", rights_policy_ref="policy:synthetic-fixture",
        retention_decision="RETAINED", payload=payload,
        storage_ref="fixture://" + snapshot_id, hash_permitted=True,
    )
    return descriptor, payload


def fixture():
    observation = {
        "observation_id": "obs-eth-filing",
        "event_time_utc": EVENT,
        "retrieved_at_utc": "2026-11-12T10:00:00Z",
        "recorded_at_utc": "2026-11-12T10:01:00Z",
        "observation_type": "PUBLIC_FILING",
    }
    source_snapshot, source_payload = make_snapshot(
        "snap-eth-observations", "source:synthetic-filings",
        "SOURCE_OBSERVATION", [observation],
    )
    claim = {
        "contract_version": "1.0.0", "claim_id": "claim-eth-actor",
        "recorded_at_utc": "2026-11-12T11:00:00Z",
        "known_at_utc": "2026-11-12T11:00:00Z",
        "valid_from_utc": EVENT, "valid_to_utc": None,
        "epistemic_status": "INFERRED",
        "source_observation_ids": ["obs-eth-filing"],
        "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth-filing"}],
    }
    manifest = build_attribution_reconstruction_manifest(
        claim=claim, snapshot_descriptors=[source_snapshot],
        observation_snapshot_map={"obs-eth-filing": "snap-eth-observations"},
        knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
        algorithm_id="iwfi.synthetic-actor-claim",
        algorithm_version="1.0.0", parameters={"fixture": True},
    )
    registry = {
        "contract_version": "1.2.0",
        "actors": [{
            "contract_version": "1.1.0", "actor_id": "synthetic-eth-fund",
            "actor_type": "FUND", "display_name": "Synthetic ETH Fund",
            "identity_status": "INFERRED",
            "known_at_utc": "2026-11-12T10:30:00Z",
            "recorded_at_utc": "2026-11-12T10:31:00Z",
            "valid_from_utc": EVENT, "valid_to_utc": None,
            "aliases": [], "classifications": [], "coverage": {},
            "evidence_refs": [
                {"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth-filing"},
                {"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-eth-actor"},
            ],
            "counter_evidence_refs": [],
        }],
        "relationships": [],
    }
    return claim, registry, source_snapshot, source_payload, manifest


class VerifiedActorRegistryReconstructionTests(unittest.TestCase):
    def test_integrates_manifest_snapshot_claim_and_actor_registry(self):
        claim, registry, snapshot, payload, manifest = fixture()
        result = reconstruct_actor_registry_as_of(
            manifest=manifest, attribution_claim=claim, actor_registry=registry,
            snapshots_by_id={snapshot["source_snapshot_id"]: snapshot},
            payloads_by_id={snapshot["source_snapshot_id"]: payload},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
        )
        self.assertEqual(result["status"], "ACTOR_REGISTRY_RECONSTRUCTED", msg=result)
        self.assertEqual(result["claim_epistemic_status"], "INFERRED")
        self.assertEqual(result["resolution"]["status"], "RESOLVED")
        self.assertEqual(len(result["verified_snapshots"]), 1)

    def test_modified_payload_fails_before_semantic_resolution(self):
        claim, registry, snapshot, payload, manifest = fixture()
        altered = payload.replace(b"PUBLIC_FILING", b"ON_CHAIN_TX___")
        result = reconstruct_actor_registry_as_of(
            manifest=manifest, attribution_claim=claim, actor_registry=registry,
            snapshots_by_id={snapshot["source_snapshot_id"]: snapshot},
            payloads_by_id={snapshot["source_snapshot_id"]: altered},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
        )
        self.assertEqual(result["status"], "INTEGRITY_FAILED")

    def test_future_snapshot_is_not_accepted(self):
        claim, registry, snapshot, payload, manifest = fixture()
        snapshot["retrieved_at_utc"] = "2026-11-12T13:00:00Z"
        result = reconstruct_actor_registry_as_of(
            manifest=manifest, attribution_claim=claim, actor_registry=registry,
            snapshots_by_id={snapshot["source_snapshot_id"]: snapshot},
            payloads_by_id={snapshot["source_snapshot_id"]: payload},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
        )
        self.assertEqual(result["status"], "INTEGRITY_FAILED")

    def test_claim_cannot_be_silently_replaced(self):
        claim, registry, snapshot, payload, manifest = fixture()
        altered = dict(claim, epistemic_status="VERIFIED")
        result = reconstruct_actor_registry_as_of(
            manifest=manifest, attribution_claim=altered, actor_registry=registry,
            snapshots_by_id={snapshot["source_snapshot_id"]: snapshot},
            payloads_by_id={snapshot["source_snapshot_id"]: payload},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
        )
        self.assertEqual(result["status"], "INTEGRITY_FAILED")

    def test_transfer_observation_cannot_be_used_as_beneficial_owner_proof(self):
        claim, registry, snapshot, payload, manifest = fixture()
        document = json.loads(payload.decode())
        document["records"][0]["observation_type"] = "TOKEN_TRANSFER"
        changed_payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        from iwfi.evidence_snapshot_provenance import build_snapshot_descriptor
        replacement = build_snapshot_descriptor(
            source_id=snapshot["source_id"], source_snapshot_id=snapshot["source_snapshot_id"],
            retrieved_at_utc=snapshot["retrieved_at_utc"], published_at_utc=None,
            media_type="application/json", rights_policy_ref=snapshot["rights_policy_ref"],
            retention_decision="RETAINED", payload=changed_payload,
            storage_ref="fixture://replacement", hash_permitted=True,
        )
        manifest = build_attribution_reconstruction_manifest(
            claim=claim, snapshot_descriptors=[replacement],
            observation_snapshot_map={"obs-eth-filing": replacement["source_snapshot_id"]},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
            algorithm_id="iwfi.synthetic-actor-claim",
            algorithm_version="1.0.0", parameters={"fixture": True},
        )
        registry["actors"][0]["evidence_refs"] = [{
            "ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth-filing"
        }]
        registry["actors"][0]["evidence_refs"][0]["predicate"] = "BENEFICIAL_OWNER"
        # The resolver's predicate is an API argument, not a reference attribute;
        # this integration deliberately does not infer predicates from arbitrary refs.
        # Verify the transfer remains typed evidence, not an ownership conclusion.
        result = reconstruct_actor_registry_as_of(
            manifest=manifest, attribution_claim=claim, actor_registry=registry,
            snapshots_by_id={replacement["source_snapshot_id"]: replacement},
            payloads_by_id={replacement["source_snapshot_id"]: changed_payload},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT,
        )
        self.assertEqual(result["status"], "ACTOR_REGISTRY_RECONSTRUCTED")
        self.assertEqual(result["resolution"]["status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
