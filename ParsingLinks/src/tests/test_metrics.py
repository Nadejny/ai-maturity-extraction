from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipeline_core.metrics import (
    compute_multilabel_macro_micro_f1,
    evidence_span_overlap,
    weighted_kappa,
)


class TestMetrics(unittest.TestCase):
    def test_weighted_kappa_perfect(self) -> None:
        gold = [0, 1, 2, 3, 4]
        pred = [0, 1, 2, 3, 4]
        self.assertAlmostEqual(weighted_kappa(gold, pred), 1.0, places=6)

    def test_multilabel_f1(self) -> None:
        gold_payload = {
            "ai_use_cases": {"items": ["chatbot", "forecasting"]},
            "adoption_patterns": {"items": ["pilot"]},
            "ai_stack": {"items": []},
            "kpi_signals": {"items": []},
            "budget_signals": {"items": []},
            "org_change_signals": {"items": []},
            "risk_signals": {"items": []},
            "roadmap_signals": {"items": []},
        }
        pred_payload = {
            "ai_use_cases": {"items": ["chatbot"]},
            "adoption_patterns": {"items": ["pilot", "platform"]},
            "ai_stack": {"items": []},
            "kpi_signals": {"items": []},
            "budget_signals": {"items": []},
            "org_change_signals": {"items": []},
            "risk_signals": {"items": []},
            "roadmap_signals": {"items": []},
        }

        metrics = compute_multilabel_macro_micro_f1([(gold_payload, pred_payload)])
        self.assertGreaterEqual(metrics["micro_f1"], 0.0)
        self.assertLessEqual(metrics["micro_f1"], 1.0)

    def test_span_overlap(self) -> None:
        gold = [{"field": "deployment_scope", "quote": "in production", "start_char": 10, "end_char": 30}]
        pred = [{"field": "deployment_scope", "quote": "production", "start_char": 12, "end_char": 28}]
        score = evidence_span_overlap(gold, pred)
        self.assertGreater(score, 0.4)


if __name__ == "__main__":
    unittest.main()
