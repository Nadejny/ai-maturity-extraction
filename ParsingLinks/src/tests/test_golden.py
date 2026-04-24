from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipeline_core.stages.golden import build_golden_dataset


class TestGoldenBuilder(unittest.TestCase):
    def test_golden_split_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dataset_csv = tmp / "dataset_base.csv"
            out_dir = tmp / "golden"

            rows = []
            for i in range(220):
                rows.append(
                    {
                        "doc_id": f"DOC{i:06d}",
                        "url_canonical": f"https://example.com/{i}",
                        "company": f"Company {i % 20}",
                        "industry": f"Industry {i % 5}",
                        "year": str(2020 + (i % 5)),
                        "title": f"Title {i}",
                        "text": "AI in production across functions" if i % 2 == 0 else "No AI",
                        "text_path": f"/tmp/{i}.txt",
                        "word_count": 500,
                        "text_len": 3000 + (i % 100),
                    }
                )

            pd.DataFrame(rows).to_csv(dataset_csv, index=False, encoding="utf-8")

            report = build_golden_dataset(
                dataset_base_csv=dataset_csv,
                output_dir=out_dir,
                sample_size=180,
                train_n=120,
                dev_n=30,
                test_n=30,
                qa_fraction=0.2,
                seed=42,
                guideline_version="maturity_v1.0",
            )

            self.assertEqual(report["sample_size"], 180)
            self.assertEqual(report["train_rows"], 120)
            self.assertEqual(report["dev_rows"], 30)
            self.assertEqual(report["test_rows"], 30)

            golden_df = pd.read_csv(out_dir / "golden.csv")
            self.assertEqual(golden_df.shape[0], 180)
            self.assertEqual(golden_df["doc_id"].nunique(), 180)

            train_ids = set(golden_df[golden_df["split"] == "train"]["doc_id"].astype(str).tolist())
            dev_ids = set(golden_df[golden_df["split"] == "dev"]["doc_id"].astype(str).tolist())
            test_ids = set(golden_df[golden_df["split"] == "test"]["doc_id"].astype(str).tolist())

            self.assertFalse(train_ids.intersection(dev_ids))
            self.assertFalse(train_ids.intersection(test_ids))
            self.assertFalse(dev_ids.intersection(test_ids))

            locked_ids = (out_dir / "golden_test_locked_ids.txt").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(locked_ids), 30)


if __name__ == "__main__":
    unittest.main()
