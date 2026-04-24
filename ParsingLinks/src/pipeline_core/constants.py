"""Project-wide constants for dataset extraction and evaluation."""

from __future__ import annotations

STATUS_VALUES = ("present", "absent", "uncertain")

LIST_SIGNAL_FIELDS = (
    "ai_use_cases",
    "adoption_patterns",
    "ai_stack",
    "kpi_signals",
    "budget_signals",
    "org_change_signals",
    "risk_signals",
    "roadmap_signals",
)

SCALAR_SIGNAL_FIELDS = ("deployment_scope",)
ALL_SIGNAL_FIELDS = LIST_SIGNAL_FIELDS + SCALAR_SIGNAL_FIELDS

DEFAULT_GUIDELINE_VERSION = "maturity_v1.0"

MATURITY_RUBRIC = {
    0: "No evidence of active AI usage.",
    1: "Experiments or isolated pilots without stable production usage.",
    2: "At least one production AI use case in a business function.",
    3: "AI integrated across multiple functions with governance/KPI tracking.",
    4: "Enterprise-scale AI in core processes/products with measurable impact.",
}

DEFAULT_STRICT_WEIGHT = 0.70
DEFAULT_SEMANTIC_WEIGHT = 0.30

SPLIT_ORDER = ("train", "dev", "test")
