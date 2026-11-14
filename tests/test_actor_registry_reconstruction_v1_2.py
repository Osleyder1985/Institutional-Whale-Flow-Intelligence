import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from iwfi.actor_registry_reconstruction_v1_2 import (
    build_actor_registry_reconstruction_manifest_v1_2,
    verify_actor_registry_reconstruction_manifest_v1_2,
)
from iwfi.evidence_snapshot_provenance import build_snapshot_descriptor
from tests.test_actor_registry_reconstruction_v1_1 import fixture as registry_fixture, CUTOFF, VALID


def root_fixture():
    registry, snapshots, payloads, mapping, _ = registry_fixture()
    claim = {
        "claim_id": "claim-eth-root", "contract_version": "1.0.0",
        "recorded_at_utc": "2026-11-12T10:30:00Z",
        "epistemic_status": "INFERRED",
        "valid_from_utc": VALID, "valid_to_utc": None,
        "source_observation_ids": ["obs-eth"],
    }
    payload = json.dumps(claim, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    descriptor = build_snapshot_descriptor(
        source_id="source:root-claim", source_snapshot_id="snap-root-claim",
        retrieved_at_utc="2026-11-12T10:40:00Z", media_type="application/json",
        rights_policy_ref="policy:synthetic", retention_decision="RETAINED",
        payload=payload, hash_permitted=True, storage_ref="fixture://root-claim",
    )
    manifest = build_actor_registry_reconstruction_manifest_v1_2(
        root_claim=claim, root_claim_snapshot_descriptor=descriptor,
        root_claim_payload=payload, actor_registry=registry,
        snapshot_descriptors=list(snapshots.values()), reference_snapshot_map=mapping,
        knowledge_cutoff_utc=CUTOFF, valid_time_utc=VALID,
        algorithm_id="iwfi.synthetic-root-replay", algorithm_version="1.2.0",
        parameters={"fixture": True},
    )
    return claim, payload, descriptor, registry, snapshots, payloads, manifest


class RootClaimReconstructionV12Tests(unittest.TestCase):
    def verify(self, data):
        claim, raw, descriptor, registry, snapshots, payloads, manifest = data
        return verify_actor_registry_reconstruction_manifest_v1_2(
            manifest=manifest, root_claim_snapshot_descriptor=descriptor,
            root_claim_payload=raw, actor_registry=registry,
            snapshots_by_id=snapshots, payloads_by_id=payloads,
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=VALID,
        )

    def test_manifest_conforms_to_versioned_json_schema(self):
        data = root_fixture()
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "attribution-reconstruction-manifest-v1.2.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(data[6])

    def test_full_root_claim_and_registry_reconstruction(self):
        data = root_fixture()
        result = self.verify(data)
        self.assertEqual(result["status"], "ROOT_CLAIM_AND_ACTOR_REGISTRY_RECONSTRUCTION_VERIFIED")

    def test_root_claim_payload_mutation_fails(self):
        data = list(root_fixture())
        data[1] = data[1].replace(b"INFERRED", b"VERIFIED_")
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_SNAPSHOT_HASH_MISMATCH")

    def test_claim_substitution_fails_even_if_valid_json(self):
        data = list(root_fixture())
        changed = json.loads(data[1])
        changed["epistemic_status"] = "VERIFIED"
        data[1] = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_SNAPSHOT_HASH_MISMATCH")

    def test_root_snapshot_descriptor_substitution_fails(self):
        data = list(root_fixture())
        data[2] = dict(data[2], source_snapshot_id="substituted")
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_SNAPSHOT_DESCRIPTOR_MISMATCH")

    def test_root_claim_snapshot_after_cutoff_fails(self):
        data = list(root_fixture())
        manifest = copy.deepcopy(data[6])
        descriptor = dict(data[2], retrieved_at_utc="2026-11-12T13:00:00Z")
        manifest["root_claim_snapshot"] = dict(
            manifest["root_claim_snapshot"],
            retrieved_at_utc="2026-11-12T13:00:00Z",
            descriptor_hash=__import__("hashlib").sha256(
                json.dumps(descriptor, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
        )
        unsigned = {k: v for k, v in manifest.items() if k != "manifest_hash"}
        manifest["manifest_hash"] = __import__("hashlib").sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        data[2], data[6] = descriptor, manifest
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_SNAPSHOT_AFTER_CUTOFF")

    def test_unbound_root_descriptor_metadata_mutation_fails(self):
        data = list(root_fixture())
        data[2] = dict(data[2], rights_policy_ref="policy:substituted")
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_SNAPSHOT_DESCRIPTOR_MISMATCH")

    def test_root_snapshot_id_cannot_collide_with_registry_snapshot(self):
        claim, raw, descriptor, registry, snapshots, _, _ = root_fixture()
        colliding = dict(descriptor, source_snapshot_id="snap-eth")
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            build_actor_registry_reconstruction_manifest_v1_2(
                root_claim=claim, root_claim_snapshot_descriptor=colliding,
                root_claim_payload=raw, actor_registry=registry,
                snapshot_descriptors=list(snapshots.values()),
                reference_snapshot_map={
                    "SOURCE_OBSERVATION:obs-eth": "snap-eth",
                    "SOURCE_OBSERVATION:obs-btc-counter": "snap-counter",
                    "ATTRIBUTION_CLAIM:claim-eth": "snap-claim",
                }, knowledge_cutoff_utc=CUTOFF, valid_time_utc=VALID,
                algorithm_id="test", algorithm_version="1", parameters={})

    def test_missing_root_claim_bytes_fails_closed(self):
        data = list(root_fixture())
        data[1] = None
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_PAYLOAD_UNAVAILABLE")

    def test_wrong_root_claim_id_fails(self):
        data = list(root_fixture())
        changed = json.loads(data[1])
        changed["claim_id"] = "other-claim"
        data[1] = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(self.verify(tuple(data))["reason"], "ROOT_CLAIM_SNAPSHOT_HASH_MISMATCH")

    def test_root_claim_snapshot_cannot_be_metadata_only(self):
        claim, raw, descriptor, registry, snapshots, payloads, _ = root_fixture()
        metadata_only = dict(descriptor, payload_retention="NOT_RETAINED_POLICY")
        with self.assertRaisesRegex(ValueError, "bytes must be retained"):
            build_actor_registry_reconstruction_manifest_v1_2(
                root_claim=claim, root_claim_snapshot_descriptor=metadata_only,
                root_claim_payload=raw, actor_registry=registry,
                snapshot_descriptors=list(snapshots.values()),
                reference_snapshot_map={
                    "SOURCE_OBSERVATION:obs-eth": "snap-eth",
                    "SOURCE_OBSERVATION:obs-btc-counter": "snap-counter",
                    "ATTRIBUTION_CLAIM:claim-eth": "snap-claim",
                }, knowledge_cutoff_utc=CUTOFF, valid_time_utc=VALID,
                algorithm_id="test", algorithm_version="1", parameters={})



if __name__ == "__main__":
    unittest.main()
