import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from iwfi.actor_registry import validate_actor_registry, resolve_actor_alias, resolve_relationship

ROOT = Path(__file__).resolve().parent

class ActorRegistryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "fixtures" / "actor-registry.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT.parent / "schemas" / "actor-registry.schema.json").read_text(encoding="utf-8"))

    def test_schema_is_valid_and_all_actor_records_validate(self):
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        for actor in self.registry["actors"]:
            self.assertEqual(list(validator.iter_errors(actor)), [])

    def test_multiple_aliases_and_distinct_fund_manager_records_are_preserved(self):
        ids = {item["actor_id"] for item in self.registry["actors"]}
        self.assertIn("actor-manager-northstar", ids)
        self.assertIn("actor-fund-northstar-btc", ids)
        self.assertNotEqual("actor-manager-northstar", "actor-fund-northstar-btc")

    def test_alias_collision_is_ambiguous_not_first_match_wins(self):
        result = resolve_actor_alias(self.registry, "Atlas", "2025-01-01T00:00:00Z", "BRAND", "global")
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertEqual(result["actor_ids"], ["actor-atlas-one", "actor-atlas-two"])

    def test_unknown_alias_remains_unknown(self):
        self.assertEqual(resolve_actor_alias(self.registry, "No such actor", "2025-01-01T00:00:00Z")["status"], "UNKNOWN")

    def test_future_known_alias_is_not_visible_in_historical_as_of_query(self):
        result = resolve_actor_alias(self.registry, "Atlas", "2024-01-02T12:00:00Z", "BRAND", "global")
        self.assertEqual(result["status"], "UNIQUE")
        self.assertEqual(result["actor_ids"], ["actor-atlas-one"])

    def test_disbanded_actor_is_not_active_after_valid_to(self):
        result = resolve_actor_alias(self.registry, "Closed BTC Vehicle", "2022-01-01T00:00:00Z")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_contradictory_relationship_claims_are_reported_and_not_resolved_by_order(self):
        errors = validate_actor_registry(self.registry)
        self.assertTrue(any("contradictory relationship claims" in error for error in errors))
        result = resolve_relationship(self.registry, "actor-manager-northstar", "actor-fund-northstar-btc", "MANAGES", "2024-03-01T00:00:00Z")
        self.assertEqual(result["status"], "DISPUTED")

    def test_invalid_temporal_interval_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["actors"][0]["valid_from_utc"] = "2025-01-01T00:00:00Z"
        registry["actors"][0]["valid_to_utc"] = "2024-01-01T00:00:00Z"
        self.assertTrue(any("validity interval ends before it starts" in error for error in validate_actor_registry(registry)))

    def test_duplicate_actor_ids_are_rejected_deterministically(self):
        registry = copy.deepcopy(self.registry)
        registry["actors"].append(copy.deepcopy(registry["actors"][0]))
        self.assertTrue(any("duplicate actor_id" in error for error in validate_actor_registry(registry)))

if __name__ == "__main__":
    unittest.main()
