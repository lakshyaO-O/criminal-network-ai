"""AIAnalyzer orchestrator — provider-independent facade for M12A.

Usage:
    analyzer = get_ai_analyzer(known_entities)
    result = analyzer.extract_entities(text)
    result = analyzer.analyze_patterns(snapshot)

Configuration via env:
- AI_PROVIDER=deterministic|local (default deterministic)
- AI_LOCAL_MODEL, AI_LOCAL_TIMEOUT_MS etc. for local.

Security:
- Input bounded (max 100k).
- No secrets in outputs/logs.
- Prompt injection: input is treated as data, never as instruction.
"""
from __future__ import annotations

import os
import hashlib
from typing import Any, Dict, List, Optional

from ai.providers.base import AIProvider, ProviderUnavailable, ProviderTimeout, ProviderMalformedResponse, sanitize_text
from ai.providers.deterministic import DeterministicAIProvider
from ai.providers.local import LocalAIProvider

MAX_INPUT_LEN = 100000


def _sanitize_for_log(text: str, max_len: int = 200) -> str:
    """Sanitized preview for logs — never log raw prompt containing secrets."""
    if not isinstance(text, str):
        return "<non-string>"
    # Truncate and strip sensitive-looking keys
    preview = text[:max_len].replace("\n", " ")
    for key in ("password", "secret", "token", "api_key", "connection_string"):
        if key in preview.lower():
            preview = preview.lower().replace(key, "[REDACTED]")
    return preview


class AIAnalyzer:
    """Facade that selects and delegates to the configured provider."""

    def __init__(self, provider: AIProvider):
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def provider_version(self) -> str:
        return self.provider.provider_version

    def extract_entities(self, text: str, source_id: Optional[str] = None):
        sanitize_text(text, max_len=MAX_INPUT_LEN)
        return self.provider.extract_entities(text, source_id=source_id)

    def extract_relationships(self, text: str, entities: List[Any], source_id: Optional[str] = None, structured_records: Optional[List[Dict[str, Any]]] = None):
        sanitize_text(text, max_len=MAX_INPUT_LEN)
        # Validate entities list bounded
        if entities is not None and len(entities) > 500:
            raise ValueError("entities list exceeds bound 500")
        if structured_records is not None and len(structured_records) > 200:
            raise ValueError("structured_records exceeds bound 200")
        return self.provider.extract_relationships(text, entities, source_id=source_id, structured_records=structured_records)

    def analyze_patterns(self, graph_snapshot: Dict[str, Any], analysis_type: str = "network_summary", case_id: Optional[str] = None, root_entity_id: Optional[str] = None):
        # graph_snapshot size bounded implicitly via repo export (150 nodes)
        return self.provider.analyze_patterns(graph_snapshot, analysis_type=analysis_type, case_id=case_id, root_entity_id=root_entity_id)

    def status(self) -> Dict[str, Any]:
        s = self.provider.status()
        s["input_max_len"] = MAX_INPUT_LEN
        return s


def get_ai_provider(known_entities=None) -> AIProvider:
    """Factory respecting env configuration. No hard-coded API keys."""
    provider_env = os.getenv("AI_PROVIDER", "deterministic").lower().strip()
    if not provider_env:
        provider_env = "deterministic"
    if provider_env == "local":
        # Try local; if unavailable, caller will get ProviderUnavailable on use — not silent fallback
        return LocalAIProvider(known_entities=known_entities)
    # Default deterministic — always available
    if provider_env not in ("deterministic", "local"):
        # Unknown provider => unavailable, not silent deterministic fallback (typed error)
        # For this milestone we treat unknown as unavailable to avoid fabrication
        class UnavailableProvider(AIProvider):
            provider_name = provider_env
            provider_version = "unknown"
            def extract_entities(self, *a, **kw): raise ProviderUnavailable(f"AI provider '{provider_env}' unavailable")
            def extract_relationships(self, *a, **kw): raise ProviderUnavailable(f"AI provider '{provider_env}' unavailable")
            def analyze_patterns(self, *a, **kw): raise ProviderUnavailable(f"AI provider '{provider_env}' unavailable")
            def status(self): return {"provider": provider_env, "available": False, "reason": "unknown provider"}
        return UnavailableProvider()
    return DeterministicAIProvider(known_entities=known_entities)


def get_ai_analyzer(known_entities=None) -> AIAnalyzer:
    return AIAnalyzer(get_ai_provider(known_entities))
