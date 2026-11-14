"""Tests for explicit local artifact deletion and audit evidence."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from iwfi.local_artifact_deletion import ArtifactDeletionError, delete_artifacts


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
            name: {"status": "APPROVED", "retention_basis": "Synthetic test rule",
                   "retention_mode": "UNTIL_EVENT", "retention_end_event": "Synthetic event",
                   "deletion_method": "test-unlink", "deletion_evidence_required": True,
                   "inherits_source_restrictions": True}
            for name in ARTIFACTS
        },
    }


def create_artifact(root, artifact_id, artifact_type, depends_on_artifact_ids=None):
    folder = Path(root) / artifact_id
    folder.mkdir()
    payload = b"synthetic"
    (folder / "payload.bin").write_bytes(payload)
    (folder / "record.json").write_text(json.dumps({
        "record_version": "1.0.0", "artifact_id": artifact_id, "artifact_type": artifact_type,
        "source_id": "binance-vision-spot-aggtrades",
        "source_url": "https://data.binance.vision/test",
        "acquired_at_utc": "2026-11-14T00:00:00Z",
        "local_sha256": hashlib.sha256(payload).hexdigest(),
        "terms_reviewed_at_utc": "2026-11-14T00:00:00Z",
        "purpose": "PERSONAL_NON_PRODUCTION_RESEARCH", "retention_policy_id": "retention-v1",
        "revision_id": artifact_id, "storage_scope": "LOCAL_ONLY", "cloud_sync_allowed": False,
        "depends_on_artifact_ids": depends_on_artifact_ids or [],
    }), encoding="utf-8")


class LocalArtifactDeletionTests(unittest.TestCase):
    def test_deletes_primary_derivative_and_backup_and_writes_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            create_artifact(temp, "feature-001", "DERIVED_DATA", ["archive-001"])
            create_artifact(temp, "backup-001", "BACKUP", ["archive-001"])
            result = delete_artifacts(
                temp, "archive-001", ["feature-001"], ["backup-001"], "deletion-001",
                "test-unlink", source_policy(), retention_policy(), "2026-11-14T00:00:00Z"
            )
            self.assertEqual(result["status"], "VERIFIED")
            for artifact_id in ("archive-001", "feature-001", "backup-001"):
                self.assertFalse((Path(temp) / artifact_id).exists())
            started = json.loads(Path(result["started_audit_record"]).read_text(encoding="utf-8"))
            audit = json.loads(Path(result["audit_record"]).read_text(encoding="utf-8"))
            self.assertEqual(started["phase"], "DELETION_STARTED")
            self.assertEqual(started["verification_status"], "NOT_VERIFIED")
            self.assertEqual(audit["phase"], "DELETION_COMPLETED")
            self.assertEqual(audit["verification_status"], "VERIFIED")
            self.assertFalse(audit["secure_erasure_claimed"])
            self.assertEqual(audit["dependent_artifact_ids_reviewed"], ["feature-001"])
            self.assertEqual(audit["backup_artifact_ids_reviewed"], ["backup-001"])

    def test_unrelated_backup_is_reviewed_but_not_deleted(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            create_artifact(temp, "backup-unrelated", "BACKUP", ["other-archive"])
            create_artifact(temp, "other-archive", "SOURCE_ARCHIVE")
            result = delete_artifacts(
                temp, "archive-001", [], ["backup-unrelated"], "deletion-001",
                "test-unlink", source_policy(), retention_policy(), "2026-11-14T00:00:00Z"
            )
            self.assertEqual(result["status"], "VERIFIED")
            self.assertFalse((Path(temp) / "archive-001").exists())
            self.assertTrue((Path(temp) / "backup-unrelated").exists())
            self.assertTrue((Path(temp) / "other-archive").exists())

    def test_backup_can_be_deleted_as_the_target_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "backup-target", "BACKUP")
            result = delete_artifacts(
                temp, "backup-target", [], ["backup-target"], "deletion-001",
                "test-unlink", source_policy(), retention_policy(), "2026-11-14T00:00:00Z"
            )
            self.assertEqual(result["status"], "VERIFIED")
            self.assertFalse((Path(temp) / "backup-target").exists())

    def test_untracked_nested_file_blocks_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            (Path(temp) / "archive-001" / "untracked.txt").write_text("extra")
            with self.assertRaisesRegex(ArtifactDeletionError, "untracked entries"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_omitted_local_dependent_blocks_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            create_artifact(temp, "feature-001", "DERIVED_DATA", ["archive-001"])
            with self.assertRaisesRegex(ArtifactDeletionError, "dependency review does not match"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())
            self.assertTrue((Path(temp) / "feature-001").exists())

    def test_schema_lineage_reference_is_discovered_as_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            create_artifact(temp, "report-001", "VALIDATION_REPORT")
            record_path = Path(temp) / "report-001" / "record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["supersedes_artifact_id"] = "archive-001"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ArtifactDeletionError, "dependency review does not match"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_validation_report_reference_is_discovered_as_dependent(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            create_artifact(temp, "report-001", "VALIDATION_REPORT")
            record_path = Path(temp) / "archive-001" / "record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["validation_report_artifact_id"] = "report-001"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ArtifactDeletionError, "dependency review does not match"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())
            self.assertTrue((Path(temp) / "report-001").exists())

    def test_omitted_backup_blocks_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            create_artifact(temp, "backup-001", "BACKUP", ["archive-001"])
            with self.assertRaisesRegex(ArtifactDeletionError, "backup review does not match"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())
            self.assertTrue((Path(temp) / "backup-001").exists())

    def test_unregistered_root_entry_blocks_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            (Path(temp) / "untracked-folder").mkdir()
            with self.assertRaisesRegex(ArtifactDeletionError, "inventory incomplete"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_payload_digest_mismatch_blocks_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            (Path(temp) / "archive-001" / "payload.bin").write_bytes(b"tampered")
            with self.assertRaisesRegex(ArtifactDeletionError, "payload digest mismatch"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_deletion_audit_binds_to_inventory_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            result = delete_artifacts(
                temp, "archive-001", [], [], "deletion-001", "test-unlink",
                source_policy(), retention_policy(), "2026-11-14T00:00:00Z"
            )
            audit = json.loads(Path(result["audit_record"]).read_text(encoding="utf-8"))
            self.assertRegex(audit["inventory_sha256"], r"^[a-f0-9]{64}$")
            self.assertEqual(audit["inventory_scope"], "SUPPLIED_LOCAL_ROOT_ONLY")
            self.assertEqual(audit["external_copies"], "NOT_VERIFIED")
            self.assertEqual(audit["os_backup_and_sync_state"], "NOT_VERIFIED")

    def test_missing_dependency_blocks_before_any_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            with self.assertRaisesRegex(ArtifactDeletionError, "dependency review does not match"):
                delete_artifacts(temp, "archive-001", ["missing-derivative"], [],
                                 "deletion-001", "test-unlink", source_policy(),
                                 retention_policy(), "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_unapproved_or_wrong_deletion_method_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            with self.assertRaisesRegex(ArtifactDeletionError, "not approved"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "other-method", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_duplicate_ids_and_existing_audit_id_block(self):
        with tempfile.TemporaryDirectory() as temp:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            with self.assertRaisesRegex(ArtifactDeletionError, "unique"):
                delete_artifacts(temp, "archive-001", ["archive-001"], [],
                                 "deletion-001", "test-unlink", source_policy(),
                                 retention_policy(), "2026-11-14T00:00:00Z")
            (Path(temp) / "_deletion_audit").mkdir()
            (Path(temp) / "_deletion_audit" / "deletion-001.started.json").write_text("{}")
            with self.assertRaisesRegex(ArtifactDeletionError, "already exists"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())

    def test_symlink_inside_artifact_blocks(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as other:
            create_artifact(temp, "archive-001", "SOURCE_ARCHIVE")
            (Path(temp) / "archive-001" / "linked").symlink_to(other, target_is_directory=True)
            with self.assertRaisesRegex(ArtifactDeletionError, "symlink"):
                delete_artifacts(temp, "archive-001", [], [], "deletion-001",
                                 "test-unlink", source_policy(), retention_policy(),
                                 "2026-11-14T00:00:00Z")
            self.assertTrue((Path(temp) / "archive-001").exists())


if __name__ == "__main__":
    unittest.main()
