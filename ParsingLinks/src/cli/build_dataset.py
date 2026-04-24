"""Step 1: build the immutable dataset_base from the merged scraping CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_core.stages.dataset import build_dataset_base


def main() -> None:
    src_root = Path(__file__).resolve().parents[1]
    project_root = src_root.parent

    ap = argparse.ArgumentParser(description="Build immutable dataset_base from parsed corpus")
    ap.add_argument(
        "--input_csv",
        type=str,
        default=str(project_root / "out" / "final" / "best_per_url_export.csv"),
    )
    ap.add_argument(
        "--output_csv",
        type=str,
        default=str(src_root / "artifacts" / "data" / "dataset_base.csv"),
    )
    ap.add_argument(
        "--output_jsonl",
        type=str,
        default=str(src_root / "artifacts" / "data" / "dataset_base.jsonl"),
    )
    ap.add_argument(
        "--report_path",
        type=str,
        default=str(src_root / "artifacts" / "data" / "dataset_base_report.json"),
    )
    args = ap.parse_args()

    report = build_dataset_base(
        input_csv_path=args.input_csv,
        output_csv_path=args.output_csv,
        output_jsonl_path=args.output_jsonl,
        report_path=args.report_path,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
