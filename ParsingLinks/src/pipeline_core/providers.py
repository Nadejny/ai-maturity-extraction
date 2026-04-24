"""Provider abstractions for Gemini, OpenAI-compatible, and mock backends."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .schema import empty_payload


@dataclass
class ModelConfig:
    model_alias: str
    provider: str
    model_id: str
    base_url: str = ""
    api_key_env: str = ""
    api_key: str = ""
    timeout_sec: int = 120
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)

    def resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.getenv(self.api_key_env, "")
        return ""


@dataclass
class ProviderResponse:
    content: str
    latency_ms: int
    token_usage: dict[str, Any]
    raw_response: dict[str, Any]


class BaseProvider:
    def __init__(self, config: ModelConfig):
        self.config = config

    def generate(self, system_prompt: str, user_prompt: str, settings: dict[str, Any]) -> ProviderResponse:
        raise NotImplementedError


class GeminiProvider(BaseProvider):
    def generate(self, system_prompt: str, user_prompt: str, settings: dict[str, Any]) -> ProviderResponse:
        api_key = self.config.resolved_api_key()
        if not api_key:
            raise RuntimeError(f"Missing Gemini API key for model_alias={self.config.model_alias}")

        base_url = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta/models"
        url = f"{base_url.rstrip('/')}/{self.config.model_id}:generateContent?key={api_key}"

        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": float(settings.get("temperature", 0.0)),
                "topP": float(settings.get("top_p", 0.95)),
                "maxOutputTokens": int(settings.get("max_output_tokens", 2048)),
            },
        }

        if settings.get("json_mode", True):
            payload["generationConfig"]["responseMimeType"] = "application/json"

        if self.config.extra_body:
            payload.update(self.config.extra_body)

        started = time.perf_counter()
        resp = requests.post(url, json=payload, timeout=self.config.timeout_sec)
        latency_ms = int((time.perf_counter() - started) * 1000)
        resp.raise_for_status()

        data = resp.json()
        content = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
            if parts:
                content = str(parts[0].get("text") or "")

        token_usage = data.get("usageMetadata") or {}

        return ProviderResponse(
            content=content,
            latency_ms=latency_ms,
            token_usage=token_usage,
            raw_response=data,
        )


class OpenAICompatibleProvider(BaseProvider):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _post_with_retry(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> requests.Response:
        resp = requests.post(url, headers=headers, json=body, timeout=self.config.timeout_sec)
        if 500 <= resp.status_code < 600:
            resp.raise_for_status()
        return resp

    def generate(self, system_prompt: str, user_prompt: str, settings: dict[str, Any]) -> ProviderResponse:
        base = (self.config.base_url or "").rstrip("/")
        if not base:
            raise RuntimeError(f"Missing base_url for model_alias={self.config.model_alias}")

        if base.endswith("/chat/completions"):
            url = base
        else:
            url = f"{base}/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }
        api_key = self.config.resolved_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        body: dict[str, Any] = {
            "model": self.config.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(settings.get("temperature", 0.0)),
            "top_p": float(settings.get("top_p", 0.95)),
            "max_tokens": int(settings.get("max_output_tokens", 2048)),
            "seed": int(settings.get("seed", 42)),
        }

        if settings.get("json_mode", True):
            body["response_format"] = {"type": "json_object"}

        if self.config.extra_body:
            body.update(self.config.extra_body)

        started = time.perf_counter()
        resp = self._post_with_retry(url, headers, body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            message = (choices[0] or {}).get("message") or {}
            content = str(message.get("content") or "")

        token_usage = data.get("usage") or {}

        return ProviderResponse(
            content=content,
            latency_ms=latency_ms,
            token_usage=token_usage,
            raw_response=data,
        )


_THINKING_MODEL_PREFIXES = ("qwen3", "qwq", "deepseek-r1")


class OllamaNativeProvider(BaseProvider):
    """Provider using Ollama's native /api/chat endpoint.

    Sends ``think: false`` only for models with reasoning mode (Qwen3, QwQ,
    DeepSeek-R1) to suppress wasteful thinking tokens.  For other models
    (Gemma, Llama, …) the parameter is omitted — sending it can break
    structured output on some backends (ollama/ollama#15260).
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _post_with_retry(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> requests.Response:
        resp = requests.post(url, headers=headers, json=body, timeout=self.config.timeout_sec)
        if 500 <= resp.status_code < 600:
            resp.raise_for_status()
        return resp

    def generate(self, system_prompt: str, user_prompt: str, settings: dict[str, Any]) -> ProviderResponse:
        base = (self.config.base_url or "").rstrip("/")
        if not base:
            raise RuntimeError(f"Missing base_url for model_alias={self.config.model_alias}")

        # Accept both "http://host:11434" and "http://host:11434/v1"
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/api/chat"

        model_lower = self.config.model_id.lower()
        needs_think_off = any(model_lower.startswith(p) for p in _THINKING_MODEL_PREFIXES)

        body: dict[str, Any] = {
            "model": self.config.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": float(settings.get("temperature", 0.0)),
                "top_p": float(settings.get("top_p", 0.95)),
                "num_predict": int(settings.get("max_output_tokens", 2048)),
                "seed": int(settings.get("seed", 42)),
            },
        }

        if needs_think_off:
            body["think"] = False

        if settings.get("json_mode", True):
            body["format"] = "json"

        if self.config.extra_body:
            body.update(self.config.extra_body)

        headers = {"Content-Type": "application/json"}
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        started = time.perf_counter()
        resp = self._post_with_retry(url, headers, body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        resp.raise_for_status()

        data = resp.json()
        content = str((data.get("message") or {}).get("content") or "")

        token_usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }

        return ProviderResponse(
            content=content,
            latency_ms=latency_ms,
            token_usage=token_usage,
            raw_response=data,
        )


class MockProvider(BaseProvider):
    def generate(self, system_prompt: str, user_prompt: str, settings: dict[str, Any]) -> ProviderResponse:
        _ = system_prompt, settings
        lower = user_prompt.lower()

        payload = empty_payload()
        has_ai = any(k in lower for k in (" ai ", "artificial intelligence", "machine learning", "llm", "generative"))

        if has_ai:
            payload["ai_use_cases"] = {"status": "present", "items": ["automation", "decision support"]}
            payload["adoption_patterns"] = {"status": "present", "items": ["pilot", "copilot"]}
            payload["ai_stack"] = {"status": "present", "items": ["llm", "cloud"]}
            payload["deployment_scope"] = {"status": "present", "value": "pilot"}
            payload["kpi_signals"] = {"status": "present", "items": ["productivity"]}
            payload["risk_signals"] = {"status": "present", "items": ["data privacy"]}
            payload["roadmap_signals"] = {"status": "present", "items": ["scale next quarter"]}

            maturity = 1
            if "production" in lower or "in production" in lower:
                maturity = 2
                payload["deployment_scope"] = {"status": "present", "value": "production"}
            if "multiple functions" in lower or "across functions" in lower:
                maturity = 3
                payload["deployment_scope"] = {"status": "present", "value": "multi-function"}
            if "enterprise-wide" in lower or "at scale" in lower:
                maturity = 4
                payload["deployment_scope"] = {"status": "present", "value": "enterprise"}

            payload["maturity_level"] = maturity
            payload["maturity_rationale"] = "Derived from explicit deployment and impact signals in text."
            payload["confidence"] = 0.78
            payload["evidence_spans"] = [
                {
                    "field": "deployment_scope",
                    "quote": "AI program is in production",
                    "start_char": None,
                    "end_char": None,
                }
            ]
        else:
            for field in payload:
                if isinstance(payload[field], dict) and "status" in payload[field]:
                    payload[field]["status"] = "absent"
            payload["maturity_level"] = 0
            payload["maturity_rationale"] = "No explicit AI adoption evidence found."
            payload["confidence"] = 0.55

        return ProviderResponse(
            content=json.dumps(payload, ensure_ascii=False),
            latency_ms=5,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            raw_response={"mock": True},
        )


def load_model_registry(path: str | Path) -> dict[str, ModelConfig]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Model registry file not found: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("models") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Model registry must contain {\"models\": [...]} structure")

    registry: dict[str, ModelConfig] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        alias = str(raw.get("model_alias") or "").strip()
        provider = str(raw.get("provider") or "").strip()
        model_id = str(raw.get("model_id") or "").strip()
        if not alias or not provider or not model_id:
            raise ValueError(f"Invalid model entry: {raw}")

        if alias in registry:
            raise ValueError(f"Duplicate model_alias in registry: {alias}")

        registry[alias] = ModelConfig(
            model_alias=alias,
            provider=provider,
            model_id=model_id,
            base_url=str(raw.get("base_url") or ""),
            api_key_env=str(raw.get("api_key_env") or ""),
            api_key=str(raw.get("api_key") or ""),
            timeout_sec=int(raw.get("timeout_sec") or 120),
            extra_headers=raw.get("extra_headers") or {},
            extra_body=raw.get("extra_body") or {},
        )

    return registry


def build_provider(config: ModelConfig) -> BaseProvider:
    provider = config.provider.strip().lower()
    if provider == "gemini":
        return GeminiProvider(config)
    if provider in {"ollama", "ollama_native", "ollama-native"}:
        return OllamaNativeProvider(config)
    if provider in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleProvider(config)
    if provider == "mock":
        return MockProvider(config)
    raise ValueError(f"Unsupported provider type: {config.provider}")
