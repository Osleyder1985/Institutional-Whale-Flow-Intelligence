"""Tests for the fail-closed zero-external-cost adapter guard."""
import copy
import unittest

from iwfi.source_cost_guard import (
    authorize_source_request,
    source_cost_policy_errors,
)


def valid_policy():
    return {
        "contract_version": "1.0.0",
        "source_id": "example-public-api",
        "cost_model": "ZERO_EXTERNAL_COST",
        "recurring_free_quota": {"limit": 1000, "period": "DAILY"},
        "billing_risk": "NONE",
        "payment_method_required": False,
        "paid_fallback_enabled": False,
        "terms_url": "https://example.org/terms",
        "terms_reviewed_at_utc": "2026-11-14T00:00:00Z",
        "zero_cost_eligible": True,
    }


class SourceCostGuardTests(unittest.TestCase):
    def test_valid_policy_and_available_quota_authorize_request(self):
        decision = authorize_source_request(valid_policy(), "AVAILABLE", 1)
        self.assertEqual(decision, {"allowed": True, "status": "AUTHORIZED", "errors": []})

    def test_missing_policy_blocks_request(self):
        decision = authorize_source_request(None, "AVAILABLE", 10)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["status"], "BLOCKED")

    def test_unknown_or_missing_cost_evidence_blocks(self):
        policy = valid_policy()
        policy["billing_risk"] = "UNKNOWN"
        self.assertTrue(source_cost_policy_errors(policy))

        policy = valid_policy()
        del policy["terms_reviewed_at_utc"]
        self.assertTrue(source_cost_policy_errors(policy))

    def test_paid_plan_or_pay_per_call_is_rejected(self):
        for field, value in (
            ("cost_model", "PAY_PER_CALL"),
            ("billing_risk", "POSSIBLE"),
            ("payment_method_required", True),
            ("paid_fallback_enabled", True),
            ("zero_cost_eligible", False),
        ):
            with self.subTest(field=field):
                policy = valid_policy()
                policy[field] = value
                self.assertTrue(source_cost_policy_errors(policy))

    def test_non_recurring_or_unknown_quota_is_rejected(self):
        for quota in (
            None,
            {"limit": 1000, "period": "UNKNOWN"},
            {"limit": 0, "period": "DAILY"},
            {"limit": 1000},
        ):
            with self.subTest(quota=quota):
                policy = valid_policy()
                policy["recurring_free_quota"] = quota
                self.assertTrue(source_cost_policy_errors(policy))

    def test_exhausted_unknown_or_unavailable_quota_blocks(self):
        for state in ("EXHAUSTED", "UNKNOWN", None):
            with self.subTest(state=state):
                decision = authorize_source_request(valid_policy(), state, 5)
                self.assertFalse(decision["allowed"])

    def test_zero_or_unknown_remaining_requests_blocks(self):
        for remaining in (0, None, -1, True, "5"):
            with self.subTest(remaining=remaining):
                decision = authorize_source_request(valid_policy(), "AVAILABLE", remaining)
                self.assertFalse(decision["allowed"])

    def test_invalid_terms_url_and_timestamp_block(self):
        policy = valid_policy()
        policy["terms_url"] = "http://example.org/terms"
        policy["terms_reviewed_at_utc"] = "not-a-date"
        self.assertGreaterEqual(len(source_cost_policy_errors(policy)), 2)

    def test_input_is_not_mutated(self):
        policy = valid_policy()
        original = copy.deepcopy(policy)
        authorize_source_request(policy, "AVAILABLE", 2)
        self.assertEqual(policy, original)


if __name__ == "__main__":
    unittest.main()
