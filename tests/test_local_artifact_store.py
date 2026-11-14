"""Tests for immutable local artifact persistence."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from iwfi.local_artifact_store import ArtifactStoreError, store_artifact


ARTIFACTS = ("SOURCE_ARCHIVE", "CHECKSUM", "VALIDATION_REPORT", "NORMALIZED_OBSERVATION",
             "DERIVED_DATA", "SNAPSHOT", "LOG", "BACKUP")


def source_policy():
    return {
        "contract_version": "1.0.0", "source_id": "binance-vision-spot-aggtrades",
        "license_id": "CC-BY-NC-SA-4.0",
        "terms_url": "https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md",
        "terms_reviewed_at_utc": "2026-11-14T00:00:00Z",
        "rights_evidence_url": "https://github.com/binance/binance-public-data/issues/502",
        "allowed_purpose": "PERSONAL_NON_PRODUCTION_RESEARCH", "storage_scope": "LOCAL_ONLY",
        "retention_policy_id": "retention-v1", "retention_approved": True,
        "derived_data_scope": "INHERITS_SOURCE_RESTRICTIONS", "cloud_sync_allowed": False,
        "redistribution_allowed": False, "commercial_use_allowed": False,
        "live_trading_allowed": False, "public_service_allowed": False,
    }


def retention_policy():
    return {
        "contract_version": "1.0.0", "policy_id": "retention-v1",
        "source_id": "binance-vision-spot-aggtrades", "status": "APPROVED",
        "storage_scope": "LOCAL_ONLY", "cloud_sync_allowed": False, "external_cost_usd": 0,
        "artifact_rules": {
            name: {"status": "APPROVED", "retention_basis": "Test-only owner-approved rule",
                   "retention_mode": "UNTIL_EVENT", "retention_end_event": "Test-only event",
                   "deletion_method": "Test-only local deletion", "deletion_evidence_required": True,
                   "inherits_source_restrictions": True}
            for name in ARTIFACTS
        },
    }


def record_for(payload=b"synthetic fixture"):
    return {
        "record_version": "1.0.0", "artifact_id": "archive-revision-001",
        "artifact_type": "SOURCE_ARCHIVE", "source_id": "binance-vision-spot-aggtrades",
        "source_url": "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/",
        "acquired_at_utc": "2026-11-14T00:00:00Z",
        "provider_checksum": None, "local_sha256": hashlib.sha256(payload).hexdigest(),
        "validation_report_artifact_id": None, "terms_reviewed_at_utc": "2026-11-14T00:00:00Z",
        "purpose": "PERSONAL_NON_PRODUCTION_RESEARCH", "retention_policy_id": "retention-v1",
        "revision_id": "provider-revision-001", "supersedes_artifact_id": None,
        "storage_scope": "LOCAL_ONLY", "cloud_sync_allowed": False,
    }


class LocalArtifactStoreTests(unittest.TestCase):
    def test_new_artifact_is_stored_with_digest_and_record(self):
        payload = b"synthetic fixture"
        with tempfile.TemporaryDirectory() as temp:
            result = store_artifact(temp, payload, record_for(payload), source_policy(), retention_policy())
            directory = Path(result["artifact_directory"])
            self.assertEqual(result["payload_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual((directory / "payload.bin").read_bytes(), payload)
            self.assertEqual(json.loads((directory / "record.json").read_text())["artifact_id"],
                             "archive-revision-001")

    def test_existing_artifact_id_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            store_artifact(temp, b"first", record_for(b"first"), source_policy(), retention_policy())
            with self.assertRaisesRegex(ArtifactStoreError, "overwrite is prohibited"):
                store_artifact(temp, b"second", record_for(b"second"), source_policy(), retention_policy())
            self.assertEqual((Path(temp) / "archive-revision-001" / "payload.bin").read_bytes(), b"first")

    def test_missing_or_unapproved_retention_blocks_write(self):
        policy = retention_policy()
        policy["status"] = "NOT_APPROVED"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ArtifactStoreError, "artifact write blocked"):
                store_artifact(temp, b"synthetic fixture", record_for(), source_policy(), policy)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_hash_mismatch_blocks_write(self):
        record = record_for()
        record["local_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ArtifactStoreError, "does not match payload"):
                store_artifact(temp, b"synthetic fixture", record, source_policy(), retention_policy())
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_source_and_retention_identity_mismatch_block(self):
        record = record_for()
        record["retention_policy_id"] = "other-policy"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ArtifactStoreError, "does not match approved policy"):
                store_artifact(temp, b"synthetic fixture", record, source_policy(), retention_policy())

    def test_path_traversal_and_symlink_root_block(self):
        record = record_for()
        record["artifact_id"] = "../escape"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ArtifactStoreError):
                store_artifact(temp, b"synthetic fixture", record, source_policy(), retention_policy())
            root = Path(temp) / "link"
            root.symlink_to(temp, target_is_directory=True)
            with self.assertRaisesRegex(ArtifactStoreError, "non-symlink"):
                store_artifact(root, b"synthetic fixture", record_for(), source_policy(), retention_policy())


if __name__ == "__main__":
    unittest.main()
