"""Immutable, local-only artifact persistence guarded by source and retention policy."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re

from iwfi.retention_policy import authorize_artifact_write

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REQUIRED_RECORD_FIELDS = (
    "artifact_id", "artifact_type", "source_id", "source_url", "acquired_at_utc",
    "local_sha256", "terms_reviewed_at_utc", "purpose", "retention_policy_id",
    "revision_id", "storage_scope", "cloud_sync_allowed",
)


class ArtifactStoreError(ValueError):
    """Raised when a local artifact write cannot be safely authorized."""


def _valid_utc(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", value
    ):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _validate_record(record, source_policy, retention_policy, payload_digest):
    if not isinstance(record, dict):
        raise ArtifactStoreError("artifact record must be an object")
    missing = [field for field in _REQUIRED_RECORD_FIELDS if field not in record]
    if missing:
        raise ArtifactStoreError("missing artifact record fields: " + ", ".join(missing))
    if not _SAFE_ID.fullmatch(record["artifact_id"]) or record["artifact_id"] in {".", ".."}:
        raise ArtifactStoreError("artifact_id is not a safe local identifier")
    if record["artifact_type"] not in {
        "SOURCE_ARCHIVE", "CHECKSUM", "VALIDATION_REPORT", "NORMALIZED_OBSERVATION",
        "DERIVED_DATA", "SNAPSHOT", "LOG", "BACKUP",
    }:
        raise ArtifactStoreError("unsupported artifact_type")
    if record["source_id"] != source_policy.get("source_id"):
        raise ArtifactStoreError("artifact source_id does not match source-use policy")
    if record["retention_policy_id"] != retention_policy.get("policy_id"):
        raise ArtifactStoreError("artifact retention_policy_id does not match approved policy")
    if record["purpose"] != "PERSONAL_NON_PRODUCTION_RESEARCH":
        raise ArtifactStoreError("artifact purpose is outside the approved research scope")
    if record["storage_scope"] != "LOCAL_ONLY" or record["cloud_sync_allowed"] is not False:
        raise ArtifactStoreError("artifact must be local-only with cloud sync disabled")
    if not isinstance(record["source_url"], str) or not record["source_url"].startswith("https://"):
        raise ArtifactStoreError("source_url must be HTTPS")
    if not _valid_utc(record["acquired_at_utc"]) or not _valid_utc(record["terms_reviewed_at_utc"]):
        raise ArtifactStoreError("artifact timestamps must be valid UTC timestamps")
    if not isinstance(record["revision_id"], str) or not record["revision_id"].strip():
        raise ArtifactStoreError("revision_id must be non-empty")
    if record["local_sha256"] != payload_digest:
        raise ArtifactStoreError("local_sha256 does not match payload bytes")


def store_artifact(root, payload, record, source_policy, retention_policy):
    """Create a new immutable artifact directory; never overwrite an existing artifact ID."""
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise ArtifactStoreError("payload must be bytes-like")
    payload = bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    _validate_record(record, source_policy, retention_policy, digest)
    authorization = authorize_artifact_write(source_policy, retention_policy, record["artifact_type"])
    if not authorization["allowed"]:
        raise ArtifactStoreError("artifact write blocked: " + "; ".join(authorization["errors"]))

    root_path = Path(root)
    if root_path.is_symlink() or not root_path.exists() or not root_path.is_dir():
        raise ArtifactStoreError("storage root must be an existing, non-symlink local directory")
    artifact_dir = root_path / record["artifact_id"]
    try:
        artifact_dir.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ArtifactStoreError("artifact_id already exists; overwrite is prohibited") from exc

    try:
        payload_path = artifact_dir / "payload.bin"
        record_path = artifact_dir / "record.json"
        with payload_path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with record_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(serialized + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        for path in (artifact_dir / "payload.bin", artifact_dir / "record.json"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            artifact_dir.rmdir()
        except OSError:
            pass
        raise

    return {
        "artifact_id": record["artifact_id"],
        "artifact_directory": str(artifact_dir),
        "payload_sha256": digest,
        "status": "STORED_LOCAL_IMMUTABLE",
    }
