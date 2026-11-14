import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from iwfi.temporal_execution_attribution import (
    resolve_actor_identity_as_of,
    resolve_execution_participants_as_of,
    resolve_relationship_as_of,
    validate_actor_registry_v11,
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


class TemporalExecutionAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actors = json.loads((FIXTURES / "actor-registry-execution-v1.1.json").read_text(encoding="utf-8"))
        cls.claims = json.loads((FIXTURES / "execution-participant-role-claims.json").read_text(encoding="utf-8"))
        cls.trade = json.loads((FIXTURES / "trade-execution-v1.1.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT.parent / "schemas" / "actor-registry-v1.1.schema.json").read_text(encoding="utf-8"))
        cls.observation_ids = [
            "obs-eth-buyer", "obs-eth-broker", "obs-eth-venue", "obs-eth-custodian",
            "obs-eth-fund", "obs-eth-manager", "obs-eth-beneficial-owner-unknown",
        ]

    def test_v11_schema_and_synthetic_fixture_validate(self):
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(self.actors)), [])
        self.assertEqual(validate_actor_registry_v11(self.actors), [])

    def test_multi_role_resolution_requires_temporally_eligible_actor_registry(self):
        result = resolve_execution_participants_as_of(
            self.claims, self.trade, "2026-02-11T12:30:00Z", self.actors, self.observation_ids
        )
        self.assertEqual(result["status"], "RESOLVED")
        buyer = next(x for x in result["participants"] if x["participant_role"] == "BUYER")
        self.assertEqual(buyer["actor_id"], "synthetic-eth-buyer-a")
        self.assertEqual(buyer["status"], "DIRECT")

    def test_actor_discovered_after_cutoff_is_not_attributed_even_with_retroactive_validity(self):
        registry = copy.deepcopy(self.actors)
        actor = next(x for x in registry["actors"] if x["actor_id"] == "synthetic-eth-buyer-a")
        actor["known_at_utc"] = "2026-02-11T12:31:00Z"
        actor["recorded_at_utc"] = "2026-02-11T12:32:00Z"
        result = resolve_execution_participants_as_of(
            self.claims, self.trade, "2026-02-11T12:30:00Z", registry, self.observation_ids
        )
        buyer = next(x for x in result["participants"] if x["participant_role"] == "BUYER")
        self.assertEqual(buyer["status"], "UNKNOWN")
        self.assertIsNone(buyer["actor_id"])

    def test_actor_recorded_after_cutoff_is_not_attributed(self):
        registry = copy.deepcopy(self.actors)
        actor = next(x for x in registry["actors"] if x["actor_id"] == "synthetic-eth-buyer-a")
        actor["recorded_at_utc"] = "2026-02-11T12:31:00Z"
        result = resolve_actor_identity_as_of(
            registry, actor["actor_id"], "2026-02-11T12:30:00Z", self.trade["event_time_utc"]
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE_AS_OF")

    def test_historically_valid_dissolved_actor_remains_eligible_for_past_event(self):
        registry = copy.deepcopy(self.actors)
        actor = registry["actors"][0]
        actor.update({
            "valid_from_utc": "2018-01-01T00:00:00Z",
            "valid_to_utc": "2022-12-31T00:00:00Z",
            "known_at_utc": "2020-01-02T00:00:00Z",
            "recorded_at_utc": "2020-01-03T00:00:00Z",
        })
        result = resolve_actor_identity_as_of(
            registry, actor["actor_id"], "2026-01-01T00:00:00Z", "2021-06-01T00:00:00Z"
        )
        self.assertEqual(result["status"], "ELIGIBLE")

    def test_actor_not_yet_created_at_event_time_is_not_eligible(self):
        registry = copy.deepcopy(self.actors)
        actor = registry["actors"][0]
        actor["valid_from_utc"] = "2026-03-01T00:00:00Z"
        result = resolve_actor_identity_as_of(
            registry, actor["actor_id"], "2026-04-01T00:00:00Z", "2026-02-11T11:00:00Z"
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE_AS_OF")

    def test_unknown_or_disputed_actor_identity_is_not_named(self):
        for status in ("UNKNOWN", "DISPUTED"):
            registry = copy.deepcopy(self.actors)
            registry["actors"][0]["identity_status"] = status
            result = resolve_actor_identity_as_of(
                registry, registry["actors"][0]["actor_id"],
                "2026-02-11T12:30:00Z", self.trade["event_time_utc"]
            )
            self.assertEqual(result["status"], status)
            self.assertIsNone(result["actor"])

    def test_relationship_discovered_after_cutoff_is_unknown(self):
        result = resolve_relationship_as_of(
            self.actors, "synthetic-eth-manager", "synthetic-eth-fund",
            "MANAGES", "2026-02-11T12:00:01Z", self.trade["event_time_utc"]
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_disputed_relationship_does_not_enable_conclusive_link(self):
        registry = copy.deepcopy(self.actors)
        registry["relationships"][0]["status"] = "DISPUTED"
        result = resolve_relationship_as_of(
            registry, "synthetic-eth-manager", "synthetic-eth-fund",
            "MANAGES", "2026-02-11T12:30:00Z", self.trade["event_time_utc"]
        )
        self.assertEqual(result["status"], "DISPUTED")

    def test_duplicate_actor_ids_fail_closed(self):
        registry = copy.deepcopy(self.actors)
        registry["actors"].append(copy.deepcopy(registry["actors"][0]))
        result = resolve_execution_participants_as_of(
            self.claims, self.trade, "2026-02-11T12:30:00Z", registry, self.observation_ids
        )
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["participants"], [])

    def test_registry_without_recorded_at_on_relationship_fails_closed(self):
        registry = copy.deepcopy(self.actors)
        del registry["relationships"][0]["recorded_at_utc"]
        self.assertTrue(validate_actor_registry_v11(registry))


if __name__ == "__main__":
    unittest.main()
