"""Step 5: build final analytics dataset from best model predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_core.stages.final_dataset import build_final_dataset


def main() -> None:
    src_root = Path(__file__).resolve().parents[1]

    ap = argparse.ArgumentParser(description="Build final analytics dataset from best model predictions")
    ap.add_argument(
        "--dataset_base_csv",
        type=str,
        default=str(src_root / "artifacts" / "data" / "dataset_base.csv"),
    )
    ap.add_argument(
        "--inference_run_dir",
        type=str,
        required=True,
        help="path to one concrete run folder inside artifacts/inference_runs",
    )
    ap.add_argument(
        "--leaderboard_csv",
        type=str,
        default=str(src_root / "artifacts" / "evaluation" / "leaderboard.csv"),
    )
    ap.add_argument("--model_alias", type=str, default="")
    ap.add_argument(
        "--output_csv",
        type=str,
        default=str(src_root / "artifacts" / "final" / "final_analytics_dataset.csv"),
    )
    ap.add_argument(
        "--output_jsonl",
        type=str,
        default=str(src_root / "artifacts" / "final" / "final_analytics_dataset.jsonl"),
    )
    args = ap.parse_args()

    summary = build_final_dataset(
        dataset_base_csv=args.dataset_base_csv,
        inference_run_dir=args.inference_run_dir,
        output_csv=args.output_csv,
        output_jsonl=args.output_jsonl,
        model_alias=args.model_alias or None,
        leaderboard_csv=args.leaderboard_csv or None,
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
