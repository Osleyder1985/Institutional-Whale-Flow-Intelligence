"""Tests for fail-closed local retention policy contracts."""
import copy
import unittest

from iwfi.retention_policy import authorize_artifact_write, retention_policy_errors


ARTIFACTS = (
    "SOURCE_ARCHIVE", "CHECKSUM", "VALIDATION_REPORT", "NORMALIZED_OBSERVATION",
    "DERIVED_DATA", "SNAPSHOT", "LOG", "BACKUP",
)


def valid_source_policy():
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
            name: {
                "status": "APPROVED", "retention_basis": "Reviewed and approved by the data owner",
                "retention_mode": "UNTIL_EVENT", "retention_end_event": "Owner-defined review event",
                "deletion_method": "Verified local deletion procedure",
                "deletion_evidence_required": True, "inherits_source_restrictions": True,
            } for name in ARTIFACTS
        },
    }


class RetentionPolicyTests(unittest.TestCase):
    def test_complete_approved_policy_authorizes_each_artifact(self):
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact):
                result = authorize_artifact_write(valid_source_policy(), valid_retention_policy(), artifact)
                self.assertTrue(result["allowed"], result)

    def test_unapproved_template_blocks(self):
        policy = valid_retention_policy()
        policy["status"] = "NOT_APPROVED"
        self.assertTrue(retention_policy_errors(policy))
        self.assertFalse(authorize_artifact_write(valid_source_policy(), policy, "SOURCE_ARCHIVE")["allowed"])

    def test_missing_artifact_coverage_blocks(self):
        policy = valid_retention_policy()
        del policy["artifact_rules"]["BACKUP"]
        self.assertTrue(retention_policy_errors(policy))

    def test_unknown_artifact_blocks(self):
        self.assertFalse(authorize_artifact_write(valid_source_policy(), valid_retention_policy(), "UNKNOWN")["allowed"])

    def test_missing_retention_duration_or_event_blocks(self):
        policy = valid_retention_policy()
        rule = policy["artifact_rules"]["SOURCE_ARCHIVE"]
        del rule["retention_end_event"]
        self.assertTrue(retention_policy_errors(policy))

    def test_fixed_duration_requires_explicit_positive_duration(self):
        policy = valid_retention_policy()
        rule = policy["artifact_rules"]["SOURCE_ARCHIVE"]
        rule["retention_mode"] = "FIXED_DURATION"
        rule.pop("retention_end_event")
        self.assertTrue(retention_policy_errors(policy))
        rule["retention_duration_seconds"] = 86400
        self.assertFalse(retention_policy_errors(policy))

    def test_source_mismatch_and_policy_id_mismatch_block(self):
        policy = valid_retention_policy()
        policy["source_id"] = "other-source"
        self.assertTrue(retention_policy_errors(policy, "local-research-retention-v1",
                                                "binance-vision-spot-aggtrades"))

    def test_cloud_sync_and_nonzero_cost_block(self):
        policy = valid_retention_policy()
        policy["cloud_sync_allowed"] = True
        policy["external_cost_usd"] = 1
        self.assertTrue(retention_policy_errors(policy))

    def test_deletion_evidence_and_license_inheritance_required(self):
        policy = valid_retention_policy()
        policy["artifact_rules"]["DERIVED_DATA"]["deletion_evidence_required"] = False
        policy["artifact_rules"]["DERIVED_DATA"]["inherits_source_restrictions"] = False
        self.assertTrue(retention_policy_errors(policy))

    def test_input_is_not_mutated(self):
        policy = valid_retention_policy()
        original = copy.deepcopy(policy)
        retention_policy_errors(policy)
        self.assertEqual(policy, original)


if __name__ == "__main__":
    unittest.main()
