"""Step 2: build stratified golden dataset scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_core.stages.golden import build_golden_dataset


def main() -> None:
    src_root = Path(__file__).resolve().parents[1]

    ap = argparse.ArgumentParser(description="Create stratified golden dataset scaffold")
    ap.add_argument(
        "--dataset_base_csv",
        type=str,
        default=str(src_root / "artifacts" / "data" / "dataset_base.csv"),
    )
    ap.add_argument(
        "--output_dir",
        type=str,
        default=str(src_root / "artifacts" / "golden"),
    )
    ap.add_argument("--sample_size", type=int, default=180)
    ap.add_argument("--train_n", type=int, default=120)
    ap.add_argument("--dev_n", type=int, default=30)
    ap.add_argument("--test_n", type=int, default=30)
    ap.add_argument("--qa_fraction", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--guideline_version", type=str, default="maturity_v1.0")
    args = ap.parse_args()

    report = build_golden_dataset(
        dataset_base_csv=args.dataset_base_csv,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        train_n=args.train_n,
        dev_n=args.dev_n,
        test_n=args.test_n,
        qa_fraction=args.qa_fraction,
        seed=args.seed,
        guideline_version=args.guideline_version,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
