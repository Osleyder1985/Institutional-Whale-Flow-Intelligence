"""Durable local append-only journal with a verifiable hash chain.

This is a single-writer reference implementation, not WORM storage. A privileged
operator can rewrite the whole file and recompute hashes; independent anchoring
or signatures are required to detect that threat.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

_GENESIS = "0" * 64
_HASH = re.compile(r"^[a-f0-9]{64}$")
_CANONICALIZATION = "IWFI-JSON-C14N-1"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_hash(sequence: int, previous_hash: str, event: dict) -> str:
    return _sha256(_canonical_bytes({
        "canonicalization": _CANONICALIZATION,
        "sequence": sequence,
        "previous_record_hash": previous_hash,
        "event": event,
    }))


def verify_journal(path: str | os.PathLike) -> dict:
    """Verify every line, sequence, hash link, and unique event ID."""
    journal = Path(path)
    if not journal.exists():
        return {"status": "EMPTY", "records_verified": 0, "head_hash": _GENESIS}
    if not journal.is_file():
        return {"status": "INVALID_JOURNAL_PATH", "records_verified": 0}
    previous_hash = _GENESIS
    seen_ids = set()
    count = 0
    try:
        with journal.open("rb") as stream:
            for line_number, raw_line in enumerate(stream, 1):
                if not raw_line.endswith(b"\n"):
                    return {"status": "TRUNCATED_LINE", "line": line_number,
                            "records_verified": count}
                try:
                    envelope = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return {"status": "INVALID_RECORD_ENCODING", "line": line_number,
                            "records_verified": count}
                if not isinstance(envelope, dict) or set(envelope) != {
                    "canonicalization", "sequence", "previous_record_hash",
                    "event", "record_hash"
                }:
                    return {"status": "INVALID_ENVELOPE", "line": line_number,
                            "records_verified": count}
                event = envelope["event"]
                event_id = event.get("event_id") if isinstance(event, dict) else None
                if envelope["canonicalization"] != _CANONICALIZATION:
                    status = "UNSUPPORTED_CANONICALIZATION"
                elif envelope["sequence"] != count + 1:
                    status = "SEQUENCE_MISMATCH"
                elif envelope["previous_record_hash"] != previous_hash:
                    status = "CHAIN_LINK_MISMATCH"
                elif not isinstance(event_id, str) or not event_id.strip():
                    status = "INVALID_EVENT_ID"
                elif event_id in seen_ids:
                    status = "DUPLICATE_EVENT_ID"
                elif not isinstance(envelope["record_hash"], str) or not _HASH.fullmatch(envelope["record_hash"]):
                    status = "INVALID_RECORD_HASH"
                else:
                    expected = _record_hash(count + 1, previous_hash, event)
                    status = "HASH_MISMATCH" if expected != envelope["record_hash"] else "OK"
                if status != "OK":
                    return {"status": status, "line": line_number,
                            "records_verified": count}
                seen_ids.add(event_id)
                previous_hash = envelope["record_hash"]
                count += 1
    except OSError as exc:
        return {"status": "JOURNAL_IO_ERROR", "error": type(exc).__name__,
                "records_verified": count}
    return {"status": "CHAIN_VERIFIED", "records_verified": count,
            "head_hash": previous_hash}


class AppendOnlyJournal:
    """Append JSON events and fsync each line; one writer process is assumed."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)

    def append(self, event: dict) -> dict:
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        # Validate JSON compatibility before opening the journal for append.
        _canonical_bytes(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        verification = verify_journal(self.path)
        if verification["status"] not in {"EMPTY", "CHAIN_VERIFIED"}:
            raise ValueError("journal verification failed: " + verification["status"])
        existing = self.read_events()
        if any(item.get("event_id") == event_id for item in existing):
            raise ValueError("event_id is immutable and cannot be reused")
        sequence = verification["records_verified"] + 1
        previous_hash = verification["head_hash"]
        record_hash = _record_hash(sequence, previous_hash, event)
        envelope = {
            "canonicalization": _CANONICALIZATION,
            "sequence": sequence,
            "previous_record_hash": previous_hash,
            "event": event,
            "record_hash": record_hash,
        }
        encoded = _canonical_bytes(envelope) + b"\n"
        with self.path.open("ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return {"sequence": sequence, "record_hash": record_hash}

    def read_events(self) -> list[dict]:
        verification = verify_journal(self.path)
        if verification["status"] == "EMPTY":
            return []
        if verification["status"] != "CHAIN_VERIFIED":
            raise ValueError("journal verification failed: " + verification["status"])
        events = []
        with self.path.open("rb") as stream:
            for line in stream:
                events.append(json.loads(line.decode("utf-8"))["event"])
        return events
