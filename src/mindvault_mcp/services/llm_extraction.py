from __future__ import annotations

import json
import os
import urllib.request

from mindvault_mcp.config import AppConfig
from mindvault_mcp.schemas import IngestMetadata


class LLMExtractionService:
    """Optional LLM-backed extraction.

    The service is disabled by default. When disabled it returns ``None`` so
    callers fall back to the existing rule-based extraction without touching the
    network.
    """

    def __init__(self, config: AppConfig):
        self.config = config

    def extract_via_llm(
        self,
        text: str,
        metadata: IngestMetadata | None = None,
        api_key: str | None = None,
    ) -> dict | None:
        if not self.config.extraction.llm_enabled:
            return None

        key = api_key or os.getenv("LLM_API_KEY")
        if not key:
            return None

        ext = self.config.extraction
        url = ext.llm_base_url.rstrip("/") + "/chat/completions"

        system_prompt = (
            "You are a knowledge-card extraction assistant. "
            "Return ONLY valid JSON with exactly these keys: "
            "title, problem, context, insight, solution, tags, domain, confidence. "
            "tags must be a list of strings. confidence must be a float between 0 and 1."
        )

        user_content = text
        if metadata:
            meta_info = {k: v for k, v in metadata.model_dump().items() if v and k != "privacy_level"}
            if meta_info:
                user_content += "\n\nMetadata: " + json.dumps(meta_info, default=str)

        payload = json.dumps(
            {
                "model": ext.llm_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            }
        ).encode("utf-8")

        user_agent = os.getenv("HTTP_USER_AGENT", "mindvault-mcp")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": user_agent,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=ext.llm_timeout_seconds) as resp:
                body = resp.read()
        except Exception:
            return None

        try:
            response_json = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return None

        try:
            content_str = response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

        try:
            result = json.loads(content_str)
        except (json.JSONDecodeError, TypeError):
            return None

        return self._normalize_result(result, fallback_text=text)

    def _normalize_result(self, raw: object, fallback_text: str = "") -> dict | None:
        if not isinstance(raw, dict):
            return None

        normalized = {
            "title": self._string_field(raw.get("title")),
            "problem": self._string_field(raw.get("problem")),
            "context": self._string_field(raw.get("context")),
            "insight": self._string_field(raw.get("insight")),
            "solution": self._string_field(raw.get("solution")),
            "tags": self._tags(raw.get("tags")),
            "domain": self._string_field(raw.get("domain")) or "general",
            "confidence": self._confidence(raw.get("confidence")),
        }

        if not normalized["title"]:
            normalized["title"] = self._title_from_text(
                normalized["context"] or normalized["problem"] or fallback_text
            )
        else:
            normalized["title"] = self._title_from_text(normalized["title"])

        return normalized

    def _string_field(self, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _tags(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _confidence(self, value: object) -> float:
        if value is None:
            return 0.5
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))

    def _title_from_text(self, text: str) -> str:
        title = text.strip().rstrip(".!?") or "Untitled memory"
        if len(title) > 80:
            return title[:77].rstrip() + "..."
        return title
