from __future__ import annotations

import json

import re
from openai import OpenAI, AzureOpenAI
import requests


class SummarizationError(Exception):
    pass


class SummarizationService:
    def __init__(self, api_key: str, model: str, azure_config: dict | None = None):
        self.api_key = api_key
        self.azure_config = azure_config or {}
        self.azure_client = None
        self.client = None
        if api_key:
            try:
                self.client = OpenAI(api_key=api_key)
            except Exception:
                self.client = None
        if self.azure_config.get("endpoint") and self.azure_config.get("api_key"):
            try:
                self.azure_client = AzureOpenAI(
                    api_version=self.azure_config.get("api_version", "2024-12-01-preview"),
                    azure_endpoint=self.azure_config.get("endpoint"),
                    api_key=self.azure_config.get("api_key"),
                )
            except Exception:
                self.azure_client = None
        self.model = model

    def summarize(self, transcript: str, caption: str = ""):
        if not transcript or len(transcript.strip()) < 20:
            return "No spoken content detected", "This Reel does not contain transcribable speech."

        if self.client is None and not self.api_key and self.azure_client is None:
            return self._fallback_summary(transcript)

        system = (
            "You are a careful analyst summarizing a short video transcript. "
            "Extract the full set of key ideas, claims, and lessons in clear, neutral language. "
            "Do not repeat slurs, stereotypes, or hate speech. If biased framing appears, "
            "name it explicitly and summarize in neutral terms. Separate FACTS from OPINIONS/CLAIMS "
            "and from SPECULATION. Preserve the argument flow and include any calls-to-action.\n\n"
            "Return a JSON object with keys: title, summary.\n"
            "- title: concise, descriptive (max ~10 words)\n"
            "- summary: complete, no length limit. Use this structure:\n"
            "  Summary:\n"
            "  Key Claims:\n"
            "  Issues / Bias Flags:\n"
            "  Calls-to-Action:"
        )
        user = (
            "Caption:\n"
            f"{caption or 'No caption available'}\n\n"
            "Transcript:\n"
            f"{transcript}"
        )

        content = ""
        if self.azure_client is not None:
            try:
                resp = self.azure_client.chat.completions.create(
                    model=self.azure_config.get("deployment") or self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=900,
                )
                if getattr(resp, "choices", None):
                    message = resp.choices[0].message if resp.choices else None
                    content = (getattr(message, "content", "") or "").strip()
            except Exception:
                content = ""

        if not content and self.client is not None:
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=900,
                )
                if getattr(resp, "choices", None):
                    message = resp.choices[0].message if resp.choices else None
                    content = (getattr(message, "content", "") or "").strip()
            except Exception:
                content = ""

        if not content and self.api_key and self.azure_client is None:
            content = self._direct_openai(system, user)

        if not content:
            return self._fallback_summary(transcript)

        data = self._parse_json(content)
        if data:
            title = self._coerce_text(data.get("title"))
            summary = self._coerce_text(data.get("summary"))

            # Handle wrapped payloads like {"result": {"title": "...", "summary": {...}}}
            if (not title or not summary) and isinstance(data, dict):
                for key in ("result", "data", "output", "analysis"):
                    nested = data.get(key)
                    if not isinstance(nested, dict):
                        continue
                    if not title:
                        title = self._coerce_text(nested.get("title"))
                    if not summary:
                        summary = self._coerce_text(
                            nested.get("summary")
                            or nested.get("detailed_summary")
                            or nested.get("long_summary")
                        )
                    if title and summary:
                        break
            if title and summary:
                return title, summary

        return self._fallback_summary(transcript)

    def _direct_openai(self, system: str, user: str) -> str:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 900,
                },
                timeout=30,
            )
            if resp.status_code >= 400:
                return ""
            data = resp.json()
            if not isinstance(data, dict):
                return ""
            choices = data.get("choices") or []
            if not choices:
                return ""
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get("message")
            if not isinstance(message, dict):
                return ""
            return message.get("content", "") or ""
        except Exception:
            return ""

    def _parse_json(self, content: str) -> dict | None:
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # Strip markdown fences before fallback extraction.
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

    def _coerce_text(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value).strip()
        if isinstance(value, list):
            parts = [self._coerce_text(item) for item in value]
            parts = [p for p in parts if p]
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            sections = []
            for k, v in value.items():
                v_text = self._coerce_text(v)
                if not v_text:
                    continue
                if "\n" in v_text:
                    sections.append(f"{k}:\n{v_text}")
                else:
                    sections.append(f"{k}: {v_text}")
            if sections:
                return "\n\n".join(sections).strip()
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return ""
        try:
            return str(value).strip()
        except Exception:
            return ""

    def _fallback_summary(self, transcript: str):
        # Try Sumy if installed, otherwise a simple heuristic
        try:
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.lsa import LsaSummarizer

            parser = PlaintextParser.from_string(transcript, Tokenizer("english"))
            summarizer = LsaSummarizer()
            sentences = summarizer(parser.document, 2)
            summary = " ".join([str(s) for s in sentences]).strip()
            if summary:
                return "Summary", summary
        except Exception:
            pass

        # Heuristic: first 2 sentences
        parts = transcript.strip().split(".")
        summary = ".".join(parts[:2]).strip()
        if summary:
            if not summary.endswith("."):
                summary += "."
        return "Summary", summary or transcript[:200]
