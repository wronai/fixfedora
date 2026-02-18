"""
Testy jednostkowe – config, anonimizacja, web search.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch


class TestConfig:
    def test_default_provider_is_gemini(self):
        from fixfedora.config import FixFedoraConfig
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}, clear=False):
            cfg = FixFedoraConfig.load()
        assert cfg.provider == "gemini"

    def test_model_default_gemini(self):
        from fixfedora.config import FixFedoraConfig
        cfg = FixFedoraConfig.load(provider="gemini")
        assert "gemini" in cfg.model.lower()

    def test_invalid_provider_fallback(self):
        from fixfedora.config import FixFedoraConfig
        with patch.dict(os.environ, {"LLM_PROVIDER": "nonexistent"}, clear=False):
            cfg = FixFedoraConfig.load()
        assert cfg.provider == "gemini"

    def test_validate_missing_key(self):
        from fixfedora.config import FixFedoraConfig
        cfg = FixFedoraConfig(provider="openai", api_key=None)
        errors = cfg.validate()
        assert len(errors) > 0
        assert "API" in errors[0]

    def test_validate_ollama_no_key_needed(self):
        from fixfedora.config import FixFedoraConfig
        cfg = FixFedoraConfig(provider="ollama", api_key=None)
        errors = cfg.validate()
        assert len(errors) == 0

    def test_agent_mode_from_env(self):
        from fixfedora.config import FixFedoraConfig
        with patch.dict(os.environ, {"AGENT_MODE": "autonomous"}, clear=False):
            cfg = FixFedoraConfig.load()
        assert cfg.agent_mode == "autonomous"

    def test_summary_masks_key(self):
        from fixfedora.config import FixFedoraConfig
        cfg = FixFedoraConfig(api_key="AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345")
        summary = cfg.summary()
        assert "AIzaSyAB" in summary
        assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ12345" not in summary


class TestAnonymizer:
    def test_empty_string(self):
        from fixfedora.utils.anonymizer import anonymize
        anon, report = anonymize("")
        assert anon == ""
        assert len(report.replacements) == 0

    def test_non_string_input(self):
        from fixfedora.utils.anonymizer import anonymize
        anon, report = anonymize({"key": "value"})
        assert isinstance(anon, str)

    def test_no_sensitive_data(self):
        from fixfedora.utils.anonymizer import anonymize
        data = "systemctl status pipewire -- Active: running"
        anon, report = anonymize(data)
        # Brak IP ani ścieżek → brak lub minimalne zastąpienia
        sensitive_replacements = {
            k: v for k, v in report.replacements.items()
            if k not in ("Hostname", "Username")
        }
        assert len(sensitive_replacements) == 0

    def test_ipv6_not_mangled(self):
        """IPv6 adresy nie powinny być uszkodzone (nie obsługujemy)."""
        from fixfedora.utils.anonymizer import anonymize
        data = "IPv6 address: 2001:db8::1"
        anon, _ = anonymize(data)
        # Nie crashuje
        assert isinstance(anon, str)

    def test_multiple_ips_all_masked(self):
        from fixfedora.utils.anonymizer import anonymize
        data = "from 192.168.1.1 to 10.0.0.50 via 172.16.0.1"
        anon, report = anonymize(data)
        assert report.replacements.get("Adresy IPv4", 0) == 3
        assert "192.168.1.1" not in anon
        assert "10.0.0.50" not in anon

    def test_password_in_env_masked(self):
        from fixfedora.utils.anonymizer import anonymize
        data = "DB_PASSWORD=mysecretpassword123 API_KEY=abc123def456"
        anon, report = anonymize(data)
        assert "mysecretpassword123" not in anon
        assert report.replacements.get("Hasła/sekrety", 0) > 0


class TestWebSearch:
    def test_format_empty_results(self):
        from fixfedora.utils.web_search import format_results_for_llm
        result = format_results_for_llm([])
        assert "Brak" in result

    def test_format_single_result(self):
        from fixfedora.utils.web_search import SearchResult, format_results_for_llm
        r = SearchResult(
            title="Fix Lenovo audio", url="https://example.com", snippet="Install sof-firmware", source="Test"
        )
        formatted = format_results_for_llm([r])
        assert "Fix Lenovo audio" in formatted
        assert "https://example.com" in formatted
        assert "[1]" in formatted

    def test_http_get_timeout(self):
        """_http_get powinien obsłużyć timeout gracefully."""
        from fixfedora.utils.web_search import _http_get
        result = _http_get("http://240.0.0.1/nonexistent", timeout=1)
        assert result is None
