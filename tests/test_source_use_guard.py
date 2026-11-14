"""Tests for fail-closed source license and use restrictions."""
import copy
import unittest

from iwfi.source_use_guard import authorize_source_use, source_use_policy_errors


def valid_policy():
    return {
        "contract_version": "1.0.0",
        "source_id": "binance-vision-spot-aggtrades",
        "license_id": "CC-BY-NC-SA-4.0",
        "terms_url": "https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md",
        "terms_reviewed_at_utc": "2026-11-14T00:00:00Z",
        "rights_evidence_url": "https://github.com/binance/binance-public-data/issues/502",
        "allowed_purpose": "PERSONAL_NON_PRODUCTION_RESEARCH",
        "storage_scope": "LOCAL_ONLY",
        "retention_policy_id": "local-research-retention-v1",
        "retention_approved": True,
        "derived_data_scope": "INHERITS_SOURCE_RESTRICTIONS",
        "cloud_sync_allowed": False,
        "redistribution_allowed": False,
        "commercial_use_allowed": False,
        "live_trading_allowed": False,
        "public_service_allowed": False,
    }


class SourceUseGuardTests(unittest.TestCase):
    def test_local_research_operations_are_allowed(self):
        for operation in ("DOWNLOAD", "STORE_LOCAL", "LOCAL_RESEARCH", "DERIVE_LOCAL"):
            with self.subTest(operation=operation):
                result = authorize_source_use(valid_policy(), operation)
                self.assertTrue(result["allowed"], result)

    def test_external_or_commercial_operations_are_blocked(self):
        for operation in ("EXPORT", "SYNC", "DISTRIBUTE", "COMMERCIAL_USE", "LIVE_TRADING", "PUBLIC_SERVICE"):
            with self.subTest(operation=operation):
                result = authorize_source_use(valid_policy(), operation)
                self.assertFalse(result["allowed"])

    def test_non_local_destination_is_blocked(self):
        result = authorize_source_use(valid_policy(), "LOCAL_RESEARCH", "CLOUD")
        self.assertFalse(result["allowed"])

    def test_unknown_operation_is_blocked(self):
        self.assertFalse(authorize_source_use(valid_policy(), "UNKNOWN")["allowed"])

    def test_missing_or_unknown_rights_and_retention_block(self):
        for field, value in (
            ("retention_approved", False),
            ("retention_policy_id", ""),
            ("allowed_purpose", "UNKNOWN"),
            ("derived_data_scope", "UNRESTRICTED"),
            ("cloud_sync_allowed", True),
        ):
            with self.subTest(field=field):
                policy = valid_policy()
                policy[field] = value
                self.assertTrue(source_use_policy_errors(policy))
                self.assertFalse(authorize_source_use(policy, "LOCAL_RESEARCH")["allowed"])

    def test_missing_terms_or_invalid_timestamp_blocks(self):
        policy = valid_policy()
        del policy["terms_url"]
        policy["terms_reviewed_at_utc"] = "unknown"
        self.assertTrue(source_use_policy_errors(policy))

    def test_input_is_not_mutated(self):
        policy = valid_policy()
        original = copy.deepcopy(policy)
        authorize_source_use(policy, "LOCAL_RESEARCH")
        self.assertEqual(policy, original)


if __name__ == "__main__":
    unittest.main()