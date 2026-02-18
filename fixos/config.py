"""
Zarządzanie konfiguracją fixos.
Ładuje .env / ~/.fixos.conf z priorytetami:
  CLI args > env vars > .env > ~/.fixos.conf > defaults
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Próbuj załadować python-dotenv
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# Kolejność szukania .env
ENV_SEARCH_PATHS = [
    Path.cwd() / ".env",
    Path.home() / ".fixos.env",
    Path.home() / ".fixos.conf",
]

PROVIDER_DEFAULTS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash-preview-04-17",
        "key_env": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey",
        "free_tier": True,
        "description": "Google Gemini – darmowy tier, bardzo dobry do diagnostyki",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "free_tier": False,
        "description": "OpenAI GPT-4o-mini – płatny, niezawodny",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
        "key_env": "OPENROUTER_API_KEY",
        "key_url": "https://openrouter.ai/settings/keys",
        "free_tier": True,
        "description": "OpenRouter – agregator 200+ modeli, darmowe modele dostępne",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-beta",
        "key_env": "XAI_API_KEY",
        "key_url": "https://console.x.ai/",
        "free_tier": False,
        "description": "xAI Grok – model od Elona Muska",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-haiku-20240307",
        "key_env": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
        "free_tier": False,
        "description": "Anthropic Claude – bardzo dobry do analizy logów",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "key_env": "MISTRAL_API_KEY",
        "key_url": "https://console.mistral.ai/api-keys/",
        "free_tier": True,
        "description": "Mistral AI – europejski provider, darmowy tier",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
        "key_env": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
        "free_tier": True,
        "description": "Groq – ultra-szybkie wnioskowanie, darmowy tier",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
        "key_env": "TOGETHER_API_KEY",
        "key_url": "https://api.together.ai/settings/api-keys",
        "free_tier": True,
        "description": "Together AI – open-source modele, $1 kredyt startowy",
    },
    "cohere": {
        "base_url": "https://api.cohere.com/v2",
        "model": "command-r",
        "key_env": "COHERE_API_KEY",
        "key_url": "https://dashboard.cohere.com/api-keys",
        "free_tier": True,
        "description": "Cohere Command-R – darmowy trial, dobry do RAG",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
        "key_url": "https://platform.deepseek.com/api_keys",
        "free_tier": False,
        "description": "DeepSeek – tani chiński provider, bardzo dobry stosunek ceny",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "key_url": "https://cloud.cerebras.ai/platform/",
        "free_tier": True,
        "description": "Cerebras – najszybsze wnioskowanie na świecie, darmowy tier",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "key_env": None,
        "key_url": "https://ollama.com/download",
        "free_tier": True,
        "description": "Ollama – lokalne modele, brak klucza API, pełna prywatność",
    },
}


def _load_env_files():
    """Ładuje pierwszy znaleziony plik .env."""
    if _HAS_DOTENV:
        for p in ENV_SEARCH_PATHS:
            if p.exists():
                load_dotenv(p, override=False)
                return str(p)
    else:
        # Ręczne parsowanie prostego KEY=VALUE
        for p in ENV_SEARCH_PATHS:
            if p.exists():
                try:
                    for line in p.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k and k not in os.environ:
                                os.environ[k] = v
                    return str(p)
                except Exception:
                    pass
    return None


@dataclass
class FixOsConfig:
    # Provider
    provider: str = "gemini"
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None

    # Agent
    agent_mode: str = "hitl"          # hitl | autonomous
    session_timeout: int = 3600
    max_auto_fixes: int = 10          # limit dla trybu autonomous

    # UI
    show_anonymized_data: bool = True  # Pokaż dane użytkownikowi przed wysłaniem

    # Web search fallback
    enable_web_search: bool = True
    serpapi_key: Optional[str] = None

    # Storage
    save_reports: bool = False
    reports_dir: Path = field(default_factory=lambda: Path("/tmp/fixos-reports"))

    # Internals (ustawiane przez _load)
    env_file_loaded: Optional[str] = None

    @classmethod
    def load(
        cls,
        *,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        agent_mode: Optional[str] = None,
        session_timeout: Optional[int] = None,
        show_anonymized_data: Optional[bool] = None,
    ) -> "FixOsConfig":
        """Tworzy konfigurację z połączonych źródeł."""
        env_file = _load_env_files()
        cfg = cls(env_file_loaded=env_file)

        # Provider
        cfg.provider = (
            provider
            or os.environ.get("LLM_PROVIDER", "gemini")
        ).lower()

        if cfg.provider not in PROVIDER_DEFAULTS:
            print(
                f"⚠️  Nieznany provider '{cfg.provider}', używam 'gemini'",
                file=sys.stderr,
            )
            cfg.provider = "gemini"

        pdef = PROVIDER_DEFAULTS[cfg.provider]

        # API Key: argument CLI > env specyficzny dla providera > OPENAI_API_KEY (fallback)
        key_env = pdef.get("key_env")
        cfg.api_key = (
            api_key
            or (os.environ.get(key_env) if key_env else None)
            or os.environ.get("API_KEY")
            or os.environ.get("OPENAI_API_KEY")  # universal fallback
        )

        # Model
        model_env_key = f"{cfg.provider.upper()}_MODEL"
        cfg.model = model or os.environ.get(model_env_key) or pdef["model"]

        # Base URL
        url_env_key = f"{cfg.provider.upper()}_BASE_URL"
        cfg.base_url = base_url or os.environ.get(url_env_key) or pdef["base_url"]

        # Agent mode
        cfg.agent_mode = (
            agent_mode
            or os.environ.get("AGENT_MODE", "hitl")
        ).lower()

        # Timeout
        cfg.session_timeout = session_timeout or int(
            os.environ.get("SESSION_TIMEOUT", "3600")
        )

        # Show data
        if show_anonymized_data is not None:
            cfg.show_anonymized_data = show_anonymized_data
        else:
            val = os.environ.get("SHOW_ANONYMIZED_DATA", "true").lower()
            cfg.show_anonymized_data = val not in ("false", "0", "no")

        # Web search
        val = os.environ.get("ENABLE_WEB_SEARCH", "true").lower()
        cfg.enable_web_search = val not in ("false", "0", "no")
        cfg.serpapi_key = os.environ.get("SERPAPI_KEY")

        # Reports
        val = os.environ.get("SAVE_REPORTS", "false").lower()
        cfg.save_reports = val in ("true", "1", "yes")
        cfg.reports_dir = Path(os.environ.get("REPORTS_DIR", "/tmp/fixos-reports"))

        return cfg

    def validate(self) -> list[str]:
        """Zwraca listę błędów walidacji (pusta = OK)."""
        errors = []
        if not self.api_key and self.provider != "ollama":
            errors.append(
                f"Brak klucza API dla providera '{self.provider}'. "
                f"Ustaw {PROVIDER_DEFAULTS[self.provider].get('key_env')} w .env"
            )
        if self.agent_mode not in ("hitl", "autonomous"):
            errors.append(
                f"Nieprawidłowy AGENT_MODE='{self.agent_mode}'. Użyj: hitl | autonomous"
            )
        return errors

    def summary(self) -> str:
        """Krótkie podsumowanie konfiguracji (bez klucza API)."""
        key_masked = (
            f"{self.api_key[:8]}...{self.api_key[-4:]}"
            if self.api_key and len(self.api_key) > 12
            else "***"
            if self.api_key
            else "❌ BRAK"
        )
        mode_icon = "🤖" if self.agent_mode == "autonomous" else "👤"
        return (
            f"  Provider  : {self.provider} ({self.model})\n"
            f"  API Key   : {key_masked}\n"
            f"  Base URL  : {self.base_url}\n"
            f"  Tryb      : {mode_icon} {self.agent_mode}\n"
            f"  Timeout   : {self.session_timeout}s\n"
            f"  Web search: {'✅' if self.enable_web_search else '❌'}\n"
            f"  .env plik : {self.env_file_loaded or 'nie znaleziono'}"
        )


def get_providers_list() -> list[dict]:
    """Zwraca listę providerów jako listę słowników."""
    result = []
    for name, d in PROVIDER_DEFAULTS.items():
        result.append({
            "name": name,
            "model": d["model"],
            "key_env": d.get("key_env") or "(brak – lokalny)",
            "key_url": d.get("key_url", ""),
            "free_tier": d.get("free_tier", False),
            "description": d.get("description", ""),
        })
    return result
