from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipeline_core.schema import normalize_extraction_payload


class TestSchemaNormalization(unittest.TestCase):
    def test_normalize_invalid_status_and_ranges(self) -> None:
        raw = {
            "ai_use_cases": {"status": "maybe", "items": ["Chatbot", "chatbot", ""]},
            "deployment_scope": {"status": "present", "value": "production"},
            "maturity_level": 12,
            "confidence": 2.0,
            "evidence_spans": [{"field": "deployment_scope", "quote": "In production"}],
        }
        payload, errors = normalize_extraction_payload(raw)

        self.assertEqual(payload["ai_use_cases"]["status"], "uncertain")
        self.assertEqual(payload["ai_use_cases"]["items"], ["Chatbot"])
        self.assertEqual(payload["maturity_level"], 4)
        self.assertEqual(payload["confidence"], 1.0)
        self.assertIsInstance(errors, list)

    def test_empty_string_payload(self) -> None:
        payload, errors = normalize_extraction_payload("")
        self.assertEqual(payload["maturity_level"], 0)
        self.assertEqual(payload["deployment_scope"]["status"], "uncertain")
        self.assertIsInstance(errors, list)


if __name__ == "__main__":
    unittest.main()
