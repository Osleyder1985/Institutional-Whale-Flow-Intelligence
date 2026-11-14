"""Explicit local artifact deletion with dependency review and retained audit evidence."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil

from iwfi.local_artifact_inventory import (
    ArtifactInventoryError, build_local_artifact_inventory, dependent_artifact_ids_for,
)
from iwfi.retention_policy import authorize_artifact_write, retention_policy_errors
from iwfi.source_use_guard import source_use_policy_errors

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ArtifactDeletionError(ValueError):
    """Raised when a requested deletion cannot be safely executed."""


def _safe_artifact_directory(root, artifact_id):
    if not isinstance(artifact_id, str) or not _SAFE_ID.fullmatch(artifact_id):
        raise ArtifactDeletionError("unsafe artifact ID")
    path = root / artifact_id
    if path.is_symlink() or not path.exists() or not path.is_dir():
        raise ArtifactDeletionError(f"artifact directory missing or unsafe: {artifact_id}")
    for current, dirs, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in dirs + files:
            if (current_path / name).is_symlink():
                raise ArtifactDeletionError(f"symlink found inside artifact: {artifact_id}")
    return path


def delete_artifacts(root, artifact_id, dependent_artifact_ids_reviewed,
                     backup_artifact_ids_reviewed, deletion_id, deletion_method,
                     source_policy, retention_policy, reviewed_at_utc):
    """Delete only explicitly reviewed IDs; never infer dependencies or delete automatically.

    The caller must supply the complete dependency and backup inventory. This function
    cannot discover artifacts stored outside this root or prove secure erasure on SSDs,
    snapshots, filesystem journals, or media controlled by other software.
    """
    root = Path(root)
    if root.is_symlink() or not root.exists() or not root.is_dir():
        raise ArtifactDeletionError("storage root must be an existing, non-symlink local directory")
    if not isinstance(source_policy, dict) or not isinstance(retention_policy, dict):
        raise ArtifactDeletionError("source and retention policies must be objects")
    policy_errors = source_use_policy_errors(source_policy)
    policy_errors.extend(retention_policy_errors(
        retention_policy,
        expected_policy_id=source_policy.get("retention_policy_id"),
        expected_source_id=source_policy.get("source_id"),
    ))
    if policy_errors:
        raise ArtifactDeletionError("source/retention policy invalid: " + "; ".join(policy_errors))
    if not isinstance(artifact_id, str) or not _SAFE_ID.fullmatch(artifact_id):
        raise ArtifactDeletionError("unsafe artifact_id")
    if not isinstance(deletion_id, str) or not _SAFE_ID.fullmatch(deletion_id):
        raise ArtifactDeletionError("unsafe deletion_id")
    if not isinstance(deletion_method, str) or not deletion_method.strip():
        raise ArtifactDeletionError("deletion_method is required")
    if not isinstance(dependent_artifact_ids_reviewed, list) or not isinstance(backup_artifact_ids_reviewed, list):
        raise ArtifactDeletionError("dependency and backup reviews must be explicit lists")
    all_ids = [artifact_id] + dependent_artifact_ids_reviewed + backup_artifact_ids_reviewed
    if any(not isinstance(item, str) or not _SAFE_ID.fullmatch(item) for item in all_ids):
        raise ArtifactDeletionError("all reviewed artifact IDs must be safe strings")
    if len(all_ids) != len(set(all_ids)):
        raise ArtifactDeletionError("artifact IDs must be unique across target, dependencies, and backups")
    if not _SAFE_ID.fullmatch(artifact_id):
        raise ArtifactDeletionError("unsafe artifact_id")
    if not isinstance(reviewed_at_utc, str):
        raise ArtifactDeletionError("reviewed_at_utc must be a UTC timestamp")
    try:
        reviewed = datetime.strptime(reviewed_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ArtifactDeletionError("reviewed_at_utc must use YYYY-MM-DDTHH:MM:SSZ") from exc
    if reviewed.strftime("%Y-%m-%dT%H:%M:%SZ") != reviewed_at_utc:
        raise ArtifactDeletionError("reviewed_at_utc is not a valid UTC timestamp")

    try:
        inventory = build_local_artifact_inventory(root)
    except ArtifactInventoryError as exc:
        raise ArtifactDeletionError("local artifact inventory incomplete: " + str(exc)) from exc
    expected_dependents = dependent_artifact_ids_for(inventory, artifact_id)
    expected_backups = inventory["backup_artifact_ids"]
    if set(dependent_artifact_ids_reviewed) != set(expected_dependents):
        raise ArtifactDeletionError(
            "dependency review does not match complete local inventory; expected: "
            + ", ".join(expected_dependents)
        )
    if set(backup_artifact_ids_reviewed) != set(expected_backups):
        raise ArtifactDeletionError(
            "backup review does not match complete local inventory; expected: "
            + ", ".join(expected_backups)
        )

    audit_dir = root / "_deletion_audit"
    if audit_dir.is_symlink() or (audit_dir.exists() and not audit_dir.is_dir()):
        raise ArtifactDeletionError("deletion audit path must be a non-symlink directory")
    started_path = audit_dir / f"{deletion_id}.started.json"
    completed_path = audit_dir / f"{deletion_id}.completed.json"
    if started_path.exists() or started_path.is_symlink() or completed_path.exists() or completed_path.is_symlink():
        raise ArtifactDeletionError("deletion audit ID already exists")
    audit_auth = authorize_artifact_write(source_policy, retention_policy, "LOG")
    if not audit_auth["allowed"]:
        raise ArtifactDeletionError("cannot retain deletion audit: " + "; ".join(audit_auth["errors"]))
    audit_dir.mkdir(mode=0o700, exist_ok=True)

    records = {}
    paths = {}
    for item_id in all_ids:
        path = _safe_artifact_directory(root, item_id)
        record_path = path / "record.json"
        if record_path.is_symlink() or not record_path.is_file():
            raise ArtifactDeletionError(f"artifact provenance record missing: {item_id}")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactDeletionError(f"invalid provenance record: {item_id}") from exc
        if not isinstance(record, dict) or record.get("source_id") != source_policy.get("source_id"):
            raise ArtifactDeletionError(f"artifact source mismatch: {item_id}")
        if record.get("retention_policy_id") != retention_policy.get("policy_id"):
            raise ArtifactDeletionError(f"artifact retention policy mismatch: {item_id}")
        artifact_type = record.get("artifact_type")
        rule = retention_policy.get("artifact_rules", {}).get(artifact_type, {})
        if rule.get("status") != "APPROVED" or rule.get("deletion_method") != deletion_method:
            raise ArtifactDeletionError(f"deletion method is not approved for {item_id}")
        authorization = authorize_artifact_write(source_policy, retention_policy, artifact_type)
        if not authorization["allowed"]:
            raise ArtifactDeletionError("retention authorization failed: " + "; ".join(authorization["errors"]))
        records[item_id] = record
        paths[item_id] = path

    started_audit = {
        "record_version": "1.0.0", "deletion_id": deletion_id,
        "phase": "DELETION_STARTED", "verification_status": "NOT_VERIFIED",
        "artifact_id": artifact_id, "artifact_type": records[artifact_id]["artifact_type"],
        "reviewed_at_utc": reviewed_at_utc, "deletion_method": deletion_method,
        "dependent_artifact_ids_reviewed": dependent_artifact_ids_reviewed,
        "backup_artifact_ids_reviewed": backup_artifact_ids_reviewed,
        "storage_scope": "LOCAL_ONLY", "secure_erasure_claimed": False,\n        "inventory_sha256": inventory["inventory_sha256"],\n        "inventory_scope": inventory["scope"],
    }
    try:
        with started_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(json.dumps(started_audit, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ArtifactDeletionError("deletion audit ID already exists") from exc

    deleted_ids = []
    failures = []
    for item_id in all_ids:
        try:
            shutil.rmtree(paths[item_id])
            if paths[item_id].exists():
                failures.append(item_id)
            else:
                deleted_ids.append(item_id)
        except OSError:
            failures.append(item_id)

    status = "VERIFIED" if not failures and len(deleted_ids) == len(all_ids) else (
        "PARTIAL" if deleted_ids else "NOT_VERIFIED"
    )
    audit = {
        "record_version": "1.0.0",
        "deletion_id": deletion_id,
        "phase": "DELETION_COMPLETED" if status == "VERIFIED" else "DELETION_INCOMPLETE",
        "artifact_id": artifact_id,
        "artifact_type": records[artifact_id]["artifact_type"],
        "deleted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deletion_method": deletion_method,
        "verification_status": status,
        "dependent_artifact_ids_reviewed": dependent_artifact_ids_reviewed,
        "backup_artifact_ids_reviewed": backup_artifact_ids_reviewed,
        "storage_scope": "LOCAL_ONLY",
        "secure_erasure_claimed": False,
        "notes": (
            "reviewed_at_utc=" + reviewed_at_utc +
            "; deleted_artifact_ids=" + ",".join(deleted_ids) +
            "; failed_artifact_ids=" + ",".join(failures)
        ),
    }
    try:
        with completed_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(json.dumps(audit, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ArtifactDeletionError("completion audit ID already exists; started event retained") from exc

    return {"status": status, "audit_record": str(completed_path), "started_audit_record": str(started_path),
            "deleted_artifact_ids": deleted_ids, "failed_artifact_ids": failures}
