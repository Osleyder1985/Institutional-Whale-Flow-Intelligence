"""Fail-closed runtime guard for the IWFI zero-external-cost source policy."""
from datetime import datetime
import re

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PERIODS = {"DAILY", "WEEKLY", "MONTHLY", "PER_REQUEST"}


def _valid_utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def source_cost_policy_errors(policy):
    """Return sorted policy errors; missing or unknown evidence always blocks."""
    if not isinstance(policy, dict):
        return ["policy must be an object"]

    errors = []
    required = (
        "contract_version",
        "source_id",
        "cost_model",
        "recurring_free_quota",
        "billing_risk",
        "payment_method_required",
        "paid_fallback_enabled",
        "terms_url",
        "terms_reviewed_at_utc",
        "zero_cost_eligible",
    )
    for field in required:
        if field not in policy:
            errors.append(f"missing required field: {field}")

    if policy.get("contract_version") != "1.0.0":
        errors.append("unsupported contract_version")
    if not isinstance(policy.get("source_id"), str) or not policy.get("source_id", "").strip():
        errors.append("source_id must be a non-empty string")
    if policy.get("cost_model") != "ZERO_EXTERNAL_COST":
        errors.append("cost_model must be ZERO_EXTERNAL_COST")
    if policy.get("billing_risk") != "NONE":
        errors.append("billing_risk must be NONE")
    if policy.get("payment_method_required") is not False:
        errors.append("payment_method_required must be false")
    if policy.get("paid_fallback_enabled") is not False:
        errors.append("paid_fallback_enabled must be false")
    if policy.get("zero_cost_eligible") is not True:
        errors.append("zero_cost_eligible must be true")
    terms_url = policy.get("terms_url")
    if not isinstance(terms_url, str) or not terms_url.startswith("https://"):
        errors.append("terms_url must be an official HTTPS URL")
    if not _valid_utc(policy.get("terms_reviewed_at_utc")):
        errors.append("terms_reviewed_at_utc must be a valid UTC timestamp")

    quota = policy.get("recurring_free_quota")
    if not isinstance(quota, dict):
        errors.append("recurring_free_quota must be an object")
    else:
        if set(quota) != {"limit", "period"}:
            errors.append("recurring_free_quota must contain only limit and period")
        limit = quota.get("limit")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            errors.append("recurring_free_quota.limit must be a positive integer")
        if quota.get("period") not in _PERIODS:
            errors.append("recurring_free_quota.period must be a documented recurring period")

    return sorted(set(errors))


def authorize_source_request(policy, quota_state, remaining_requests):
    """Return an explicit allow/deny decision before transport; never fail open."""
    errors = source_cost_policy_errors(policy)
    if quota_state != "AVAILABLE":
        errors.append("quota_state must be AVAILABLE")
    if (
        isinstance(remaining_requests, bool)
        or not isinstance(remaining_requests, int)
        or remaining_requests <= 0
    ):
        errors.append("remaining_requests must be a positive integer")
    if errors:
        return {"allowed": False, "status": "BLOCKED", "errors": sorted(set(errors))}
    return {"allowed": True, "status": "AUTHORIZED", "errors": []}
