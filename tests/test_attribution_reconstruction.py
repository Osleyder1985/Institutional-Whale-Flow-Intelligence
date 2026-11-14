import hashlib
import json
from pathlib import Path
import unittest

import jsonschema

from iwfi.attribution_reconstruction import (
    build_attribution_reconstruction_manifest,
    verify_attribution_reconstruction,
)
from iwfi.evidence_snapshot_provenance import build_snapshot_descriptor


CUTOFF = "2026-11-12T12:00:00Z"
EVENT_TIME = "2026-11-12T09:00:00Z"


def make_snapshot(snapshot_id, source_id, payload, retrieved_at="2026-11-12T10:00:00Z"):
    return build_snapshot_descriptor(
        source_id=source_id,
        source_snapshot_id=snapshot_id,
        retrieved_at_utc=retrieved_at,
        published_at_utc=None,
        media_type="application/json",
        rights_policy_ref="policy:synthetic-fixture",
        retention_decision="NOT_RETAINED_POLICY",
        payload=payload,
        hash_permitted=True,
    )


def make_claim(asset="BTC"):
    return {
        "contract_version": "1.0.0",
        "claim_id": "claim-" + asset.lower() + "-001",
        "recorded_at_utc": "2026-11-12T11:00:00Z",
        "valid_from_utc": EVENT_TIME,
        "valid_to_utc": None,
        "epistemic_status": "DISPUTED",
        "claim_source": {"provider": "synthetic-fixture", "endpoint": "fixture",
                         "record_id": None, "observation_ids": ["obs-" + asset.lower() + "-support"]},
        "supporting_evidence": [{
            "evidence_type": "ON_CHAIN_OBSERVATION", "evidence_ref": "ref-support",
            "source": "synthetic-fixture", "observation_id": "obs-" + asset.lower() + "-support"
        }],
        "counter_evidence": [{
            "evidence_type": "OTHER", "evidence_ref": "ref-counter",
            "source": "synthetic-fixture", "observation_id": "obs-" + asset.lower() + "-counter"
        }],
    }


def build(asset="BTC"):
    claim = make_claim(asset)
    support_payload = ('{"asset":"' + asset + '","side":"support"}').encode()
    counter_payload = ('{"asset":"' + asset + '","side":"counter"}').encode()
    support = make_snapshot("snap-" + asset.lower() + "-support", "source-" + asset.lower(), support_payload)
    counter = make_snapshot("snap-" + asset.lower() + "-counter", "source-" + asset.lower() + "-counter", counter_payload)
    snapshots = [support, counter]
    payloads = {
        support["source_snapshot_id"]: support_payload,
        counter["source_snapshot_id"]: counter_payload,
    }
    mapping = {
        "obs-" + asset.lower() + "-support": support["source_snapshot_id"],
        "obs-" + asset.lower() + "-counter": counter["source_snapshot_id"],
    }
    manifest = build_attribution_reconstruction_manifest(
        claim=claim, snapshot_descriptors=snapshots,
        observation_snapshot_map=mapping, knowledge_cutoff_utc=CUTOFF,
        valid_time_utc=EVENT_TIME, algorithm_id="iwfi-claim-reconstruction",
        algorithm_version="1.0.0", parameters={"preserve_counter_evidence": True},
    )
    return claim, snapshots, payloads, manifest


class AttributionReconstructionTests(unittest.TestCase):
    def test_btc_and_eth_manifests_validate_schema_and_reconstruct_offline(self):
        schema_path = Path(__file__).parent.parent / "schemas" / "attribution-reconstruction-manifest-v1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for asset in ("BTC", "ETH"):
            with self.subTest(asset=asset):
                claim, snapshots, payloads, manifest = build(asset)
                jsonschema.validate(manifest, schema)
                result = verify_attribution_reconstruction(
                    manifest=manifest, claim=claim,
                    snapshots_by_id={item["source_snapshot_id"]: item for item in snapshots},
                    payloads_by_id=payloads,
                )
                self.assertEqual(result["status"], "RECONSTRUCTION_INPUTS_VERIFIED")
                self.assertEqual(len(result["dependencies"]), 2)

    def test_same_frozen_inputs_produce_identical_manifest(self):
        claim, snapshots, _, first = build("BTC")
        mapping = {
            "obs-btc-support": "snap-btc-support",
            "obs-btc-counter": "snap-btc-counter",
        }
        second = build_attribution_reconstruction_manifest(
            claim=claim, snapshot_descriptors=list(reversed(snapshots)),
            observation_snapshot_map=mapping, knowledge_cutoff_utc=CUTOFF,
            valid_time_utc=EVENT_TIME, algorithm_id="iwfi-claim-reconstruction",
            algorithm_version="1.0.0", parameters={"preserve_counter_evidence": True},
        )
        self.assertEqual(first, second)

    def test_claim_recorded_after_cutoff_is_rejected(self):
        claim, snapshots, _, _ = build()
        claim["recorded_at_utc"] = "2026-11-12T13:00:00Z"
        with self.assertRaises(ValueError):
            build_attribution_reconstruction_manifest(
                claim=claim, snapshot_descriptors=snapshots,
                observation_snapshot_map={"obs-btc-support": "snap-btc-support",
                                          "obs-btc-counter": "snap-btc-counter"},
                knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT_TIME,
                algorithm_id="a", algorithm_version="1", parameters={},
            )

    def test_snapshot_retrieved_after_cutoff_is_rejected(self):
        claim = make_claim()
        late = make_snapshot("late", "late-source", b"{}", "2026-11-12T13:00:00Z")
        with self.assertRaises(ValueError):
            build_attribution_reconstruction_manifest(
                claim=claim, snapshot_descriptors=[late],
                observation_snapshot_map={"obs-btc-support": "late"},
                knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT_TIME,
                algorithm_id="a", algorithm_version="1", parameters={},
            )

    def test_unmapped_evidence_observation_fails_closed(self):
        claim, snapshots, _, _ = build()
        with self.assertRaisesRegex(ValueError, "no snapshot mapping"):
            build_attribution_reconstruction_manifest(
                claim=claim, snapshot_descriptors=snapshots,
                observation_snapshot_map={"obs-btc-support": "snap-btc-support"},
                knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT_TIME,
                algorithm_id="a", algorithm_version="1", parameters={},
            )

    def test_modified_claim_fails_claim_hash(self):
        claim, snapshots, payloads, manifest = build()
        claim["epistemic_status"] = "VERIFIED"
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={item["source_snapshot_id"]: item for item in snapshots},
            payloads_by_id=payloads,
        )
        self.assertEqual(result["manifest_status"], "CLAIM_HASH_MISMATCH")

    def test_modified_manifest_parameter_fails_manifest_hash(self):
        claim, snapshots, payloads, manifest = build()
        manifest["parameters"]["preserve_counter_evidence"] = False
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={item["source_snapshot_id"]: item for item in snapshots},
            payloads_by_id=payloads,
        )
        self.assertEqual(result["manifest_status"], "MANIFEST_HASH_MISMATCH")

    def test_missing_counter_snapshot_does_not_discard_contradiction(self):
        claim, snapshots, payloads, manifest = build()
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={snapshots[0]["source_snapshot_id"]: snapshots[0]},
            payloads_by_id={snapshots[0]["source_snapshot_id"]: payloads[snapshots[0]["source_snapshot_id"]]},
        )
        self.assertEqual(result["status"], "INTEGRITY_FAILED")
        self.assertEqual(result["dependencies"][1]["status"], "SNAPSHOT_MISSING")


    def test_valid_time_outside_claim_interval_is_rejected(self):
        claim, snapshots, _, _ = build()
        with self.assertRaisesRegex(ValueError, "precedes the claim validity interval"):
            build_attribution_reconstruction_manifest(
                claim=claim, snapshot_descriptors=snapshots,
                observation_snapshot_map={"obs-btc-support": "snap-btc-support",
                                          "obs-btc-counter": "snap-btc-counter"},
                knowledge_cutoff_utc=CUTOFF,
                valid_time_utc="2026-11-12T08:00:00Z",
                algorithm_id="a", algorithm_version="1", parameters={},
            )

    def test_manifest_schema_rejects_missing_dependency_hash_algorithm(self):
        schema_path = Path(__file__).parent.parent / "schemas" / "attribution-reconstruction-manifest-v1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        _, _, _, manifest = build()
        del manifest["dependencies"][0]["hash_algorithm"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_claim_contract_version_is_bound_to_manifest(self):
        claim, snapshots, payloads, manifest = build()
        claim["contract_version"] = "9.9.9"
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={item["source_snapshot_id"]: item for item in snapshots},
            payloads_by_id=payloads,
        )
        self.assertEqual(result["manifest_status"], "CLAIM_HASH_MISMATCH")


    def test_execution_participant_claim_v1_1_binds_source_observation_snapshots(self):
        schema_path = Path(__file__).parent.parent / "schemas" / "execution-participant-role-claim.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        claim = {
            "contract_version": "1.1.0",
            "claim_id": "exec-role-btc-001",
            "execution_id": "execution-btc-001",
            "actor_id": "actor-institution-001",
            "candidate_actor_ids": [],
            "participant_role": "BUYER",
            "participant_side": "BUY",
            "epistemic_status": "DIRECT",
            "attribution_method": "OFFICIAL_NAMED_EXECUTION_DISCLOSURE",
            "recorded_at_utc": "2026-11-12T11:00:00Z",
            "known_at_utc": "2026-11-12T11:00:00Z",
            "valid_from_utc": EVENT_TIME,
            "valid_to_utc": "2026-11-12T10:00:00Z",
            "source_observation_ids": ["obs-execution-btc"],
            "supporting_evidence": [{
                "evidence_type": "OFFICIAL_NAMED_EXECUTION_DISCLOSURE",
                "source": "synthetic-fixture", "record_ref": "record-btc-001",
                "observation_id": "obs-execution-btc"
            }],
            "counter_evidence": []
        }
        jsonschema.validate({"contract_version": "1.1.0", "claims": [claim]}, schema)
        payload = b'{"execution":"btc","participant":"actor-institution-001"}'
        snapshot = make_snapshot("snap-execution-btc", "synthetic-execution", payload)
        manifest = build_attribution_reconstruction_manifest(
            claim=claim, snapshot_descriptors=[snapshot],
            observation_snapshot_map={"obs-execution-btc": "snap-execution-btc"},
            knowledge_cutoff_utc=CUTOFF, valid_time_utc=EVENT_TIME,
            algorithm_id="iwfi-execution-claim-reconstruction",
            algorithm_version="1.0.0", parameters={"role_resolution": "direct-only"},
        )
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={"snap-execution-btc": snapshot},
            payloads_by_id={"snap-execution-btc": payload},
        )
        self.assertEqual(result["status"], "RECONSTRUCTION_INPUTS_VERIFIED")


    def test_manifest_cannot_drop_or_invent_claim_observation_dependencies(self):
        claim, snapshots, payloads, manifest = build()
        manifest["dependencies"][0]["observation_ids"] = ["invented-observation"]
        unsigned = {key: value for key, value in manifest.items() if key != "manifest_hash"}
        encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        manifest["manifest_hash"] = hashlib.sha256(encoded).hexdigest()
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={item["source_snapshot_id"]: item for item in snapshots},
            payloads_by_id=payloads,
        )
        self.assertEqual(result["manifest_status"], "OBSERVATION_DEPENDENCY_MISMATCH")

    def test_payload_substitution_is_detected(self):
        claim, snapshots, payloads, manifest = build()
        payloads["snap-btc-support"] = b'{"asset":"ETH","side":"support"}'
        result = verify_attribution_reconstruction(
            manifest=manifest, claim=claim,
            snapshots_by_id={item["source_snapshot_id"]: item for item in snapshots},
            payloads_by_id=payloads,
        )
        self.assertEqual(result["status"], "INTEGRITY_FAILED")


if __name__ == "__main__":
    unittest.main()
