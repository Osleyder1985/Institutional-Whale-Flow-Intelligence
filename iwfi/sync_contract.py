"""Pure helpers for validating and fingerprinting offline sync operations.

This module has no network, database, credential, retry, or background behavior.
"""
import hashlib
import json
import re
from datetime import datetime
from uuid import UUID
from datetime import datetime, timezone


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def canonical_payload_hash(payload):
    """Return SHA-256 of deterministic UTF-8 JSON payload bytes."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def operation_fingerprint(operation):
    """Fingerprint the complete immutable envelope, including payload hash."""
    encoded = json.dumps(
        operation,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_operation_semantics(operation):
    """Validate semantic invariants not expressible by the JSON Schema alone."""
    if not isinstance(operation, dict):
        raise ValueError("operation must be an object")
    operation_id = operation.get("operation_id")
    timestamp = operation.get("created_at_device_utc")
    if not isinstance(timestamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp):
        raise ValueError("created_at_device_utc must be UTC with a Z suffix")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at_device_utc must be a valid calendar timestamp") from exc
    if parsed_timestamp.tzinfo != timezone.utc:
        raise ValueError("created_at_device_utc must be UTC")
    dependencies = operation.get("causal_dependencies")
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise ValueError("operation_id must be a non-empty string")
    try:
        if str(UUID(operation_id)) != operation_id.lower():
            raise ValueError("operation_id must use canonical UUID text")
    except (ValueError, AttributeError) as exc:
        raise ValueError("operation_id must be a UUID") from exc
    timestamp = operation.get("created_at_device_utc")
    if not isinstance(timestamp, str):
        raise ValueError("created_at_device_utc must be a UTC timestamp")
    try:
        parsed_timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("created_at_device_utc must be a valid UTC calendar timestamp") from exc
    if parsed_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") != timestamp:
        raise ValueError("created_at_device_utc must use canonical UTC seconds format")
    if not isinstance(dependencies, list):
        raise ValueError("causal_dependencies must be an array")
    if any(not isinstance(value, str) or not value.strip() for value in dependencies):
        raise ValueError("causal dependencies must be non-empty strings")
    if len(dependencies) != len(set(dependencies)):
        raise ValueError("causal dependencies must be unique")
    if operation_id in dependencies:
        raise ValueError("an operation cannot depend on itself")
    payload = operation.get("payload")
    expected_hash = operation.get("payload_hash")
    if not isinstance(payload, dict) or not isinstance(expected_hash, str):
        raise ValueError("operation payload and payload_hash are required")
    if not _SHA256_RE.fullmatch(expected_hash):
        raise ValueError("payload_hash must be a lowercase SHA-256 digest")
    if canonical_payload_hash(payload) != expected_hash:
        raise ValueError("payload_hash does not match canonical payload bytes")
    return True


def classify_idempotent_replay(existing_fingerprint, incoming_fingerprint):
    """Classify reuse of one operation ID without mutating either record."""
    if not isinstance(existing_fingerprint, str) or not _SHA256_RE.fullmatch(existing_fingerprint):
        raise ValueError("existing fingerprint must be a lowercase SHA-256 digest")
    if not isinstance(incoming_fingerprint, str) or not _SHA256_RE.fullmatch(incoming_fingerprint):
        raise ValueError("incoming fingerprint must be a lowercase SHA-256 digest")
    if existing_fingerprint == incoming_fingerprint:
        return "DUPLICATE"
    return "IDEMPOTENCY_KEY_REUSE"


def validate_receipt_binding(operation, receipt):
    """Ensure a receipt and its cursor belong to the exact originating operation stream."""
    if not isinstance(operation, dict) or not isinstance(receipt, dict):
        raise ValueError("operation and receipt must be objects")
    for field in ("operation_id", "device_id", "stream_id"):
        if operation.get(field) != receipt.get(field):
            raise ValueError("receipt does not match operation " + field)
    if receipt.get("operation_fingerprint") != operation_fingerprint(operation):
        raise ValueError("receipt fingerprint does not match the immutable operation")
    outcome = receipt.get("outcome")
    if outcome in ("ACCEPTED", "DUPLICATE"):
        if not isinstance(receipt.get("cursor"), str) or not receipt["cursor"].strip():
            raise ValueError("accepted receipt must carry a server cursor")
        if not isinstance(receipt.get("server_sequence"), int) or receipt["server_sequence"] < 1:
            raise ValueError("accepted receipt must carry a positive server sequence")
    elif outcome == "DEPENDENCY_PENDING":
        if receipt.get("cursor") is not None or receipt.get("server_sequence") is not None:
            raise ValueError("dependency-pending receipt cannot advance a cursor")
    else:
        if receipt.get("cursor") is not None:
            raise ValueError("non-accepted receipt cannot advance a cursor")
    return True
