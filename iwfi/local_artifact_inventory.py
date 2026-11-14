"""Complete, integrity-checked inventory of one managed local artifact root.

This inventory cannot discover copies outside the supplied root or prove OS-level
backup/synchronization state. It fails closed on unregistered or malformed entries.
"""
import hashlib
import json
from pathlib import Path
import re

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ARTIFACT_TYPES = {
    "SOURCE_ARCHIVE", "CHECKSUM", "VALIDATION_REPORT", "NORMALIZED_OBSERVATION",
    "DERIVED_DATA", "SNAPSHOT", "LOG", "BACKUP",
}


class ArtifactInventoryError(ValueError):
    """Raised when the managed artifact root cannot be inventoried completely."""


def build_local_artifact_inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.exists() or not root.is_dir():
        raise ArtifactInventoryError("inventory root must be an existing non-symlink directory")

    records = {}
    entries = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.name == "_deletion_audit":
            if path.is_symlink() or not path.is_dir():
                raise ArtifactInventoryError("deletion audit entry is unsafe")
            continue
        if path.is_symlink() or not path.is_dir() or not _SAFE_ID.fullmatch(path.name):
            raise ArtifactInventoryError(f"unrecognized or unsafe root entry: {path.name}")
        record_path = path / "record.json"
        payload_path = path / "payload.bin"
        if record_path.is_symlink() or not record_path.is_file():
            raise ArtifactInventoryError(f"artifact provenance record missing: {path.name}")
        if payload_path.is_symlink() or not payload_path.is_file():
            raise ArtifactInventoryError(f"artifact payload missing or unsafe: {path.name}")
        try:
            raw_record = record_path.read_bytes()
            record = json.loads(raw_record.decode("utf-8"))
            payload_digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArtifactInventoryError(f"artifact content cannot be verified: {path.name}") from exc
        if not isinstance(record, dict) or record.get("artifact_id") != path.name:
            raise ArtifactInventoryError(f"artifact ID does not match directory: {path.name}")
        if record.get("artifact_type") not in _ARTIFACT_TYPES:
            raise ArtifactInventoryError(f"unsupported artifact type: {path.name}")
        if record.get("local_sha256") != payload_digest:
            raise ArtifactInventoryError(f"payload digest mismatch: {path.name}")
        dependencies = record.get("depends_on_artifact_ids")
        if not isinstance(dependencies, list) or any(
            not isinstance(item, str) or not _SAFE_ID.fullmatch(item) for item in dependencies
        ):
            raise ArtifactInventoryError(
                f"depends_on_artifact_ids must be an explicit safe-ID list: {path.name}"
            )
        # Reconcile established schema lineage fields as well as the explicit graph.
        for field in ("validation_report_artifact_id", "supersedes_artifact_id"):
            reference = record.get(field)
            if reference is not None:
                if not isinstance(reference, str) or not _SAFE_ID.fullmatch(reference):
                    raise ArtifactInventoryError(f"invalid {field}: {path.name}")
                dependencies.append(reference)
        dependencies = sorted(set(dependencies))
        if path.name in dependencies:
            raise ArtifactInventoryError(f"artifact cannot depend on itself: {path.name}")
        records[path.name] = record
        entries.append({
            "artifact_id": path.name,
            "record_sha256": hashlib.sha256(raw_record).hexdigest(),
            "payload_sha256": payload_digest,
            "artifact_type": record["artifact_type"],
            "depends_on_artifact_ids": sorted(dependencies),
        })

    for artifact_id, record in records.items():
        missing = set(record["depends_on_artifact_ids"]) - set(records)
        if missing:
            raise ArtifactInventoryError(
                f"artifact {artifact_id} references missing dependencies: {', '.join(sorted(missing))}"
            )

    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    backups = sorted(
        artifact_id for artifact_id, record in records.items()
        if record["artifact_type"] == "BACKUP"
    )
    return {
        "status": "COMPLETE_LOCAL_ROOT",
        "scope": "SUPPLIED_LOCAL_ROOT_ONLY",
        "artifact_count": len(entries),
        "backup_artifact_ids": backups,
        "entries": entries,
        "inventory_sha256": hashlib.sha256(canonical).hexdigest(),
        "external_copies": "NOT_VERIFIED",
        "os_backup_and_sync_state": "NOT_VERIFIED",
    }



def related_backup_artifact_ids_for(inventory, target_artifact_id):
    dependencies = {
        entry["artifact_id"]: set(entry["depends_on_artifact_ids"])
        for entry in inventory["entries"]
    }
    closure = {target_artifact_id}
    changed = True
    while changed:
        changed = False
        for artifact_id, refs in dependencies.items():
            if artifact_id not in closure and refs.intersection(closure):
                closure.add(artifact_id)
                changed = True
    return sorted(
        artifact_id for artifact_id in inventory["backup_artifact_ids"]
        if artifact_id in closure
    )

def dependent_artifact_ids_for(inventory, target_artifact_id):
    dependencies = {
        entry["artifact_id"]: set(entry["depends_on_artifact_ids"])
        for entry in inventory["entries"]
        if entry["artifact_type"] != "BACKUP"
    }
    closure = {target_artifact_id}
    dependents = set()
    changed = True
    while changed:
        changed = False
        for artifact_id, refs in dependencies.items():
            if artifact_id not in closure and refs.intersection(closure):
                closure.add(artifact_id)
                dependents.add(artifact_id)
                changed = True
    return sorted(dependents)
