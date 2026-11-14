"""Tests for fail-closed source license and retention restrictions."""
import copy
import unittest

from iwfi.source_use_guard import authorize_source_use, source_use_policy_errors


ARTIFACTS = ("SOURCE_ARCHIVE", "CHECKSUM", "VALIDATION_REPORT", "NORMALIZED_OBSERVATION",
             "DERIVED_DATA", "SNAPSHOT", "LOG", "BACKUP")


def valid_policy():
    return {
        "contract_version": "1.0.0", "source_id": "binance-vision-spot-aggtrades",
        "license_id": "CC-BY-NC-SA-4.0",
        "terms_url": "https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md",
        "terms_reviewed_at_utc": "2026-11-14T00:00:00Z",
        "rights_evidence_url": "https://github.com/binance/binance-public-data/issues/502",
        "allowed_purpose": "PERSONAL_NON_PRODUCTION_RESEARCH", "storage_scope": "LOCAL_ONLY",
        "retention_policy_id": "local-research-retention-v1", "retention_approved": True,
        "derived_data_scope": "INHERITS_SOURCE_RESTRICTIONS", "cloud_sync_allowed": False,
        "redistribution_allowed": False, "commercial_use_allowed": False,
        "live_trading_allowed": False, "public_service_allowed": False,
    }


def valid_retention_policy():
    return {
        "contract_version": "1.0.0", "policy_id": "local-research-retention-v1",
        "source_id": "binance-vision-spot-aggtrades", "status": "APPROVED",
        "storage_scope": "LOCAL_ONLY", "cloud_sync_allowed": False, "external_cost_usd": 0,
        "artifact_rules": {
            name: {"status": "APPROVED", "retention_basis": "Owner-reviewed basis",
                   "retention_mode": "UNTIL_EVENT", "retention_end_event": "Owner-defined event",
                   "deletion_method": "Verified local deletion", "deletion_evidence_required": True,
                   "inherits_source_restrictions": True}
            for name in ARTIFACTS
        },
    }


def authorize(operation="LOCAL_RESEARCH", policy=None, retention=None, artifact="SOURCE_ARCHIVE",
              destination="LOCAL_ONLY"):
    return authorize_source_use(policy or valid_policy(), operation, destination,
                                retention if retention is not None else valid_retention_policy(),
                                artifact)


class SourceUseGuardTests(unittest.TestCase):
    def test_local_operations_require_and_accept_matching_retention(self):
        for operation in ("DOWNLOAD", "STORE_LOCAL", "LOCAL_RESEARCH", "DERIVE_LOCAL"):
            with self.subTest(operation=operation):
                self.assertTrue(authorize(operation)["allowed"])

    def test_missing_retention_blocks_every_operation(self):
        for operation in ("DOWNLOAD", "STORE_LOCAL", "LOCAL_RESEARCH", "DERIVE_LOCAL"):
            with self.subTest(operation=operation):
                self.assertFalse(authorize(operation, retention=None if False else {}).get("allowed"))
        self.assertFalse(authorize(retention={})["allowed"])

    def test_external_or_commercial_operations_are_blocked(self):
        for operation in ("EXPORT", "SYNC", "DISTRIBUTE", "COMMERCIAL_USE", "LIVE_TRADING", "PUBLIC_SERVICE"):
            with self.subTest(operation=operation):
                self.assertFalse(authorize(operation)["allowed"])

    def test_non_local_destination_and_unknown_operation_block(self):
        self.assertFalse(authorize(destination="CLOUD")["allowed"])
        self.assertFalse(authorize("UNKNOWN")["allowed"])

    def test_unapproved_incomplete_or_mismatched_retention_blocks(self):
        for mutate in (
            lambda p: p.update(status="NOT_APPROVED"),
            lambda p: p["artifact_rules"].pop("BACKUP"),
            lambda p: p.update(policy_id="different-id"),
            lambda p: p.update(source_id="different-source"),
            lambda p: p.update(cloud_sync_allowed=True),
        ):
            retention = valid_retention_policy()
            mutate(retention)
            self.assertFalse(authorize(retention=retention)["allowed"])

    def test_unknown_or_unapproved_artifact_blocks(self):
        self.assertFalse(authorize(artifact="UNKNOWN")["allowed"])
        retention = valid_retention_policy()
        retention["artifact_rules"]["SOURCE_ARCHIVE"]["status"] = "NOT_APPROVED"
        self.assertFalse(authorize(retention=retention)["allowed"])

    def test_source_rights_errors_still_block(self):
        policy = valid_policy()
        policy["commercial_use_allowed"] = True
        self.assertTrue(source_use_policy_errors(policy))
        self.assertFalse(authorize(policy=policy)["allowed"])

    def test_input_is_not_mutated(self):
        policy, retention = valid_policy(), valid_retention_policy()
        original = copy.deepcopy((policy, retention))
        authorize(policy=policy, retention=retention)
        self.assertEqual((policy, retention), original)


if __name__ == "__main__":
    unittest.main()
