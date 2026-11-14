"""Pure helpers for validating and fingerprinting offline sync operations.

This module has no network, database, credential, retry, or background behavior.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_UTC_SECONDS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


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
    """Validate semantic invariants not expressible by JSON Schema alone."""
    if not isinstance(operation, dict):
        raise ValueError("operation must be an object")

    operation_id = operation.get("operation_id")
    if not isinstance(operation_id, str):
        raise ValueError("operation_id must be a UUID")
    try:
        if str(uuid.UUID(operation_id)) != operation_id:
            raise ValueError("operation_id must use canonical UUID notation")
    except (ValueError, AttributeError) as exc:
        raise ValueError("operation_id must be a UUID") from exc

    timestamp = operation.get("created_at_device_utc")
    if not isinstance(timestamp, str) or not _UTC_SECONDS_RE.fullmatch(timestamp):
        raise ValueError("created_at_device_utc must be UTC with a Z suffix")
    try:
        parsed_timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("created_at_device_utc must be a valid UTC calendar timestamp") from exc
    if parsed_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") != timestamp:
        raise ValueError("created_at_device_utc must use canonical UTC seconds format")

    dependencies = operation.get("causal_dependencies")
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


def _validate_utc_seconds(value, field):
    """Require a real UTC calendar timestamp in canonical whole-second form."""
    if not isinstance(value, str) or not _UTC_SECONDS_RE.fullmatch(value):
        raise ValueError(field + " must be canonical UTC seconds ending in Z")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(field + " must be a valid UTC calendar timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(field + " must use canonical UTC seconds format")
    return True

def validate_receipt_semantics(receipt):
    """Validate receipt outcomes and prevent rejected/pending receipts advancing state."""
    if not isinstance(receipt, dict):
        raise ValueError("receipt must be an object")
    for field in ("operation_id", "device_id", "stream_id"):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(field + " must be a non-empty string")
    try:
        if str(uuid.UUID(receipt["operation_id"])) != receipt["operation_id"]:
            raise ValueError("receipt operation_id must use canonical UUID notation")
    except (ValueError, AttributeError) as exc:
        raise ValueError("receipt operation_id must be a UUID") from exc
    if not isinstance(receipt.get("operation_fingerprint"), str) or not _SHA256_RE.fullmatch(receipt["operation_fingerprint"]):
        raise ValueError("receipt operation_fingerprint must be a lowercase SHA-256 digest")
    _validate_utc_seconds(receipt.get("received_at_utc"), "received_at_utc")
    outcome = receipt.get("outcome")
    if outcome not in {"ACCEPTED", "DUPLICATE", "DEPENDENCY_PENDING", "REJECTED", "QUARANTINED", "CONFLICT"}:
        raise ValueError("receipt outcome is unsupported")
    sequence, cursor = receipt.get("server_sequence"), receipt.get("cursor")
    committed, reason = receipt.get("committed_at_utc"), receipt.get("reason_code")
    replay = receipt.get("idempotent_replay")
    if outcome in {"ACCEPTED", "DUPLICATE"}:
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError("accepted receipt requires a positive integer server_sequence")
        if not isinstance(cursor, str) or not cursor.strip():
            raise ValueError("accepted receipt requires a non-empty server cursor")
        _validate_utc_seconds(committed, "committed_at_utc")
        if reason is not None:
            raise ValueError("accepted receipt cannot carry a rejection reason")
        if replay is not (outcome == "DUPLICATE"):
            raise ValueError("idempotent_replay must match the receipt outcome")
    else:
        if sequence is not None or cursor is not None or committed is not None:
            raise ValueError("non-accepted receipt cannot advance or commit a server cursor")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("non-accepted receipt requires a stable reason_code")
        if replay is not False:
            raise ValueError("non-accepted receipt cannot be an idempotent replay")
    return True

def validate_cursor_semantics(cursor, device_id, stream_id, last_server_sequence=0, previous_cursor=None):
    """Validate cursor ownership, continuation shape and monotonic server progress."""
    if not isinstance(cursor, dict):
        raise ValueError("cursor must be an object")
    if cursor.get("device_id") != device_id or cursor.get("stream_id") != stream_id:
        raise ValueError("cursor does not belong to the requested device stream")
    token, sequence = cursor.get("cursor"), cursor.get("server_sequence")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("cursor token must be non-empty")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise ValueError("server_sequence must be a non-negative integer")
    if not isinstance(last_server_sequence, int) or isinstance(last_server_sequence, bool) or last_server_sequence < 0:
        raise ValueError("last_server_sequence must be a non-negative integer")
    if sequence < last_server_sequence:
        raise ValueError("server cursor cannot move backwards")
    if sequence == last_server_sequence and previous_cursor is not None and token != previous_cursor:
        raise ValueError("same server sequence cannot change its opaque cursor token")
    _validate_utc_seconds(cursor.get("issued_at_utc"), "issued_at_utc")
    terminal, next_cursor = cursor.get("terminal"), cursor.get("next_cursor")
    if not isinstance(terminal, bool):
        raise ValueError("terminal must be boolean")
    if terminal and next_cursor is not None:
        raise ValueError("terminal cursor cannot advertise a next page")
    if not terminal and (not isinstance(next_cursor, str) or not next_cursor.strip()):
        raise ValueError("non-terminal cursor requires a next page token")
    if not terminal and next_cursor == token:
        raise ValueError("non-terminal cursor cannot point to itself")
    return True
def validate_receipt_binding(operation, receipt):
    """Ensure a receipt and its cursor belong to the exact originating operation stream."""
    if not isinstance(operation, dict) or not isinstance(receipt, dict):
        raise ValueError("operation and receipt must be objects")
    validate_receipt_semantics(receipt)
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
