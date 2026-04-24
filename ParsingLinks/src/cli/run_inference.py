"""Step 3: run extraction inference for all configured models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_core.stages.inference import run_inference


def main() -> None:
    src_root = Path(__file__).resolve().parents[1]

    ap = argparse.ArgumentParser(description="Run extraction inference for all configured models")
    ap.add_argument(
        "--dataset_base_csv",
        type=str,
        default=str(src_root / "artifacts" / "data" / "dataset_base.csv"),
    )
    ap.add_argument(
        "--model_registry",
        type=str,
        default=str(src_root / "config" / "model_registry.example.json"),
    )
    ap.add_argument(
        "--settings",
        type=str,
        default=str(src_root / "config" / "inference_settings.json"),
    )
    ap.add_argument(
        "--output_dir",
        type=str,
        default=str(src_root / "artifacts" / "inference_runs"),
    )
    ap.add_argument("--run_id", type=str, default="",
                    help="Custom run_id. If reusing existing run_id with --skip-existing,"
                         " the script continues that run.")
    ap.add_argument("--models", type=str, default="", help="comma-separated model aliases")
    ap.add_argument("--max_docs", type=int, default=0)
    ap.add_argument("--skip-existing", action="store_true",
                    help="Resume incomplete runs: skip doc_ids already processed")
    ap.add_argument("--prompt_version", type=str, default="v1",
                    choices=["v1", "baseline", "ceiling", "v2"],
                    help="Prompt builder version. 'v1'/'baseline' = original; "
                         "'ceiling'/'v2' = prompt-engineered with few-shot + checklists.")
    ap.add_argument("--doc_ids_file", type=str, default="",
                    help="Optional path to a text file with one doc_id per line. "
                         "Inference runs only on these doc_ids.")
    args = ap.parse_args()

    aliases = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None
    max_docs = args.max_docs if args.max_docs > 0 else None

    doc_ids_filter = None
    if args.doc_ids_file:
        ids_path = Path(args.doc_ids_file)
        if not ids_path.exists():
            raise SystemExit(f"doc_ids_file not found: {ids_path}")
        doc_ids_filter = [line.strip() for line in ids_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not doc_ids_filter:
            raise SystemExit(f"doc_ids_file is empty: {ids_path}")

    summary = run_inference(
        dataset_base_csv=args.dataset_base_csv,
        model_registry_path=args.model_registry,
        output_dir=args.output_dir,
        model_aliases=aliases,
        run_id=args.run_id or None,
        settings_path=args.settings,
        max_docs=max_docs,
        skip_existing=args.skip_existing,
        prompt_version=args.prompt_version,
        doc_ids_filter=doc_ids_filter,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
