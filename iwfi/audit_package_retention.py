"""Fail-closed retention authorization for local IWFI audit packages.

This module evaluates only caller-supplied authorization and source-policy records.
It performs no I/O, networking, publication, distribution, or synchronization.
"""
from datetime import datetime
import hashlib
import json
import re

_VERSION = "1.0.0"
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_FORBIDDEN = {"DISTRIBUTE", "PUBLISH", "UPLOAD", "TRANSMIT", "SHARE_EXTERNAL", "SYNC_EXTERNAL"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _fail(reason, **extra):
    return {"status": "RETENTION_REJECTED", "reason": reason, **extra}


def _source_closure(direct, lineage):
    closure, visiting, visited = set(), set(), set()

    def visit(source):
        if source in visiting:
            raise ValueError("SOURCE_LINEAGE_CYCLE")
        if source in visited:
            return
        if source not in lineage:
            raise ValueError("SOURCE_LINEAGE_INCOMPLETE")
        visiting.add(source)
        parents = lineage[source]
        if not isinstance(parents, list) or any(
                not isinstance(parent, str) or not parent.strip() for parent in parents):
            raise ValueError("SOURCE_LINEAGE_INVALID")
        for parent in parents:
            visit(parent)
        visiting.remove(source)
        visited.add(source)
        closure.add(source)

    for source in direct:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("DIRECT_SOURCE_INVALID")
        visit(source)
    return sorted(closure)


def evaluate_retention_authorizations(*, manifest, authorization_context):
    """Require one exact authorization per artifact and valid policies for all ancestors."""
    if not isinstance(manifest, dict) or not isinstance(authorization_context, dict):
        return _fail("INPUT_OBJECTS_REQUIRED")
    evaluated_at = _time(authorization_context.get("evaluated_at_utc"))
    if evaluated_at is None:
        return _fail("EVALUATION_TIME_INVALID")
    if authorization_context.get("package_mode") != "LOCAL_ONLY":
        return _fail("PACKAGE_MODE_NOT_LOCAL_ONLY")
    authorizations = authorization_context.get("artifact_authorizations")
    policies = authorization_context.get("source_policies")
    lineage = authorization_context.get("source_lineage")
    if not isinstance(authorizations, list) or not isinstance(policies, list) or not isinstance(lineage, dict):
        return _fail("AUTHORIZATION_CONTEXT_INCOMPLETE")

    entries = manifest.get("artifacts")
    if not isinstance(entries, list) or not entries:
        return _fail("ARTIFACT_INVENTORY_REQUIRED")
    auth_by_path = {}
    authorization_ids = set()
    for auth in authorizations:
        if not isinstance(auth, dict) or not isinstance(auth.get("artifact_path"), str):
            return _fail("ARTIFACT_AUTHORIZATION_INCOMPLETE")
        path = auth["artifact_path"]
        authorization_id = auth.get("authorization_id")
        if not isinstance(authorization_id, str) or not authorization_id.strip() or authorization_id in authorization_ids:
            return _fail("DUPLICATE_OR_INVALID_ARTIFACT_AUTHORIZATION_ID", artifact_path=path)
        authorization_ids.add(authorization_id)
        if path in auth_by_path:
            return _fail("CONTRADICTORY_ARTIFACT_AUTHORIZATIONS", artifact_path=path)
        auth_by_path[path] = auth
    paths = [item.get("path") if isinstance(item, dict) else None for item in entries]
    if set(auth_by_path) != set(paths) or len(paths) != len(set(paths)):
        return _fail("ARTIFACT_AUTHORIZATION_INVENTORY_MISMATCH")

    for source, parents in lineage.items():
        if (not isinstance(source, str) or not source.strip()
                or not isinstance(parents, list)
                or any(not isinstance(parent, str) or not parent.strip() for parent in parents)
                or len(parents) != len(set(parents))):
            return _fail("SOURCE_LINEAGE_INVALID")
    policy_by_source = {}
    policy_ids = set()
    for policy in policies:
        if not isinstance(policy, dict):
            return _fail("SOURCE_POLICY_INCOMPLETE")
        source = policy.get("source_id")
        if not isinstance(source, str) or not source.strip():
            return _fail("SOURCE_POLICY_INCOMPLETE")
        policy_id = policy.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id.strip() or (source, policy_id) in policy_ids:
            return _fail("DUPLICATE_OR_INVALID_SOURCE_POLICY_ID", source_id=source)
        policy_ids.add((source, policy_id))
        policy_by_source.setdefault(source, []).append(policy)

    artifact_decisions = []
    for entry in sorted(entries, key=lambda item: item["path"]):
        path = entry["path"]
        auth = auth_by_path[path]
        required = ("authorization_id", "artifact_path", "artifact_sha256",
                    "source_ids", "action", "status", "valid_from_utc", "expires_at_utc")
        if any(field not in auth or auth[field] is None for field in required):
            return _fail("ARTIFACT_AUTHORIZATION_INCOMPLETE", artifact_path=path)
        if (not isinstance(auth["authorization_id"], str) or not auth["authorization_id"].strip()
                or auth["artifact_path"] != path or auth["artifact_sha256"] != entry.get("sha256")
                or auth["action"] != "RETAIN_LOCAL" or auth["status"] != "AUTHORIZED"):
            return _fail("ARTIFACT_AUTHORIZATION_MISMATCH", artifact_path=path)
        start, expiry = _time(auth["valid_from_utc"]), _time(auth["expires_at_utc"])
        if start is None or expiry is None or expiry <= start:
            return _fail("ARTIFACT_AUTHORIZATION_INCOMPLETE", artifact_path=path)
        if evaluated_at < start or evaluated_at >= expiry:
            return _fail("ARTIFACT_AUTHORIZATION_EXPIRED_OR_NOT_YET_VALID", artifact_path=path)
        direct = auth["source_ids"]
        if (not isinstance(direct, list) or not direct
                or any(not isinstance(item, str) or not item.strip() for item in direct)
                or len(direct) != len(set(direct))):
            return _fail("ARTIFACT_SOURCE_LINEAGE_INCOMPLETE", artifact_path=path)
        declared_sources = entry.get("source_ids")
        if (not isinstance(declared_sources, list) or not declared_sources
                or any(not isinstance(item, str) or not item.strip() for item in declared_sources)
                or len(declared_sources) != len(set(declared_sources))
                or set(direct) != set(declared_sources)):
            return _fail("ARTIFACT_AUTHORIZATION_SOURCE_BINDING_MISMATCH", artifact_path=path)
        try:
            closure = _source_closure(direct, lineage)
        except ValueError as exc:
            return _fail(str(exc), artifact_path=path)

        for source in closure:
            source_policies = policy_by_source.get(source, [])
            if not source_policies:
                return _fail("SOURCE_POLICY_MISSING", artifact_path=path, source_id=source)
            for policy in source_policies:
                fields = ("policy_id", "policy_version", "source_id", "rights_ref",
                          "status", "valid_from_utc", "expires_at_utc",
                          "allowed_actions", "prohibited_actions")
                if any(field not in policy or policy[field] is None for field in fields):
                    return _fail("SOURCE_POLICY_INCOMPLETE", artifact_path=path, source_id=source)
                pstart, pexpiry = _time(policy["valid_from_utc"]), _time(policy["expires_at_utc"])
                if (not isinstance(policy["policy_id"], str) or not policy["policy_id"].strip()
                        or not isinstance(policy["policy_version"], str) or not policy["policy_version"].strip()
                        or not isinstance(policy["rights_ref"], str) or not policy["rights_ref"].strip()
                        or policy["source_id"] != source or pstart is None or pexpiry is None
                        or pexpiry <= pstart):
                    return _fail("SOURCE_POLICY_INCOMPLETE", artifact_path=path, source_id=source)
                if policy["status"] != "ACTIVE" or evaluated_at < pstart or evaluated_at >= pexpiry:
                    return _fail("SOURCE_POLICY_INACTIVE_OR_EXPIRED", artifact_path=path, source_id=source)
                if (not isinstance(policy["allowed_actions"], list)
                        or "RETAIN_LOCAL" not in policy["allowed_actions"]
                        or not isinstance(policy["prohibited_actions"], list)):
                    return _fail("SOURCE_POLICY_DOES_NOT_AUTHORIZE_LOCAL_RETENTION",
                                 artifact_path=path, source_id=source)
                if _FORBIDDEN.intersection(policy["allowed_actions"]):
                    return _fail("EXTERNAL_DISTRIBUTION_OR_SYNC_PERMISSION_FORBIDDEN",
                                 artifact_path=path, source_id=source)
                if "RETAIN_LOCAL" in policy["prohibited_actions"]:
                    return _fail("CONTRADICTORY_SOURCE_POLICY", artifact_path=path, source_id=source)
        artifact_decisions.append({
            "artifact_path": path,
            "artifact_sha256": entry["sha256"],
            "authorization_id": auth["authorization_id"],
            "authorization_sha256": _sha(_canonical(auth)),
            "direct_source_ids": sorted(direct),
            "resolved_source_ids": closure,
            "source_policy_sha256": {
                source: sorted(_sha(_canonical(policy)) for policy in policy_by_source[source])
                for source in closure
            },
        })

    evidence = {
        "artifact_authorizations": sorted(authorizations, key=lambda item: item["artifact_path"]),
        "source_policies": sorted(policies, key=lambda item: (item.get("source_id", ""), item.get("policy_id", ""))),
        "source_lineage": {key: sorted(value) for key, value in sorted(lineage.items())},
        "package_mode": "LOCAL_ONLY",
    }
    return {
        "status": "RETENTION_AUTHORIZED",
        "decision_version": _VERSION,
        "evaluated_at_utc": authorization_context["evaluated_at_utc"],
        "authorization_evidence_sha256": _sha(_canonical(evidence)),
        "authorization_evidence": evidence,
        "artifact_decisions": artifact_decisions,
    }


def build_retention_decision(*, manifest, authorization_context):
    evaluated = evaluate_retention_authorizations(
        manifest=manifest, authorization_context=authorization_context)
    if evaluated.get("status") != "RETENTION_AUTHORIZED":
        raise ValueError("retention authorization rejected: " + evaluated.get("reason", "UNKNOWN"))
    decision = {
        "decision_version": _VERSION,
        "package_mode": "LOCAL_ONLY",
        "inventory_manifest_hash": manifest.get("manifest_hash"),
        **{key: value for key, value in evaluated.items() if key != "status"},
    }
    decision["decision_sha256"] = _sha(_canonical(decision))
    return decision


def verify_retention_decision(*, decision, manifest, authorization_context):
    """Re-evaluate current rights; a historical authorization is not perpetual."""
    if not isinstance(decision, dict):
        return _fail("RETENTION_DECISION_MISSING")
    unsigned = {key: value for key, value in decision.items() if key != "decision_sha256"}
    if decision.get("decision_sha256") != _sha(_canonical(unsigned)):
        return _fail("RETENTION_DECISION_HASH_MISMATCH")
    frozen_evidence = decision.get("authorization_evidence")
    if (not isinstance(frozen_evidence, dict)
            or _sha(_canonical(frozen_evidence)) != decision.get("authorization_evidence_sha256")):
        return _fail("FROZEN_AUTHORIZATION_EVIDENCE_INVALID")
    if (decision.get("decision_version") != _VERSION
            or decision.get("package_mode") != "LOCAL_ONLY"
            or decision.get("inventory_manifest_hash") != manifest.get("manifest_hash")):
        return _fail("RETENTION_DECISION_BINDING_MISMATCH")
    current = evaluate_retention_authorizations(
        manifest=manifest, authorization_context=authorization_context)
    if current.get("status") != "RETENTION_AUTHORIZED":
        return current
    if current.get("authorization_evidence_sha256") != decision.get("authorization_evidence_sha256"):
        return _fail("AUTHORIZATION_OR_POLICY_CHANGED")
    if current.get("authorization_evidence") != frozen_evidence:
        return _fail("FROZEN_AUTHORIZATION_EVIDENCE_MISMATCH")
    if current.get("artifact_decisions") != decision.get("artifact_decisions"):
        return _fail("ARTIFACT_AUTHORIZATION_DECISION_CHANGED")
    return {"status": "RETENTION_AUTHORIZED",
            "authorization_evidence_sha256": current["authorization_evidence_sha256"],
            "artifact_count": len(current["artifact_decisions"]),
            "evaluated_at_utc": current["evaluated_at_utc"]}
