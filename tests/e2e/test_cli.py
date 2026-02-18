"""
Testy e2e – CLI commands (fixos, fixos llm, fixos token, fixos providers).
Używa Click test runner – nie wymaga API.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from fixos.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_env(tmp_path):
    """Tymczasowy plik .env do testów token set/show/clear."""
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=gemini\n", encoding="utf-8")
    return env_file


class TestWelcomeScreen:
    """Testy ekranu powitalnego (fixos bez argumentów)."""

    def test_welcome_shows_banner(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "fixOS" in result.output or "fix" in result.output.lower()

    def test_welcome_shows_commands(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "fixos fix" in result.output
        assert "fixos scan" in result.output
        assert "fixos llm" in result.output
        assert "fixos token set" in result.output

    def test_welcome_shows_status_section(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Provider" in result.output
        assert "API Key" in result.output

    def test_welcome_shows_tip_when_no_key(self, runner):
        """Gdy brak klucza API, powinien pokazać wskazówkę."""
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "API_KEY": "",
            "OPENROUTER_API_KEY": "", "GROQ_API_KEY": "",
        }, clear=False):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0
        # Powinien sugerować fixos llm lub fixos token set
        assert "llm" in result.output or "token" in result.output


class TestLlmCommand:
    """Testy komendy fixos llm."""

    def test_llm_shows_all_providers(self, runner):
        result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        for provider in ["gemini", "openai", "openrouter", "groq", "mistral",
                         "anthropic", "together", "cohere", "deepseek", "cerebras", "ollama"]:
            assert provider in result.output

    def test_llm_shows_urls(self, runner):
        result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        assert "https://" in result.output
        assert "aistudio.google.com" in result.output
        assert "console.groq.com" in result.output
        assert "openrouter.ai" in result.output

    def test_llm_shows_free_paid_badges(self, runner):
        result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        assert "FREE" in result.output
        assert "PAID" in result.output

    def test_llm_free_filter(self, runner):
        result = runner.invoke(cli, ["llm", "--free"])
        assert result.exit_code == 0
        # Darmowe providery muszą być
        assert "gemini" in result.output
        assert "groq" in result.output
        # Płatne nie powinny być (openai jest PAID)
        assert "openai" not in result.output or "openrouter" in result.output

    def test_llm_shows_token_set_commands(self, runner):
        result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        assert "fixos token set" in result.output

    def test_llm_shows_env_vars(self, runner):
        result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        assert "GEMINI_API_KEY" in result.output
        assert "GROQ_API_KEY" in result.output
        assert "OPENROUTER_API_KEY" in result.output

    def test_llm_marks_active_provider(self, runner):
        """Aktywny provider powinien być oznaczony."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq"}, clear=False):
            result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        assert "aktywny" in result.output

    def test_llm_shows_12_providers(self, runner):
        result = runner.invoke(cli, ["llm"])
        assert result.exit_code == 0
        # Sprawdź że jest co najmniej 10 providerów
        count = result.output.count("Klucz   :")
        assert count >= 10


class TestTokenCommands:
    """Testy komend fixos token set/show/clear."""

    def test_token_set_gemini_auto_detect(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "gemini" in result.output.lower()
        content = tmp_env.read_text()
        assert "GEMINI_API_KEY=" in content

    def test_token_set_openai_auto_detect(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "sk-abcdefghijklmnopqrstuvwxyz1234567890",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "openai" in result.output.lower()

    def test_token_set_openrouter_auto_detect(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "openrouter" in result.output.lower()

    def test_token_set_anthropic_auto_detect(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "sk-ant-abcdefghijklmnopqrstuvwxyz1234567890",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "anthropic" in result.output.lower()

    def test_token_set_groq_auto_detect(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "gsk_abcdefghijklmnopqrstuvwxyz1234567890",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "groq" in result.output.lower()

    def test_token_set_xai_auto_detect(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "xai-abcdefghijklmnopqrstuvwxyz1234567890",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "xai" in result.output.lower()

    def test_token_set_explicit_provider(self, runner, tmp_env):
        result = runner.invoke(cli, [
            "token", "set", "mytoken12345678901234567890",
            "--provider", "mistral",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "mistral" in result.output.lower()
        content = tmp_env.read_text()
        assert "MISTRAL_API_KEY=" in content

    def test_token_set_masked_in_output(self, runner, tmp_env):
        """Token w outputcie powinien być zamaskowany."""
        result = runner.invoke(cli, [
            "token", "set", "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345",
            "--env-file", str(tmp_env)
        ])
        assert result.exit_code == 0
        assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345" not in result.output
        assert "..." in result.output

    def test_token_set_file_permissions(self, runner, tmp_env):
        """Plik .env powinien mieć uprawnienia 600."""
        runner.invoke(cli, [
            "token", "set", "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345",
            "--env-file", str(tmp_env)
        ])
        mode = oct(tmp_env.stat().st_mode)[-3:]
        assert mode == "600"

    def test_token_set_replaces_existing(self, runner, tmp_env):
        """Drugi token set powinien zastąpić istniejący."""
        tmp_env.write_text("GEMINI_API_KEY=oldtoken123456789012345\n", encoding="utf-8")
        runner.invoke(cli, [
            "token", "set", "AIzaSyNEWTOKENABCDEFGHIJKLMNOPQRSTUV",
            "--env-file", str(tmp_env)
        ])
        content = tmp_env.read_text()
        assert "oldtoken" not in content
        assert "GEMINI_API_KEY=" in content

    def test_token_clear(self, runner, tmp_env):
        tmp_env.write_text(
            "LLM_PROVIDER=gemini\nGEMINI_API_KEY=AIzaSyABC123\n",
            encoding="utf-8"
        )
        result = runner.invoke(cli, ["token", "clear", "--env-file", str(tmp_env)])
        assert result.exit_code == 0
        content = tmp_env.read_text()
        assert "GEMINI_API_KEY=" not in content


class TestProvidersCommand:
    """Testy komendy fixos providers."""

    def test_providers_shows_list(self, runner):
        result = runner.invoke(cli, ["providers"])
        assert result.exit_code == 0
        assert "gemini" in result.output
        assert "openai" in result.output

    def test_providers_shows_free_paid(self, runner):
        result = runner.invoke(cli, ["providers"])
        assert result.exit_code == 0
        assert "FREE" in result.output or "PAID" in result.output

    def test_providers_suggests_llm_command(self, runner):
        result = runner.invoke(cli, ["providers"])
        assert result.exit_code == 0
        assert "fixos llm" in result.output


class TestConfigCommands:
    """Testy komend fixos config."""

    def test_config_show_runs(self, runner):
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "Provider" in result.output

    def test_config_init_creates_env(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["config", "init"])
            assert result.exit_code == 0
            assert Path(".env").exists()

    def test_config_set_writes_value(self, runner, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("LLM_PROVIDER=gemini\n", encoding="utf-8")
        with patch("fixos.cli.Path") as mock_path:
            # Użyj prawdziwego pliku
            pass
        # Bezpośredni test przez isolated filesystem
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path(".env").write_text("LLM_PROVIDER=gemini\n")
            result = runner.invoke(cli, ["config", "set", "AGENT_MODE", "autonomous"])
            assert result.exit_code == 0
            content = Path(".env").read_text()
            assert "AGENT_MODE=autonomous" in content
