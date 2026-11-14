"""Pure helpers for validating and fingerprinting offline sync operations.

This module has no network, database, credential, retry, or background behavior.
"""
import hashlib
import json
import re


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
    dependencies = operation.get("causal_dependencies")
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise ValueError("operation_id must be a non-empty string")
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
