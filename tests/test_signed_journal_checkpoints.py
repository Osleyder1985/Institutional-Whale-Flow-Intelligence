import tempfile
import unittest
from pathlib import Path

from iwfi.append_only_journal import AppendOnlyJournal
from iwfi.signed_journal_checkpoints import (
    create_signed_checkpoint, generate_ed25519_keypair,
    verify_signed_checkpoint, verify_signed_checkpoint_chain,
)


class SignedJournalCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.keys = generate_ed25519_keypair()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal.jsonl"
        self.journal = AppendOnlyJournal(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def checkpoint(self, previous=None):
        return create_signed_checkpoint(
            journal_path=self.path, journal_id="synthetic-iwfi-journal",
            private_key_pem=self.keys["private_key_pem"],
            issued_at_utc="2026-11-12T12:00:00Z",
            previous_checkpoint=previous,
        )

    def test_signed_checkpoint_and_journal_prefix_verify(self):
        self.journal.append({"event_id": "evt-1", "kind": "SNAPSHOT"})
        checkpoint = self.checkpoint()
        result = verify_signed_checkpoint(checkpoint, self.keys["public_key_pem"], self.path)
        self.assertEqual(result["status"], "SIGNATURE_VERIFIED")
        self.assertEqual(result["journal_status"], "PREFIX_HASH_MATCHED")

    def test_signature_tampering_is_detected(self):
        self.journal.append({"event_id": "evt-1"})
        checkpoint = self.checkpoint()
        checkpoint["journal_head_hash"] = "f" * 64
        self.assertEqual(verify_signed_checkpoint(
            checkpoint, self.keys["public_key_pem"])["status"], "SIGNATURE_INVALID")

    def test_wrong_trusted_public_key_is_rejected(self):
        self.journal.append({"event_id": "evt-1"})
        other = generate_ed25519_keypair()
        checkpoint = self.checkpoint()
        self.assertEqual(verify_signed_checkpoint(
            checkpoint, other["public_key_pem"])["status"], "SIGNATURE_INVALID")

    def test_checkpoint_chain_links_signed_checkpoints(self):
        self.journal.append({"event_id": "evt-1"})
        first = self.checkpoint()
        self.journal.append({"event_id": "evt-2"})
        second = self.checkpoint(previous=first)
        result = verify_signed_checkpoint_chain(
            [first, second], self.keys["public_key_pem"])
        self.assertEqual(result["status"], "CHECKPOINT_CHAIN_VERIFIED")
        self.assertEqual(result["count"], 2)

    def test_checkpoint_chain_rejects_reordered_or_missing_anchor(self):
        self.journal.append({"event_id": "evt-1"})
        first = self.checkpoint()
        self.journal.append({"event_id": "evt-2"})
        second = self.checkpoint(previous=first)
        result = verify_signed_checkpoint_chain(
            [second, first], self.keys["public_key_pem"])
        self.assertEqual(result["status"], "CHAIN_INVALID")

    def test_checkpoint_must_match_journal_prefix(self):
        self.journal.append({"event_id": "evt-1"})
        checkpoint = self.checkpoint()
        self.journal.append({"event_id": "evt-2"})
        result = verify_signed_checkpoint(
            checkpoint, self.keys["public_key_pem"], self.path)
        self.assertEqual(result["journal_status"], "PREFIX_HASH_MATCHED")

    def test_cannot_sign_corrupt_journal(self):
        self.journal.append({"event_id": "evt-1"})
        self.path.write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "journal must verify"):
            self.checkpoint()


if __name__ == "__main__":
    unittest.main()
