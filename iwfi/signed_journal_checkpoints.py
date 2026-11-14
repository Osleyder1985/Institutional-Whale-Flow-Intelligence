"""Ed25519 signed checkpoints for independently anchored journal heads.

Private keys are supplied by the caller and must be kept outside the repository.
A signature is not a trusted timestamp, WORM guarantee, or proof of event truth.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from iwfi.append_only_journal import verify_journal

_GENESIS = "0" * 64
_CANON = "IWFI-JSON-C14N-1"
_ALGORITHM = "Ed25519"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _parse_utc(value):
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ValueError("timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc


def generate_ed25519_keypair():
    """Return PKCS8 private PEM and SubjectPublicKeyInfo public PEM bytes."""
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {"private_key_pem": private_pem, "public_key_pem": public_pem}


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


def _public_fingerprint(public_key):
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return _sha(raw)


def checkpoint_hash(checkpoint):
    return _sha(_canonical(checkpoint))


def create_signed_checkpoint(*, journal_path, journal_id, private_key_pem,
                             issued_at_utc, previous_checkpoint=None):
    """Sign the verified current journal head; caller anchors output independently."""
    _parse_utc(issued_at_utc)
    if not isinstance(journal_id, str) or not journal_id.strip():
        raise ValueError("journal_id is required")
    verification = verify_journal(journal_path)
    if verification.get("status") not in {"EMPTY", "CHAIN_VERIFIED"}:
        raise ValueError("journal must verify before checkpoint signing")
    private = _load_private(private_key_pem)
    public = private.public_key()
    previous_hash = _GENESIS
    if previous_checkpoint is not None:
        previous_result = verify_signed_checkpoint(
            previous_checkpoint, public.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo))
        if previous_result.get("status") != "SIGNATURE_VERIFIED":
            raise ValueError("previous checkpoint signature is invalid")
        if previous_checkpoint.get("journal_id") != journal_id:
            raise ValueError("previous checkpoint belongs to another journal")
        if previous_checkpoint.get("sequence", -1) >= verification["records_verified"]:
            raise ValueError("new checkpoint must advance the journal sequence")
        previous_hash = checkpoint_hash(previous_checkpoint)
    body = {
        "checkpoint_version": "1.0.0",
        "journal_id": journal_id,
        "sequence": verification["records_verified"],
        "journal_head_hash": verification["head_hash"],
        "previous_checkpoint_hash": previous_hash,
        "issued_at_utc": issued_at_utc,
        "signature_algorithm": _ALGORITHM,
        "canonicalization_version": _CANON,
        "key_fingerprint_sha256": _public_fingerprint(public),
    }
    signature = private.sign(_canonical(body)).hex()
    return {**body, "signature_hex": signature}


def verify_signed_checkpoint(checkpoint, trusted_public_key_pem, journal_path=None):
    """Verify using an independently trusted/pinned public key, never embedded trust."""
    if not isinstance(checkpoint, dict):
        return {"status": "INVALID_INPUT", "reason": "CHECKPOINT_OBJECT_REQUIRED"}
    try:
        if checkpoint.get("checkpoint_version") != "1.0.0":
            return {"status": "INVALID_INPUT", "reason": "UNSUPPORTED_CHECKPOINT_VERSION"}
        if checkpoint.get("signature_algorithm") != _ALGORITHM:
            return {"status": "INVALID_INPUT", "reason": "UNSUPPORTED_SIGNATURE_ALGORITHM"}
        if checkpoint.get("canonicalization_version") != _CANON:
            return {"status": "INVALID_INPUT", "reason": "UNSUPPORTED_CANONICALIZATION"}
        _parse_utc(checkpoint.get("issued_at_utc"))
        public = _load_public(trusted_public_key_pem)
        if checkpoint.get("key_fingerprint_sha256") != _public_fingerprint(public):
            return {"status": "SIGNATURE_INVALID", "reason": "TRUSTED_KEY_FINGERPRINT_MISMATCH"}
        signature_hex = checkpoint.get("signature_hex")
        if not isinstance(signature_hex, str):
            return {"status": "SIGNATURE_INVALID", "reason": "SIGNATURE_MISSING"}
        body = {k: v for k, v in checkpoint.items() if k != "signature_hex"}
        public.verify(bytes.fromhex(signature_hex), _canonical(body))
    except (ValueError, TypeError, KeyError):
        return {"status": "SIGNATURE_INVALID", "reason": "SIGNATURE_OR_FORMAT_INVALID"}
    result = {"status": "SIGNATURE_VERIFIED",
              "checkpoint_hash": checkpoint_hash(checkpoint),
              "sequence": checkpoint.get("sequence"),
              "journal_head_hash": checkpoint.get("journal_head_hash")}
    if journal_path is not None:
        journal_result = verify_journal(journal_path)
        if journal_result.get("status") not in {"EMPTY", "CHAIN_VERIFIED"}:
            return {"status": "JOURNAL_INVALID", "journal": journal_result}
        sequence = checkpoint.get("sequence")
        if not isinstance(sequence, int) or sequence < 0:
            return {"status": "INVALID_INPUT", "reason": "INVALID_SEQUENCE"}
        if sequence == 0:
            prefix_head = _GENESIS
        else:
            if sequence > journal_result["records_verified"]:
                return {"status": "JOURNAL_MISMATCH", "reason": "CHECKPOINT_AHEAD_OF_JOURNAL"}
            prefix_head = None
            with Path(journal_path).open("rb") as stream:
                for index, line in enumerate(stream, 1):
                    if index == sequence:
                        prefix_head = json.loads(line.decode("utf-8")).get("record_hash")
                        break
        if prefix_head != checkpoint.get("journal_head_hash"):
            return {"status": "JOURNAL_MISMATCH", "reason": "CHECKPOINT_HEAD_NOT_IN_JOURNAL"}
        result["journal_status"] = "PREFIX_HASH_MATCHED"
    return result


def verify_signed_checkpoint_chain(checkpoints, trusted_public_key_pem):
    """Verify checkpoint signatures and previous-checkpoint hash continuity."""
    if not isinstance(checkpoints, list):
        return {"status": "INVALID_INPUT", "reason": "CHECKPOINT_LIST_REQUIRED"}
    previous_hash = _GENESIS
    previous_sequence = -1
    journal_id = None
    results = []
    for checkpoint in checkpoints:
        verified = verify_signed_checkpoint(checkpoint, trusted_public_key_pem)
        if verified.get("status") != "SIGNATURE_VERIFIED":
            return {"status": "CHAIN_INVALID", "results": results, "failure": verified}
        if journal_id is None:
            journal_id = checkpoint.get("journal_id")
        if checkpoint.get("journal_id") != journal_id:
            return {"status": "CHAIN_INVALID", "reason": "JOURNAL_ID_CHANGED", "results": results}
        if checkpoint.get("previous_checkpoint_hash") != previous_hash:
            return {"status": "CHAIN_INVALID", "reason": "PREVIOUS_CHECKPOINT_HASH_MISMATCH",
                    "results": results}
        sequence = checkpoint.get("sequence")
        if not isinstance(sequence, int) or sequence <= previous_sequence:
            return {"status": "CHAIN_INVALID", "reason": "NON_MONOTONIC_SEQUENCE",
                    "results": results}
        previous_hash = verified["checkpoint_hash"]
        previous_sequence = sequence
        results.append({"sequence": sequence, "checkpoint_hash": previous_hash})
    return {"status": "CHECKPOINT_CHAIN_VERIFIED", "count": len(results), "results": results}
