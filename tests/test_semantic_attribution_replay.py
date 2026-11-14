import copy
import json
from pathlib import Path
import tempfile
import unittest

from iwfi.semantic_attribution_replay import (
    replay_execution_participants,
    verify_execution_replay,
)


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
HISTORICAL_CUTOFF = "2026-02-11T12:30:00Z"
CORRECTION_CUTOFF = "2026-02-12T12:00:00Z"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class SemanticAttributionReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actor_registry = load_fixture("actor-registry-execution-v1.1.json")
        cls.claim_registry = load_fixture("execution-participant-role-claims.json")
        cls.trade = load_fixture("trade-execution-v1.1.json")
        cls.observation_ids = [
            "obs-eth-buyer", "obs-eth-broker", "obs-eth-venue",
            "obs-eth-custodian", "obs-eth-fund", "obs-eth-manager",
            "obs-eth-beneficial-owner-unknown",
        ]

    def _replay(self, cutoff, claims=None, actors=None):
        return replay_execution_participants(
            trade=copy.deepcopy(self.trade),
            claim_registry=copy.deepcopy(claims if claims is not None else self.claim_registry),
            actor_registry=copy.deepcopy(actors if actors is not None else self.actor_registry),
            observation_ids=list(self.observation_ids),
            knowledge_cutoff_utc=cutoff,
        )

    def test_same_frozen_inputs_regenerate_identical_semantic_result(self):
        first = self._replay(HISTORICAL_CUTOFF)
        second = self._replay(HISTORICAL_CUTOFF)
        self.assertEqual(first, second)
        self.assertEqual(first["result"]["status"], "RESOLVED")
        buyer = next(x for x in first["result"]["participants"] if x["participant_role"] == "BUYER")
        self.assertEqual(buyer["actor_id"], "synthetic-eth-buyer-a")
        self.assertEqual(buyer["status"], "DIRECT")

    def test_replay_record_binds_all_inputs_and_detects_substitution(self):
        replay = self._replay(HISTORICAL_CUTOFF)
        verified = verify_execution_replay(
            replay=replay, trade=self.trade, claim_registry=self.claim_registry,
            actor_registry=self.actor_registry, observation_ids=self.observation_ids,
        )
        self.assertEqual(verified["status"], "SEMANTIC_REPLAY_VERIFIED")
        changed_trade = copy.deepcopy(self.trade)
        changed_trade["aggressor_side"] = "BUY"
        substituted = verify_execution_replay(
            replay=replay, trade=changed_trade, claim_registry=self.claim_registry,
            actor_registry=self.actor_registry, observation_ids=self.observation_ids,
        )
        self.assertEqual(substituted["status"], "REPLAY_INPUT_MISMATCH")

    def test_later_claim_correction_changes_current_view_not_historical_replay(self):
        historical = self._replay(HISTORICAL_CUTOFF)
        corrected_registry = copy.deepcopy(self.claim_registry)
        buyer = next(x for x in corrected_registry["claims"] if x["participant_role"] == "BUYER")
        buyer.update({
            "actor_id": None,
            "candidate_actor_ids": [],
            "participant_side": "UNKNOWN",
            "epistemic_status": "UNKNOWN",
            "attribution_method": "NONE",
            "known_at_utc": "2026-02-12T11:00:00Z",
            "recorded_at_utc": "2026-02-12T11:00:01Z",
            "source_observation_ids": ["obs-eth-buyer"],
            "supporting_evidence": [],
            "counter_evidence": [],
        })
        current = self._replay(CORRECTION_CUTOFF, claims=corrected_registry)
        historical_again = self._replay(HISTORICAL_CUTOFF)

        old_buyer = next(x for x in historical["result"]["participants"] if x["participant_role"] == "BUYER")
        new_buyer = next(x for x in current["result"]["participants"] if x["participant_role"] == "BUYER")
        self.assertEqual(old_buyer["status"], "DIRECT")
        self.assertEqual(old_buyer["actor_id"], "synthetic-eth-buyer-a")
        self.assertEqual(new_buyer["status"], "UNKNOWN")
        self.assertIsNone(new_buyer["actor_id"])
        self.assertEqual(historical["replay_hash"], historical_again["replay_hash"])
        self.assertNotEqual(historical["result_hash"], current["result_hash"])

    def test_changed_actor_registry_changes_replay_input_binding(self):
        original = self._replay(HISTORICAL_CUTOFF)
        changed_actors = copy.deepcopy(self.actor_registry)
        actor = next(x for x in changed_actors["actors"] if x["actor_id"] == "synthetic-eth-buyer-a")
        actor["identity_status"] = "INFERRED"
        changed = self._replay(HISTORICAL_CUTOFF, actors=changed_actors)
        self.assertNotEqual(original["input_hashes"]["actor_registry"], changed["input_hashes"]["actor_registry"])
        buyer = next(x for x in changed["result"]["participants"] if x["participant_role"] == "BUYER")
        self.assertEqual(buyer["status"], "INFERRED")

    def test_modified_replay_record_fails_integrity(self):
        replay = self._replay(HISTORICAL_CUTOFF)
        replay["result"]["participants"][0]["status"] = "VERIFIED"
        result = verify_execution_replay(
            replay=replay, trade=self.trade, claim_registry=self.claim_registry,
            actor_registry=self.actor_registry, observation_ids=self.observation_ids,
        )
        self.assertEqual(result["status"], "REPLAY_RECORD_HASH_MISMATCH")


if __name__ == "__main__":
    unittest.main()
