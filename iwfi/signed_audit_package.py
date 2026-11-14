"""Detached Ed25519 signatures for deterministic IWFI audit ZIP packages."""
from datetime import datetime
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

_VERSION = "1.0.0"
_ALGORITHM = "Ed25519"
_CANON = "IWFI-JSON-C14N-1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _load_private(pem):
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Ed25519 private key required")
    return key


def _load_public(pem):
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Ed25519 public key required")
    return key


def _fingerprint(public):
    raw = public.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return _sha(raw)


def _valid_time(value):
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ValueError("issued_at_utc must use YYYY-MM-DDTHH:MM:SSZ")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def sign_audit_package(*, archive_bytes, private_key_pem, issued_at_utc):
    """Sign exact ZIP bytes. Return a detached JSON-compatible signature envelope."""
    if not isinstance(archive_bytes, bytes):
        raise ValueError("archive_bytes must be bytes")
    _valid_time(issued_at_utc)
    private = _load_private(private_key_pem)
    public = private.public_key()
    body = {
        "signature_envelope_version": _VERSION,
        "artifact_type": "IWFI_AUDIT_PACKAGE_ZIP",
        "signature_algorithm": _ALGORITHM,
        "canonicalization_version": _CANON,
        "archive_media_type": "application/zip",
        "archive_size_bytes": len(archive_bytes),
        "archive_sha256": _sha(archive_bytes),
        "issued_at_utc": issued_at_utc,
        "key_fingerprint_sha256": _fingerprint(public),
    }
    return {**body, "signature_hex": private.sign(_canonical(body)).hex()}


def verify_audit_package_signature(*, archive_bytes, signature_envelope,
                                   trusted_public_key_pem):
    """Verify detached signature against a separately trusted public key."""
    if not isinstance(archive_bytes, bytes) or not isinstance(signature_envelope, dict):
        return {"status": "INVALID_INPUT", "reason": "ARCHIVE_AND_SIGNATURE_REQUIRED"}
    try:
        body = {key: value for key, value in signature_envelope.items()
                if key != "signature_hex"}
        if body.get("signature_envelope_version") != _VERSION:
            return {"status": "INVALID_INPUT", "reason": "UNSUPPORTED_SIGNATURE_VERSION"}
        if body.get("artifact_type") != "IWFI_AUDIT_PACKAGE_ZIP":
            return {"status": "INVALID_INPUT", "reason": "WRONG_ARTIFACT_TYPE"}
        if body.get("signature_algorithm") != _ALGORITHM:
            return {"status": "INVALID_INPUT", "reason": "UNSUPPORTED_SIGNATURE_ALGORITHM"}
        if body.get("canonicalization_version") != _CANON:
            return {"status": "INVALID_INPUT", "reason": "UNSUPPORTED_CANONICALIZATION"}
        if body.get("archive_media_type") != "application/zip":
            return {"status": "INVALID_INPUT", "reason": "WRONG_MEDIA_TYPE"}
        _valid_time(body.get("issued_at_utc"))
        public = _load_public(trusted_public_key_pem)
        if body.get("key_fingerprint_sha256") != _fingerprint(public):
            return {"status": "SIGNATURE_INVALID", "reason": "TRUSTED_KEY_FINGERPRINT_MISMATCH"}
        signature_hex = signature_envelope.get("signature_hex")
        if not isinstance(signature_hex, str):
            return {"status": "SIGNATURE_INVALID", "reason": "SIGNATURE_MISSING"}
        public.verify(bytes.fromhex(signature_hex), _canonical(body))
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return {"status": "SIGNATURE_INVALID", "reason": "SIGNATURE_OR_FORMAT_INVALID"}
    if body.get("archive_size_bytes") != len(archive_bytes):
        return {"status": "SIGNATURE_INVALID", "reason": "ARCHIVE_SIZE_MISMATCH"}
    if body.get("archive_sha256") != _sha(archive_bytes):
        return {"status": "SIGNATURE_INVALID", "reason": "ARCHIVE_HASH_MISMATCH"}
    return {
        "status": "SIGNATURE_VERIFIED",
        "archive_sha256": body["archive_sha256"],
        "archive_size_bytes": body["archive_size_bytes"],
        "key_fingerprint_sha256": body["key_fingerprint_sha256"],
        "issued_at_utc": body["issued_at_utc"],
    }
