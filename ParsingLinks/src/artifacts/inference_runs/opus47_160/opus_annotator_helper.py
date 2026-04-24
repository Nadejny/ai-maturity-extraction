"""Helper for Opus 4.7 annotator run.

Usage:
    python opus_annotator_helper.py get DOC000492
    python opus_annotator_helper.py processed
    python opus_annotator_helper.py append DOC000492 <payload_json_path>
    python opus_annotator_helper.py parse_error DOC000492 "reason"
    python opus_annotator_helper.py summary
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows (default cp1251 can't encode many chars)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT.parents[1] / "data" / "dataset_base.jsonl"
PREDICTIONS_PATH = ROOT / "opus_4_7/predictions.jsonl"
BATCH1_PATH = ROOT / "doc_ids_batch1.txt"
SIGNAL_FIELDS = [
    "ai_use_cases", "adoption_patterns", "ai_stack", "kpi_signals",
    "budget_signals", "org_change_signals", "risk_signals",
    "roadmap_signals", "deployment_scope",
]


def _load_index() -> dict:
    idx = {}
    with DATASET_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            idx[r["doc_id"]] = r
    return idx


def _processed_ids() -> set:
    ids = set()
    if PREDICTIONS_PATH.exists():
        with PREDICTIONS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["doc_id"])
                except Exception:
                    pass
    return ids


def _batch1_ids() -> list:
    with BATCH1_PATH.open("r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]


def cmd_get(doc_id: str) -> int:
    idx = _load_index()
    r = idx.get(doc_id)
    if not r:
        print(f"ERROR: {doc_id} not in dataset", file=sys.stderr)
        return 1
    meta = {
        "doc_id": r["doc_id"],
        "company": r.get("company"),
        "industry": r.get("industry"),
        "year": r.get("year"),
        "title": r.get("title"),
        "word_count": r.get("word_count"),
        "url_canonical": r.get("url_canonical"),
    }
    print("=== META ===")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("=== TEXT ===")
    print(r.get("text", ""))
    return 0


def cmd_processed() -> int:
    ids = _processed_ids()
    print(f"processed_count: {len(ids)}")
    for i in sorted(ids):
        print(i)
    return 0


def cmd_append(doc_id: str, payload_path: str) -> int:
    with open(payload_path, "r", encoding="utf-8") as f:
        payload_text = f.read()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        print(f"ERROR: payload JSON invalid: {exc}", file=sys.stderr)
        return 2
    # Sanity checks
    for fld in SIGNAL_FIELDS:
        if fld not in payload:
            print(f"ERROR: missing field {fld}", file=sys.stderr)
            return 3
    for fld in SIGNAL_FIELDS[:-1]:  # all except deployment_scope
        block = payload[fld]
        if "status" not in block or "items" not in block:
            print(f"ERROR: {fld} missing status/items", file=sys.stderr)
            return 4
    ds = payload["deployment_scope"]
    if "status" not in ds or "value" not in ds:
        print("ERROR: deployment_scope missing status/value", file=sys.stderr)
        return 5
    if not isinstance(payload.get("maturity_level"), int) or payload["maturity_level"] not in (0, 1, 2, 3, 4):
        print(f"ERROR: maturity_level invalid: {payload.get('maturity_level')}", file=sys.stderr)
        return 6
    conf = payload.get("confidence")
    if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
        print(f"ERROR: confidence invalid: {conf}", file=sys.stderr)
        return 7
    if not isinstance(payload.get("evidence_spans"), list):
        print("ERROR: evidence_spans must be list", file=sys.stderr)
        return 8

    status_snapshot = {fld: payload[fld]["status"] for fld in SIGNAL_FIELDS}
    row = {
        "doc_id": doc_id,
        "model_alias": "opus_4_7",
        "run_id": "opus47_160",
        "fields_payload": payload,
        "confidence": payload["confidence"],
        "evidence_spans": payload["evidence_spans"],
        "raw_response": json.dumps(payload, ensure_ascii=False),
        "latency_ms": 0,
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "status_snapshot": status_snapshot,
        "structured_valid": True,
        "error_tags": [],
        "error_message": "",
        "schema_errors": [],
        "maturity_level": payload["maturity_level"],
        "deployment_scope_status": payload["deployment_scope"]["status"],
        "deployment_scope_value": payload["deployment_scope"]["value"],
    }
    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    done = len(_processed_ids())
    total = 80
    print(f"[{done}/{total}] {doc_id} -> mat={payload['maturity_level']}, confidence={payload['confidence']:.2f}")
    return 0


def cmd_parse_error(doc_id: str, reason: str) -> int:
    empty = {fld: ({"status": "absent", "items": []} if fld != "deployment_scope" else {"status": "absent", "value": ""}) for fld in SIGNAL_FIELDS}
    row = {
        "doc_id": doc_id,
        "model_alias": "opus_4_7",
        "run_id": "opus47_160",
        "fields_payload": {
            **empty,
            "maturity_level": 0,
            "maturity_rationale": "",
            "confidence": 0.0,
            "evidence_spans": [],
        },
        "confidence": 0.0,
        "evidence_spans": [],
        "raw_response": "",
        "latency_ms": 0,
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "status_snapshot": {fld: "absent" for fld in SIGNAL_FIELDS},
        "structured_valid": False,
        "error_tags": ["parse_error"],
        "error_message": reason,
        "schema_errors": [],
        "maturity_level": 0,
        "deployment_scope_status": "absent",
        "deployment_scope_value": "",
    }
    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    done = len(_processed_ids())
    print(f"[{done}/80] {doc_id} -> PARSE_ERROR ({reason})")
    return 0


def cmd_summary() -> int:
    rows = []
    if PREDICTIONS_PATH.exists():
        with PREDICTIONS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    total = len(rows)
    valid = [r for r in rows if r.get("structured_valid")]
    parse_err = [r for r in rows if not r.get("structured_valid")]
    mat_dist = {str(i): 0 for i in range(5)}
    for r in valid:
        mat_dist[str(r["maturity_level"])] = mat_dist.get(str(r["maturity_level"]), 0) + 1
    confs = [r["confidence"] for r in valid]
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    signals_present = {fld: 0 for fld in SIGNAL_FIELDS}
    for r in valid:
        for fld in SIGNAL_FIELDS:
            if r["status_snapshot"].get(fld) == "present":
                signals_present[fld] += 1
    present_rates = {fld: (signals_present[fld] / len(valid) if valid else 0.0) for fld in SIGNAL_FIELDS}
    error_tag_counts = {}
    for r in rows:
        for tag in r.get("error_tags", []) or []:
            error_tag_counts[tag] = error_tag_counts.get(tag, 0) + 1

    summary = {
        "run_id": "opus47_160",
        "batch": 1,
        "batch_size": 80,
        "model_alias": "opus_4_7",
        "rows": total,
        "structured_valid_rows": len(valid),
        "structured_valid_rate": (len(valid) / total) if total else 0.0,
        "parse_error_rows": len(parse_err),
        "error_tag_counts": error_tag_counts,
        "maturity_distribution": mat_dist,
        "avg_confidence": round(avg_conf, 4),
        "signals_present_rates": {k: round(v, 4) for k, v in present_rates.items()},
        "predictions_jsonl": str(PREDICTIONS_PATH),
    }
    out_path = PREDICTIONS_PATH.parent / "run_summary.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Written: {out_path}")
    return 0


def cmd_remaining() -> int:
    done = _processed_ids()
    remaining = [d for d in _batch1_ids() if d not in done]
    for d in remaining:
        print(d)
    print(f"--- remaining_count: {len(remaining)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    cmd = argv[0]
    if cmd == "get" and len(argv) == 2:
        sys.exit(cmd_get(argv[1]))
    elif cmd == "processed":
        sys.exit(cmd_processed())
    elif cmd == "append" and len(argv) == 3:
        sys.exit(cmd_append(argv[1], argv[2]))
    elif cmd == "parse_error" and len(argv) == 3:
        sys.exit(cmd_parse_error(argv[1], argv[2]))
    elif cmd == "summary":
        sys.exit(cmd_summary())
    elif cmd == "remaining":
        sys.exit(cmd_remaining())
    else:
        print(f"Unknown command: {argv}", file=sys.stderr)
        sys.exit(1)
