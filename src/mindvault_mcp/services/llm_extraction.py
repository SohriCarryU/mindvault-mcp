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

        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-type": "application/json",
                "Authorization": f"Bearer {key}",
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

        if not isinstance(result, dict):
            return None

        return result
