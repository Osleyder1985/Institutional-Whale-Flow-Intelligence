"""Fail-closed runtime guard for source license and artifact retention restrictions."""
from datetime import datetime
import re

_LOCAL_OPERATIONS = {"DOWNLOAD", "STORE_LOCAL", "LOCAL_RESEARCH", "DERIVE_LOCAL"}
_FORBIDDEN_OPERATIONS = {
    "EXPORT", "SYNC", "DISTRIBUTE", "COMMERCIAL_USE", "LIVE_TRADING", "PUBLIC_SERVICE"
}


def _valid_utc(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", value
    ):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def source_use_policy_errors(policy):
    """Return source-use metadata errors; this does not establish legal rights."""
    if not isinstance(policy, dict):
        return ["policy must be an object"]
    required = (
        "contract_version", "source_id", "license_id", "terms_url",
        "terms_reviewed_at_utc", "rights_evidence_url", "allowed_purpose",
        "storage_scope", "retention_policy_id", "retention_approved",
        "derived_data_scope", "cloud_sync_allowed", "redistribution_allowed",
        "commercial_use_allowed", "live_trading_allowed", "public_service_allowed",
    )
    errors = [f"missing required field: {key}" for key in required if key not in policy]
    if policy.get("contract_version") != "1.0.0":
        errors.append("unsupported contract_version")
    for key in ("source_id", "license_id", "retention_policy_id"):
        if not isinstance(policy.get(key), str) or not policy.get(key, "").strip():
            errors.append(f"{key} must be a non-empty string")
    for key in ("terms_url", "rights_evidence_url"):
        value = policy.get(key)
        if not isinstance(value, str) or not value.startswith("https://"):
            errors.append(f"{key} must be an HTTPS URL")
    if not _valid_utc(policy.get("terms_reviewed_at_utc")):
        errors.append("terms_reviewed_at_utc must be a valid UTC timestamp")
    fixed_values = {
        "allowed_purpose": "PERSONAL_NON_PRODUCTION_RESEARCH",
        "storage_scope": "LOCAL_ONLY",
        "retention_approved": True,
        "derived_data_scope": "INHERITS_SOURCE_RESTRICTIONS",
        "cloud_sync_allowed": False,
        "redistribution_allowed": False,
        "commercial_use_allowed": False,
        "live_trading_allowed": False,
        "public_service_allowed": False,
    }
    for key, expected in fixed_values.items():
        actual = policy.get(key)
        if actual is not expected if isinstance(expected, bool) else actual != expected:
            errors.append(f"{key} must be {str(expected).lower() if isinstance(expected, bool) else expected}")
    return sorted(set(errors))


def authorize_source_use(policy, operation, destination="LOCAL_ONLY",
                         retention_policy=None, artifact_type=None):
    """Authorize only when source terms AND the exact artifact retention rule pass."""
    errors = source_use_policy_errors(policy)
    if operation in _FORBIDDEN_OPERATIONS:
        errors.append(f"operation {operation} is prohibited by the current source-use scope")
    elif operation not in _LOCAL_OPERATIONS:
        errors.append("operation is unknown or not explicitly permitted")
    if destination != "LOCAL_ONLY":
        errors.append("destination must be LOCAL_ONLY")
    if retention_policy is None:
        errors.append("an approved retention_policy is required for every operation")
    else:
        from iwfi.retention_policy import retention_policy_errors
        source_id = policy.get("source_id") if isinstance(policy, dict) else None
        policy_id = policy.get("retention_policy_id") if isinstance(policy, dict) else None
        errors.extend(retention_policy_errors(
            retention_policy, expected_policy_id=policy_id, expected_source_id=source_id
        ))
        if artifact_type not in retention_policy.get("artifact_rules", {}):
            errors.append("artifact_type must identify a covered retention rule")
        elif retention_policy.get("artifact_rules", {}).get(artifact_type, {}).get("status") != "APPROVED":
            errors.append("artifact_type retention rule must be APPROVED")
    if errors:
        return {"allowed": False, "status": "BLOCKED", "errors": sorted(set(errors))}
    return {"allowed": True, "status": "AUTHORIZED_LOCAL_ONLY", "errors": []}
