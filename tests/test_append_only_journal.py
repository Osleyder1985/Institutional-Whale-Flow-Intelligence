import json
from pathlib import Path
import tempfile
import unittest

from iwfi.append_only_journal import AppendOnlyJournal, verify_journal


class AppendOnlyJournalTests(unittest.TestCase):
    def test_empty_journal_and_durable_append_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger" / "events.jsonl"
            self.assertEqual(verify_journal(path)["status"], "EMPTY")
            journal = AppendOnlyJournal(path)
            first = journal.append({"event_id": "evt-1", "kind": "SNAPSHOT_RECORDED"})
            second = journal.append({"event_id": "evt-2", "kind": "SNAPSHOT_CORRECTED",
                                     "supersedes_event_id": "evt-1"})
            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(verify_journal(path)["status"], "CHAIN_VERIFIED")
            self.assertEqual([e["event_id"] for e in journal.read_events()], ["evt-1", "evt-2"])

    def test_event_ids_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = AppendOnlyJournal(Path(directory) / "events.jsonl")
            journal.append({"event_id": "evt-1"})
            with self.assertRaisesRegex(ValueError, "cannot be reused"):
                journal.append({"event_id": "evt-1", "kind": "different"})

    def test_modified_record_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            AppendOnlyJournal(path).append({"event_id": "evt-1", "value": "original"})
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["event"]["value"] = "modified"
            path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")
            self.assertEqual(verify_journal(path)["status"], "HASH_MISMATCH")

    def test_reordered_records_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            journal = AppendOnlyJournal(path)
            journal.append({"event_id": "evt-1"})
            journal.append({"event_id": "evt-2"})
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")
            self.assertIn(verify_journal(path)["status"], {"SEQUENCE_MISMATCH", "CHAIN_LINK_MISMATCH"})

    def test_truncated_final_line_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            AppendOnlyJournal(path).append({"event_id": "evt-1"})
            path.write_bytes(path.read_bytes().rstrip(b"\n"))
            self.assertEqual(verify_journal(path)["status"], "TRUNCATED_LINE")

    def test_duplicate_event_ids_in_file_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            journal = AppendOnlyJournal(path)
            journal.append({"event_id": "evt-1"})
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["sequence"] = 2
            envelope["previous_record_hash"] = envelope["record_hash"]
            # Duplicate-ID detection is reached only after a valid second hash.
            from iwfi.append_only_journal import _record_hash
            envelope["record_hash"] = _record_hash(2, envelope["previous_record_hash"], envelope["event"])
            with path.open("ab") as stream:
                stream.write(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            self.assertEqual(verify_journal(path)["status"], "DUPLICATE_EVENT_ID")

    def test_non_json_values_fail_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with self.assertRaises(ValueError):
                AppendOnlyJournal(path).append({"event_id": "evt-1", "not_json": float("nan")})
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
