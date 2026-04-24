"""Step 4: evaluate benchmark quality vs golden split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_core.stages.evaluation import evaluate_run


def main() -> None:
    src_root = Path(__file__).resolve().parents[1]

    ap = argparse.ArgumentParser(description="Evaluate benchmark quality vs golden split")
    ap.add_argument(
        "--golden_jsonl",
        type=str,
        default=str(src_root / "artifacts" / "golden" / "golden.jsonl"),
    )
    ap.add_argument(
        "--inference_run_dir",
        type=str,
        required=True,
        help="path to one concrete run folder inside artifacts/inference_runs",
    )
    ap.add_argument(
        "--output_dir",
        type=str,
        default=str(src_root / "artifacts" / "evaluation"),
    )
    ap.add_argument("--split", type=str, default="test")
    ap.add_argument("--strict_weight", type=float, default=0.70)
    ap.add_argument("--semantic_weight", type=float, default=0.30)
    ap.add_argument("--judge_model_registry", type=str, default="")
    ap.add_argument("--judge_model_alias", type=str, default="")
    ap.add_argument("--judge_settings", type=str, default="")
    args = ap.parse_args()

    summary = evaluate_run(
        golden_jsonl=args.golden_jsonl,
        inference_run_dir=args.inference_run_dir,
        output_dir=args.output_dir,
        split=args.split,
        strict_weight=args.strict_weight,
        semantic_weight=args.semantic_weight,
        judge_model_registry_path=args.judge_model_registry or None,
        judge_model_alias=args.judge_model_alias or None,
        judge_settings_path=args.judge_settings or None,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
