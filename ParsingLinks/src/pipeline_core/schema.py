"""Normalization and validation for extraction payloads."""

from __future__ import annotations

import json
from typing import Any

from .constants import ALL_SIGNAL_FIELDS, LIST_SIGNAL_FIELDS, SCALAR_SIGNAL_FIELDS, STATUS_VALUES

QUOTE_ALIASES = ("quote", "text", "excerpt", "content", "evidence", "span")
START_ALIASES = ("start_char", "start", "begin", "from", "offset")
END_ALIASES = ("end_char", "end", "finish", "to", "stop")


def empty_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in LIST_SIGNAL_FIELDS:
        payload[field] = {"status": "uncertain", "items": []}
    for field in SCALAR_SIGNAL_FIELDS:
        payload[field] = {"status": "uncertain", "value": ""}
    payload["maturity_level"] = 0
    payload["maturity_rationale"] = ""
    payload["confidence"] = 0.0
    payload["evidence_spans"] = []
    return payload


def _normalize_status(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in STATUS_VALUES:
        return s
    return "uncertain"


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return s


def _normalize_list_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # If user provides comma-separated string, split for convenience.
        candidates = [p.strip() for p in text.split(",")]
    elif isinstance(value, list):
        candidates = [str(x).strip() for x in value if str(x).strip()]
    else:
        candidates = [str(value).strip()]

    uniq: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def _normalize_maturity(value: Any) -> int:
    try:
        lvl = int(value)
    except (TypeError, ValueError):
        return 0
    return min(4, max(0, lvl))


def _normalize_confidence(value: Any) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.0
    if c < 0:
        return 0.0
    if c > 1:
        return 1.0
    return round(c, 4)


def _first_present(raw_dict: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the value for the first key found in *raw_dict*, or ``None``."""
    for key in keys:
        if key in raw_dict and raw_dict[key] is not None:
            return raw_dict[key]
    return None


def _normalize_evidence_spans(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    spans: list[dict[str, Any]] = []
    for raw in value[:30]:
        if not isinstance(raw, dict):
            continue
        field = _normalize_text(raw.get("field"))
        if field and field not in ALL_SIGNAL_FIELDS and field != "maturity_rationale":
            field = ""

        quote = _normalize_text(_first_present(raw, QUOTE_ALIASES))[:500]

        start_char = _first_present(raw, START_ALIASES)
        end_char = _first_present(raw, END_ALIASES)

        try:
            start = int(start_char) if start_char is not None else None
        except (TypeError, ValueError):
            start = None
        try:
            end = int(end_char) if end_char is not None else None
        except (TypeError, ValueError):
            end = None

        if start is not None and start < 0:
            start = None
        if end is not None and end < 0:
            end = None
        if start is not None and end is not None and end < start:
            start, end = end, start

        spans.append(
            {
                "field": field,
                "quote": quote,
                "start_char": start,
                "end_char": end,
            }
        )

    return spans


def normalize_extraction_payload(raw_payload: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []

    payload: dict[str, Any]
    if isinstance(raw_payload, str):
        raw_payload = raw_payload.strip()
        if not raw_payload:
            payload = {}
        else:
            try:
                parsed = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                errors.append(f"payload_json_decode_error:{exc.msg}")
                parsed = {}
            payload = parsed if isinstance(parsed, dict) else {}
    elif isinstance(raw_payload, dict):
        payload = raw_payload
    else:
        payload = {}

    normalized = empty_payload()

    for field in LIST_SIGNAL_FIELDS:
        raw_field = payload.get(field)
        if isinstance(raw_field, dict):
            status = _normalize_status(raw_field.get("status"))
            items = _normalize_list_items(raw_field.get("items"))
        else:
            status = "uncertain"
            items = _normalize_list_items(raw_field)
            if items:
                status = "present"
        if status == "absent":
            items = []
        normalized[field] = {"status": status, "items": items}

    for field in SCALAR_SIGNAL_FIELDS:
        raw_field = payload.get(field)
        if isinstance(raw_field, dict):
            status = _normalize_status(raw_field.get("status"))
            value = _normalize_text(raw_field.get("value"))
        else:
            value = _normalize_text(raw_field)
            status = "present" if value else "uncertain"
        if status == "absent":
            value = ""
        normalized[field] = {"status": status, "value": value}

    normalized["maturity_level"] = _normalize_maturity(payload.get("maturity_level"))
    normalized["maturity_rationale"] = _normalize_text(payload.get("maturity_rationale"))
    normalized["confidence"] = _normalize_confidence(payload.get("confidence"))
    normalized["evidence_spans"] = _normalize_evidence_spans(payload.get("evidence_spans"))

    validation_errors = validate_extraction_payload(normalized)
    errors.extend(validation_errors)

    return normalized, errors


def validate_extraction_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in LIST_SIGNAL_FIELDS:
        value = payload.get(field)
        if not isinstance(value, dict):
            errors.append(f"{field}:not_dict")
            continue
        status = value.get("status")
        if status not in STATUS_VALUES:
            errors.append(f"{field}:bad_status")
        items = value.get("items")
        if not isinstance(items, list):
            errors.append(f"{field}:items_not_list")

    for field in SCALAR_SIGNAL_FIELDS:
        value = payload.get(field)
        if not isinstance(value, dict):
            errors.append(f"{field}:not_dict")
            continue
        status = value.get("status")
        if status not in STATUS_VALUES:
            errors.append(f"{field}:bad_status")
        scalar = value.get("value")
        if scalar is None:
            errors.append(f"{field}:value_none")

    maturity = payload.get("maturity_level")
    if not isinstance(maturity, int) or maturity < 0 or maturity > 4:
        errors.append("maturity_level:out_of_range")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append("confidence:out_of_range")

    spans = payload.get("evidence_spans")
    if not isinstance(spans, list):
        errors.append("evidence_spans:not_list")
    else:
        for idx, span in enumerate(spans):
            if not isinstance(span, dict):
                errors.append(f"evidence_spans:{idx}:not_dict")
                continue
            if "quote" not in span:
                errors.append(f"evidence_spans:{idx}:quote_missing")

    return errors


_WRONG_FIELD_NAMES = ("use_cases", "stack", "usecases", "kpis", "risks")


def extract_error_flags(raw_text: str, normalized: dict[str, Any]) -> list[str]:
    """Detect warning-level issues in a model response.

    Used by inference.py to tag predictions with fine-grained error signals
    without marking them as invalid.
    """
    flags: list[str] = []

    # 1. qwen3_thinking_present
    if "<think>" in raw_text or "</think>" in raw_text:
        flags.append("qwen3_thinking_present")

    # 2. evidence_spans_alias_used
    has_alias = any(k in raw_text for k in ('"text":', '"start":', '"end":', '"excerpt":'))
    has_canonical = any(k in raw_text for k in ('"quote":', '"start_char":', '"end_char":'))
    if has_alias and not has_canonical:
        flags.append("evidence_spans_alias_used")

    # 3. evidence_spans_empty_despite_signals
    has_present_items = any(
        isinstance(normalized.get(f), dict)
        and normalized[f].get("status") == "present"
        and normalized[f].get("items")
        for f in LIST_SIGNAL_FIELDS
    )
    if has_present_items and not normalized.get("evidence_spans"):
        flags.append("evidence_spans_empty_despite_signals")

    # 4. maturity_rationale_empty
    if normalized.get("maturity_level", 0) > 0 and not normalized.get("maturity_rationale"):
        flags.append("maturity_rationale_empty")

    # 5. wrong_field_names_detected
    raw_lower = raw_text.lower()
    for wrong in _WRONG_FIELD_NAMES:
        if f'"{wrong}"' in raw_lower:
            flags.append("wrong_field_names_detected")
            break

    return flags


def payload_status_snapshot(payload: dict[str, Any]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for field in ALL_SIGNAL_FIELDS:
        value = payload.get(field, {})
        if isinstance(value, dict):
            snapshot[field] = _normalize_status(value.get("status"))
        else:
            snapshot[field] = "uncertain"
    return snapshot
