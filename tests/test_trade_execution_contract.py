import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from iwfi.trade_execution import validate_trade_execution

ROOT = Path(__file__).resolve().parent

class TradeExecutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executions = json.loads((ROOT / "fixtures" / "trade-executions.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((ROOT / "fixtures" / "trade-execution-evidence.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT.parent / "schemas" / "trade-execution.schema.json").read_text(encoding="utf-8"))
        cls.evidence_ids = [item["evidence_id"] for item in cls.evidence]

    def test_schema_is_valid_and_synthetic_btc_eth_executions_validate(self):
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        for execution in self.executions:
            self.assertEqual(list(validator.iter_errors(execution)), [])
            self.assertEqual(validate_trade_execution(execution, self.evidence_ids, {"actor-fund-northstar-btc"}), [])

    def test_confirmed_execution_can_have_unknown_participant(self):
        execution = self.executions[0]
        self.assertEqual(execution["execution_status"], "EXECUTED")
        self.assertEqual(execution["participant_attribution_status"], "UNKNOWN")
        self.assertIsNone(execution["participant_actor_id"])
        self.assertEqual(execution["aggressor_side"], "BUY")

    def test_aggressor_side_does_not_overwrite_participant_side(self):
        execution = self.executions[1]
        self.assertEqual(execution["aggressor_side"], "SELL")
        self.assertEqual(execution["participant_side"], "BUY")

    def test_transfer_and_aggregate_flows_cannot_be_execution_evidence(self):
        for forbidden in ("ON_CHAIN_TRANSFER", "EXCHANGE_FLOW_METRIC", "ETF_FLOW_METRIC", "HOLDING_CHANGE", "AGGREGATED_REPORT", "ORDER"):
            execution = copy.deepcopy(self.executions[0])
            execution["source_evidence"][0]["evidence_type"] = forbidden
            errors = validate_trade_execution(execution, self.evidence_ids)
            self.assertTrue(any("non-execution evidence is inadmissible" in error for error in errors), forbidden)

    def test_aggregate_record_cannot_become_individual_execution(self):
        execution = copy.deepcopy(self.executions[0])
        execution["aggregation_level"] = "AGGREGATED_REPORT"
        self.assertIn("only INDIVIDUAL_EXECUTION is admissible", validate_trade_execution(execution, self.evidence_ids))

    def test_order_or_transfer_event_type_is_rejected(self):
        for value in ("ORDER", "ON_CHAIN_TRANSFER", "ETF_FLOW", "HOLDING_CHANGE"):
            execution = copy.deepcopy(self.executions[0])
            execution["event_type"] = value
            self.assertIn("event_type must be TRADE_EXECUTION", validate_trade_execution(execution, self.evidence_ids))

    def test_missing_evidence_reference_is_rejected(self):
        execution = copy.deepcopy(self.executions[0])
        execution["source_observation_ids"] = ["not-present"]
        self.assertTrue(any("source execution evidence not found" in error for error in validate_trade_execution(execution, self.evidence_ids)))

    def test_unknown_participant_cannot_be_assigned_an_actor_or_side(self):
        execution = copy.deepcopy(self.executions[0])
        execution["participant_actor_id"] = "actor-fund-northstar-btc"
        self.assertTrue(any("UNKNOWN participant attribution" in error for error in validate_trade_execution(execution, self.evidence_ids)))

    def test_temporal_ordering_is_enforced(self):
        execution = copy.deepcopy(self.executions[0])
        execution["ingested_at_utc"] = "2026-01-10T09:00:00Z"
        self.assertIn("execution timestamps are not chronological", validate_trade_execution(execution, self.evidence_ids))

    def test_float_and_exponential_amounts_are_rejected(self):
        for value in (1.5, "1e3", "01.2"):
            execution = copy.deepcopy(self.executions[0])
            execution["base_quantity"] = value
            self.assertTrue(any("invalid canonical decimal: base_quantity" in error for error in validate_trade_execution(execution, self.evidence_ids)))

if __name__ == "__main__":
    unittest.main()
