"""Fail-closed validation for local artifact retention policies."""
from datetime import datetime
import re

_REQUIRED_ARTIFACTS = {
    "SOURCE_ARCHIVE", "CHECKSUM", "VALIDATION_REPORT", "NORMALIZED_OBSERVATION",
    "DERIVED_DATA", "SNAPSHOT", "LOG", "BACKUP",
}
_UTC = re.compile(r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$")


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _valid_utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def retention_policy_errors(policy, expected_policy_id=None, expected_source_id=None):
    """Return errors; missing, incomplete, or unapproved retention always blocks writes."""
    if not isinstance(policy, dict):
        return ["retention policy must be an object"]
    errors = []
    required = ("contract_version", "policy_id", "source_id", "status", "storage_scope",
                "cloud_sync_allowed", "external_cost_usd", "artifact_rules")
    errors.extend(f"missing required field: {key}" for key in required if key not in policy)
    if policy.get("contract_version") != "1.0.0":
        errors.append("unsupported retention contract_version")
    if not _nonempty(policy.get("policy_id")):
        errors.append("policy_id must be a non-empty string")
    if expected_policy_id is not None and policy.get("policy_id") != expected_policy_id:
        errors.append("retention policy_id does not match source-use policy")
    if not _nonempty(policy.get("source_id")):
        errors.append("source_id must be a non-empty string")
    if expected_source_id is not None and policy.get("source_id") != expected_source_id:
        errors.append("retention source_id does not match source-use policy")
    if policy.get("status") != "APPROVED":
        errors.append("retention policy status must be APPROVED")
    if policy.get("storage_scope") != "LOCAL_ONLY":
        errors.append("storage_scope must be LOCAL_ONLY")
    if policy.get("cloud_sync_allowed") is not False:
        errors.append("cloud_sync_allowed must be false")
    if policy.get("external_cost_usd") != 0 or isinstance(policy.get("external_cost_usd"), bool):
        errors.append("external_cost_usd must be exactly 0")
    rules = policy.get("artifact_rules")
    if not isinstance(rules, dict):
        errors.append("artifact_rules must be an object")
        return sorted(set(errors))
    missing = _REQUIRED_ARTIFACTS - set(rules)
    extra = set(rules) - _REQUIRED_ARTIFACTS
    errors.extend(f"missing artifact rule: {name}" for name in sorted(missing))
    errors.extend(f"unsupported artifact rule: {name}" for name in sorted(extra))
    for name in sorted(_REQUIRED_ARTIFACTS & set(rules)):
        rule = rules[name]
        if not isinstance(rule, dict):
            errors.append(f"{name}: rule must be an object")
            continue
        if rule.get("status") != "APPROVED":
            errors.append(f"{name}: status must be APPROVED")
        if not _nonempty(rule.get("retention_basis")):
            errors.append(f"{name}: retention_basis is required")
        mode = rule.get("retention_mode")
        if mode == "FIXED_DURATION":
            duration = rule.get("retention_duration_seconds")
            if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
                errors.append(f"{name}: positive retention_duration_seconds required")
            if "retention_end_event" in rule:
                errors.append(f"{name}: fixed duration cannot define retention_end_event")
        elif mode == "UNTIL_EVENT":
            if not _nonempty(rule.get("retention_end_event")):
                errors.append(f"{name}: retention_end_event is required")
            if "retention_duration_seconds" in rule:
                errors.append(f"{name}: event retention cannot define retention_duration_seconds")
        else:
            errors.append(f"{name}: retention_mode must be FIXED_DURATION or UNTIL_EVENT")
        if not _nonempty(rule.get("deletion_method")):
            errors.append(f"{name}: deletion_method is required")
        if rule.get("deletion_evidence_required") is not True:
            errors.append(f"{name}: deletion_evidence_required must be true")
        if rule.get("inherits_source_restrictions") is not True:
            errors.append(f"{name}: source restrictions must be inherited")
    return sorted(set(errors))


def authorize_artifact_write(source_use_policy, retention_policy, artifact_type):
    """Authorize a local write only when source rights and artifact retention both pass."""
    from iwfi.source_use_guard import source_use_policy_errors

    errors = source_use_policy_errors(source_use_policy)
    if not isinstance(source_use_policy, dict):
        errors.append("source-use policy must be an object")
    else:
        errors.extend(retention_policy_errors(
            retention_policy,
            expected_policy_id=source_use_policy.get("retention_policy_id"),
            expected_source_id=source_use_policy.get("source_id"),
        ))
    if artifact_type not in _REQUIRED_ARTIFACTS:
        errors.append("unknown artifact_type")
    if errors:
        return {"allowed": False, "status": "BLOCKED", "errors": sorted(set(errors))}
    return {"allowed": True, "status": "AUTHORIZED_LOCAL_ONLY", "errors": []}
