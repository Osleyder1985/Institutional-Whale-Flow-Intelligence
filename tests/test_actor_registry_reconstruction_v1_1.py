import copy
import unittest

from iwfi.actor_registry_reconstruction_v1_1 import (
    build_actor_registry_reconstruction_manifest_v1_1,
    verify_actor_registry_reconstruction_manifest_v1_1,
)
from iwfi.evidence_snapshot_provenance import build_snapshot_descriptor

CUTOFF = "2026-11-12T12:00:00Z"
VALID = "2026-11-12T09:00:00Z"


def make_snapshot(sid, source, content):
    payload = content.encode("utf-8")
    descriptor = build_snapshot_descriptor(
        source_id=source, source_snapshot_id=sid,
        retrieved_at_utc="2026-11-12T10:00:00Z", published_at_utc=None,
        media_type="application/json", rights_policy_ref="policy:synthetic",
        retention_decision="RETAINED", payload=payload,
        storage_ref="fixture://" + sid, hash_permitted=True,
    )
    return descriptor, payload


def fixture():
    registry = {
        "contract_version": "1.2.0",
        "actors": [{
            "contract_version": "1.1.0", "actor_id": "actor-eth-fund",
            "actor_type": "FUND", "display_name": "Synthetic ETH Fund",
            "identity_status": "INFERRED", "recorded_at_utc": "2026-11-12T10:30:00Z",
            "known_at_utc": "2026-11-12T10:30:00Z", "valid_from_utc": VALID,
            "valid_to_utc": None,
            "aliases": [{
                "value": "Synthetic Fund", "alias_type": "BRAND", "scope": "global",
                "known_at_utc": "2026-11-12T10:30:00Z", "recorded_at_utc": "2026-11-12T10:30:00Z",
                "valid_from_utc": VALID, "valid_to_utc": None,
                "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth"}],
            }],
            "classifications": [{
                "classification": "institutional", "status": "INFERRED", "method": "synthetic",
                "known_at_utc": "2026-11-12T10:30:00Z", "recorded_at_utc": "2026-11-12T10:30:00Z",
                "valid_from_utc": VALID, "valid_to_utc": None,
                "evidence_refs": [{"ref_type": "ATTRIBUTION_CLAIM", "ref_id": "claim-eth"}],
            }],
            "coverage": [],
            "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth"}],
            "counter_evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-btc-counter"}],
        }],
        "relationships": [{
            "relationship_id": "rel-fund-custodian", "subject_actor_id": "actor-eth-fund",
            "object_actor_id": "actor-custodian", "relationship_type": "CUSTODIES_FOR",
            "status": "INFERRED", "known_at_utc": "2026-11-12T10:30:00Z",
            "recorded_at_utc": "2026-11-12T10:30:00Z", "valid_from_utc": VALID,
            "valid_to_utc": None,
            "evidence_refs": [{"ref_type": "SOURCE_OBSERVATION", "ref_id": "obs-eth"}],
            "counter_evidence_refs": [],
        }],
    }
    payloads = {
        "snap-eth": ('{"record_type":"SOURCE_OBSERVATION","coverage_status":"COMPLETE","records":[{"observation_id":"obs-eth"}]}', "source:eth"),
        "snap-counter": ('{"record_type":"SOURCE_OBSERVATION","coverage_status":"COMPLETE","records":[{"observation_id":"obs-btc-counter"}]}', "source:btc"),
        "snap-claim": ('{"record_type":"ATTRIBUTION_CLAIM","coverage_status":"COMPLETE","records":[{"claim_id":"claim-eth"}]}', "source:claims"),
    }
    snapshots, bytes_by_id = {}, {}
    for sid, (body, source) in payloads.items():
        desc, raw = make_snapshot(sid, source, body)
        snapshots[sid], bytes_by_id[sid] = desc, raw
    mapping = {
        "SOURCE_OBSERVATION:obs-eth": "snap-eth",
        "SOURCE_OBSERVATION:obs-btc-counter": "snap-counter",
        "ATTRIBUTION_CLAIM:claim-eth": "snap-claim",
    }
    manifest = build_actor_registry_reconstruction_manifest_v1_1(
        actor_registry=registry, snapshot_descriptors=list(snapshots.values()),
        reference_snapshot_map=mapping, knowledge_cutoff_utc=CUTOFF,
        valid_time_utc=VALID, algorithm_id="iwfi.synthetic-registry-replay",
        algorithm_version="1.1.0", parameters={"fixture": True},
        root_claim_id="claim-eth-root", root_claim_hash="a" * 64,
        root_claim_contract_version="1.0.0",
    )
    return registry, snapshots, bytes_by_id, mapping, manifest


class ActorRegistryManifestV11Tests(unittest.TestCase):
    def verify(self, registry, snapshots, payloads, manifest):
        return verify_actor_registry_reconstruction_manifest_v1_1(
            manifest=manifest, actor_registry=registry, snapshots_by_id=snapshots,
            payloads_by_id=payloads, knowledge_cutoff_utc=CUTOFF,
            valid_time_utc=VALID,
        )

    def test_freezes_all_actor_alias_classification_relationship_and_counter_refs(self):
        registry, snapshots, payloads, _, manifest = fixture()
        self.assertEqual(len(manifest["references"]), 6)
        self.assertEqual(self.verify(registry, snapshots, payloads, manifest)["status"],
                         "ACTOR_REGISTRY_RECONSTRUCTION_VERIFIED")

    def test_registry_mutation_fails_hash_verification(self):
        registry, snapshots, payloads, _, manifest = fixture()
        changed = copy.deepcopy(registry)
        changed["actors"][0]["display_name"] = "Substituted"
        self.assertEqual(self.verify(changed, snapshots, payloads, manifest)["reason"],
                         "ACTOR_REGISTRY_HASH_MISMATCH")

    def test_missing_reference_fails_completeness(self):
        registry, snapshots, payloads, _, manifest = fixture()
        changed = copy.deepcopy(registry)
        changed["actors"][0]["counter_evidence_refs"] = []
        self.assertEqual(self.verify(changed, snapshots, payloads, manifest)["reason"],
                         "ACTOR_REGISTRY_HASH_MISMATCH")

    def test_extra_reference_entry_fails_completeness(self):
        registry, snapshots, payloads, _, manifest = fixture()
        changed = copy.deepcopy(manifest)
        changed["references"].append(copy.deepcopy(changed["references"][0]))
        # Rehashing a malformed manifest does not make the duplicate valid.
        import hashlib, json
        unsigned = {k: v for k, v in changed.items() if k != "manifest_hash"}
        changed["manifest_hash"] = hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False).encode()).hexdigest()
        self.assertEqual(self.verify(registry, snapshots, payloads, changed)["reason"],
                         "DUPLICATE_REFERENCE_ENTRY")

    def test_missing_mapping_rejected_at_build(self):
        registry, snapshots, _, mapping, _ = fixture()
        mapping.pop("SOURCE_OBSERVATION:obs-btc-counter")
        with self.assertRaises(ValueError):
            build_actor_registry_reconstruction_manifest_v1_1(
                actor_registry=registry, snapshot_descriptors=list(snapshots.values()),
                reference_snapshot_map=mapping, knowledge_cutoff_utc=CUTOFF,
                valid_time_utc=VALID, algorithm_id="test", algorithm_version="1",
                parameters={}, root_claim_id="root", root_claim_hash="b"*64,
                root_claim_contract_version="1.0.0")

    def test_wrong_snapshot_substitution_fails_descriptor_binding(self):
        registry, snapshots, payloads, _, manifest = fixture()
        changed = copy.deepcopy(snapshots["snap-eth"])
        changed["source_snapshot_id"] = "snap-counter"
        snapshots["snap-eth"] = changed
        self.assertEqual(self.verify(registry, snapshots, payloads, manifest)["reason"],
                         "SNAPSHOT_VERIFICATION_FAILED")

    def test_partial_payload_unavailable_is_not_claimed_reconstructed(self):
        registry, snapshots, payloads, _, manifest = fixture()
        payloads.pop("snap-eth")
        result = self.verify(registry, snapshots, payloads, manifest)
        self.assertEqual(result["reason"], "SNAPSHOT_VERIFICATION_FAILED")
        self.assertIn("PAYLOAD_UNAVAILABLE", [x["status"] for x in result["dependencies"]])

    def test_snapshot_after_cutoff_is_rejected(self):
        registry, snapshots, payloads, _, manifest = fixture()
        snapshots["snap-eth"]["retrieved_at_utc"] = "2026-11-12T13:00:00Z"
        result = self.verify(registry, snapshots, payloads, manifest)
        self.assertEqual(result["reason"], "SNAPSHOT_VERIFICATION_FAILED")

    def test_valid_time_and_cutoff_must_match_manifest(self):
        registry, snapshots, payloads, _, manifest = fixture()
        result = verify_actor_registry_reconstruction_manifest_v1_1(
            manifest=manifest, actor_registry=registry, snapshots_by_id=snapshots,
            payloads_by_id=payloads, knowledge_cutoff_utc="2026-11-12T13:00:00Z",
            valid_time_utc=VALID)
        self.assertEqual(result["reason"], "KNOWLEDGE_CUTOFF_MISMATCH")

    def test_supporting_and_counterevidence_are_preserved_as_distinct_refs(self):
        registry, _, _, _, manifest = fixture()
        polarities = {r["polarity"] for r in manifest["references"]}
        self.assertEqual(polarities, {"evidence_refs", "counter_evidence_refs"})
        self.assertTrue(any(r["ref_id"] == "obs-btc-counter" and
                            r["polarity"] == "counter_evidence_refs"
                            for r in manifest["references"]))


if __name__ == "__main__":
    unittest.main()
