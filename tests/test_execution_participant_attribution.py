import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from iwfi.execution_attribution import validate_execution_attributions, resolve_execution_participant

ROOT = Path(__file__).resolve().parent

class ExecutionParticipantAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "fixtures" / "execution-participant-attributions.json").read_text(encoding="utf-8"))
        cls.executions = json.loads((ROOT / "fixtures" / "trade-executions.json").read_text(encoding="utf-8"))
        cls.actors = json.loads((ROOT / "fixtures" / "actor-registry.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT.parent / "schemas" / "execution-participant-attribution.schema.json").read_text(encoding="utf-8"))
        cls.actor_ids = [x["actor_id"] for x in cls.actors["actors"]]
        cls.observation_ids = ["official-execution-disclosure-eth-001"]

    def test_schema_and_synthetic_direct_and_unknown_claims_validate(self):
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(self.registry)), [])
        self.assertEqual(validate_execution_attributions(self.registry, self.executions, self.actor_ids, self.observation_ids), [])

    def test_direct_participant_is_hidden_before_known_at(self):
        execution = self.executions[1]
        result = resolve_execution_participant(self.registry, execution, "2026-02-11T11:15:00Z")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["actor_id"])

    def test_direct_participant_resolves_only_after_known_at(self):
        execution = self.executions[1]
        result = resolve_execution_participant(self.registry, execution, "2026-02-11T12:00:00Z")
        self.assertEqual(result["status"], "DIRECT")
        self.assertEqual(result["actor_id"], "actor-fund-northstar-btc")
        self.assertEqual(result["participant_side"], "BUY")

    def test_unknown_participant_remains_unknown_even_when_execution_is_confirmed(self):
        result = resolve_execution_participant(self.registry, self.executions[0], "2026-01-10T10:00:10Z")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["actor_id"])

    def test_conflicting_actor_claims_resolve_to_disputed(self):
        registry = copy.deepcopy(self.registry)
        claim = copy.deepcopy(registry["claims"][0])
        claim["attribution_id"] = "claim-execution-eth-conflict"
        claim["actor_id"] = "actor-manager-northstar"
        claim["participant_side"] = "SELL"
        claim["supporting_evidence"][0]["record_ref"] = "synthetic:eth:conflict"
        registry["claims"].append(claim)
        result = resolve_execution_participant(registry, self.executions[1], "2026-02-11T13:00:00Z")
        self.assertEqual(result["status"], "DISPUTED")
        self.assertIsNone(result["actor_id"])

    def test_provider_label_alone_cannot_support_direct_execution_attribution(self):
        registry = copy.deepcopy(self.registry)
        claim = registry["claims"][0]
        claim["supporting_evidence"][0]["evidence_type"] = "PROVIDER_ATTRIBUTION"
        errors = validate_execution_attributions(registry, self.executions, self.actor_ids, self.observation_ids)
        self.assertTrue(any("lacks participant-specific evidence" in x for x in errors))

    def test_validity_interval_must_cover_execution_time(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["valid_to_utc"] = "2026-02-10T00:00:00Z"
        errors = validate_execution_attributions(registry, self.executions, self.actor_ids, self.observation_ids)
        self.assertTrue(any("validity interval does not cover execution event time" in x for x in errors))

    def test_recorded_time_cannot_precede_known_time(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["recorded_at_utc"] = "2026-02-11T11:00:00Z"
        errors = validate_execution_attributions(registry, self.executions, self.actor_ids, self.observation_ids)
        self.assertTrue(any("recorded_at_utc precedes known_at_utc" in x for x in errors))

    def test_unknown_cannot_select_actor_or_side(self):
        registry = copy.deepcopy(self.registry)
        unknown = copy.deepcopy(registry["claims"][0])
        unknown["attribution_id"] = "claim-btc-unknown-invalid"
        unknown["execution_id"] = "btc-execution-001"
        unknown["actor_id"] = "actor-fund-northstar-btc"
        unknown["attribution_status"] = "UNKNOWN"
        unknown["participant_side"] = "UNKNOWN"
        unknown["attribution_method"] = "NONE"
        unknown["valid_from_utc"] = None
        unknown["valid_to_utc"] = None
        unknown["source_observation_ids"] = []
        unknown["supporting_evidence"] = []
        registry["claims"].append(unknown)
        errors = validate_execution_attributions(registry, self.executions, self.actor_ids, self.observation_ids)
        self.assertTrue(any("UNKNOWN attribution" in x for x in errors))

    def test_transfer_reference_cannot_resolve_as_trade_execution(self):
        registry = copy.deepcopy(self.registry)
        registry["claims"][0]["execution_id"] = "movement-btc-synthetic-001"
        errors = validate_execution_attributions(registry, self.executions, self.actor_ids, self.observation_ids)
        self.assertTrue(any("execution not found" in x for x in errors))

if __name__ == "__main__":
    unittest.main()
