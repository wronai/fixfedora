"""
Zarządzanie konfiguracją fixfedora.
Ładuje .env / ~/.fixfedora.conf z priorytetami:
  CLI args > env vars > .env > ~/.fixfedora.conf > defaults
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
    Path.home() / ".fixfedora.env",
    Path.home() / ".fixfedora.conf",
]

PROVIDER_DEFAULTS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash-preview-04-17",
        "key_env": "GEMINI_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-beta",
        "key_env": "XAI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "google/gemini-2.0-flash-exp:free",
        "key_env": "OPENROUTER_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "key_env": None,  # Bez klucza
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
class FixFedoraConfig:
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
    reports_dir: Path = field(default_factory=lambda: Path("/tmp/fixfedora-reports"))

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
    ) -> "FixFedoraConfig":
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
        cfg.reports_dir = Path(os.environ.get("REPORTS_DIR", "/tmp/fixfedora-reports"))

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


def get_providers_list() -> str:
    """Zwraca sformatowaną listę providerów."""
    lines = []
    for name, d in PROVIDER_DEFAULTS.items():
        key_env = d.get("key_env", "brak")
        lines.append(f"  {name:<12} model: {d['model']:<40} klucz: {key_env}")
    return "\n".join(lines)
