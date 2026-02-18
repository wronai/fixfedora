"""
Testy e2e anonimizacji – weryfikacja wszystkich warstw przepływu danych.

Warstwy:
  1. anonymize() – funkcja bazowa, wszystkie 10 wzorców
  2. Dane diagnostyczne → anonymize()
  3. HITL: dane → anonymize() → LLM prompt
  4. Autonomous: output komend → anonymize() → LLM
  5. Orchestrator: diagnostics + stdout/stderr → anonymize() → LLM
  6. Brak wycieków przez granicę LLM
"""

from __future__ import annotations

import getpass
import json
import os
import re
import socket
from unittest.mock import MagicMock, patch

import pytest

from fixfedora.utils.anonymizer import anonymize, AnonymizationReport

REAL_HOSTNAME = socket.gethostname()
REAL_USER = getpass.getuser()
REAL_HOME = os.path.expanduser("~")


def _assert_no_sensitive(text: str, label: str = ""):
    prefix = f"[{label}] " if label else ""
    assert REAL_HOSTNAME not in text, f"{prefix}Hostname wyciekł"
    assert f"192.168.10.55" not in text, f"{prefix}IP wyciekł"
    assert "aa:bb:cc:dd:ee:ff" not in text, f"{prefix}MAC wyciekł"
    assert "sk-abc123def456ghi789jkl012mno345pqr" not in text, f"{prefix}API token wyciekł"
    assert "mysecretpass123" not in text, f"{prefix}Hasło wyciekło"
    assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in text, f"{prefix}UUID wyciekł"


@pytest.fixture
def mock_cfg():
    from fixfedora.config import FixFedoraConfig
    return FixFedoraConfig(
        provider="gemini",
        api_key="AIzaSy_FAKE_TOKEN_FOR_TESTING_1234567890",
        model="gemini-2.5-flash-preview-04-17",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        agent_mode="hitl",
        session_timeout=60,
        show_anonymized_data=False,
        enable_web_search=False,
    )


# ══════════════════════════════════════════════════════════
#  WARSTWA 1: anonymize() – wszystkie wzorce
# ══════════════════════════════════════════════════════════

class TestAnonymizePatterns:

    def test_hostname_replaced(self):
        anon, report = anonymize(f"host={REAL_HOSTNAME}")
        assert REAL_HOSTNAME not in anon
        assert "[HOSTNAME]" in anon
        assert report.replacements.get("Hostname", 0) >= 1

    def test_username_replaced(self):
        anon, report = anonymize(f"user {REAL_USER} logged in")
        assert REAL_USER not in anon
        assert "[USER]" in anon

    def test_home_path_replaced(self):
        anon, _ = anonymize(f"config at {REAL_HOME}/.config")
        assert REAL_HOME not in anon

    def test_home_slash_pattern(self):
        anon, report = anonymize("/home/jankowalski/.ssh and /home/admin/.bashrc")
        assert "jankowalski" not in anon
        assert "admin" not in anon
        assert "/home/[USER]" in anon
        assert report.replacements.get("Ścieżki /home", 0) >= 2

    def test_ipv4_last_octets_masked(self):
        anon, report = anonymize("from 192.168.1.100 to 10.0.0.50")
        assert "192.168.1.100" not in anon
        assert "10.0.0.50" not in anon
        assert "192.168.XXX.XXX" in anon
        assert report.replacements.get("Adresy IPv4", 0) == 2

    def test_ipv4_preserves_first_two_octets(self):
        anon, _ = anonymize("gateway 192.168.1.1")
        assert "192.168" in anon

    def test_mac_replaced(self):
        anon, report = anonymize("device aa:bb:cc:dd:ee:ff connected")
        assert "aa:bb:cc:dd:ee:ff" not in anon
        assert "XX:XX:XX:XX:XX:XX" in anon

    def test_sk_token_replaced(self):
        anon, report = anonymize("key=sk-abc123def456ghi789jkl012mno345pqr678stu")
        assert "sk-abc123def456ghi789jkl012mno345pqr678stu" not in anon
        assert "[API_TOKEN_REDACTED]" in anon

    def test_openrouter_token_replaced(self):
        anon, _ = anonymize("sk-or-v1-abc123def456ghi789jkl012mno345pqr678stu901vwx")
        assert "sk-or-v1-abc123def456ghi789jkl012mno345pqr678stu901vwx" not in anon

    def test_xai_token_replaced(self):
        anon, _ = anonymize("XAI_API_KEY=xai-ABCDEF1234567890abcdef1234567890xyz")
        assert "xai-ABCDEF1234567890abcdef1234567890xyz" not in anon

    def test_gemini_token_replaced(self):
        anon, _ = anonymize("GEMINI_API_KEY=AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456")
        assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in anon

    def test_password_replaced(self):
        anon, report = anonymize("DB_PASSWORD=mysecretpass123 API_KEY=abc123def456ghi")
        assert "mysecretpass123" not in anon
        assert report.replacements.get("Hasła/sekrety", 0) >= 1

    def test_uuid_replaced(self):
        anon, report = anonymize("UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in anon
        assert "[UUID-REDACTED]" in anon

    def test_serial_replaced(self):
        anon, report = anonymize("Serial: PF1A2B3C4D, SN: XYZ123456")
        assert "PF1A2B3C4D" not in anon
        assert "XYZ123456" not in anon

    def test_multiple_occurrences(self):
        anon, report = anonymize(f"{REAL_HOSTNAME} {REAL_HOSTNAME} {REAL_HOSTNAME}")
        assert REAL_HOSTNAME not in anon
        assert report.replacements.get("Hostname", 0) == 3

    def test_non_sensitive_unchanged(self):
        data = "systemctl status pipewire -- Active: running"
        anon, _ = anonymize(data)
        assert "systemctl" in anon
        assert "pipewire" in anon

    def test_empty_string(self):
        anon, report = anonymize("")
        assert anon == ""
        assert len(report.replacements) == 0

    def test_dict_input(self):
        anon, _ = anonymize({"host": REAL_HOSTNAME})
        assert REAL_HOSTNAME not in anon

    def test_localhost_not_masked(self):
        anon, _ = anonymize("connect to localhost:8080")
        assert "localhost" in anon

    def test_ipv6_not_broken(self):
        anon, _ = anonymize("IPv6: 2001:db8::1")
        assert isinstance(anon, str)

    def test_report_size_tracking(self):
        data = "hello world"
        anon, report = anonymize(data)
        assert report.original_length == len(data)
        assert report.anonymized_length == len(anon)


# ══════════════════════════════════════════════════════════
#  WARSTWA 2: Dane diagnostyczne → anonymize()
# ══════════════════════════════════════════════════════════

class TestDiagnosticsAnonymization:

    def _make_diag(self) -> dict:
        return {
            "system": {
                "os_release": f"NAME=Fedora\nHOSTNAME={REAL_HOSTNAME}",
                "journal_errors_24h": (
                    f"Feb 18 {REAL_HOSTNAME} systemd: Failed\n"
                    f"Config at /home/{REAL_USER}/.config"
                ),
                "dnf_history": f"user {REAL_USER} ran dnf upgrade",
            },
            "audio": {
                "pactl_info": f"User Name: {REAL_USER}\nHost Name: {REAL_HOSTNAME}",
                "alsa_cards": "0 [PCH]: HDA-Intel",
            },
            "thumbnails": {
                "thumbnail_cache_size": f"86M\t{REAL_HOME}/.cache/thumbnails/",
            },
            "hardware": {
                "dmi_product": "Yoga 7",
                "sensors": "Package id 0: +73.0°C",
            },
        }

    def test_hostname_not_in_anonymized(self):
        anon, report = anonymize(str(self._make_diag()))
        assert REAL_HOSTNAME not in anon
        assert report.replacements.get("Hostname", 0) > 0

    def test_username_not_in_anonymized(self):
        anon, _ = anonymize(str(self._make_diag()))
        pattern = rf"\b{re.escape(REAL_USER)}\b"
        assert not re.search(pattern, anon)

    def test_home_path_not_in_anonymized(self):
        anon, _ = anonymize(str(self._make_diag()))
        assert REAL_HOME not in anon

    def test_pactl_info_anonymized(self):
        data = f"User Name: {REAL_USER}\nHost Name: {REAL_HOSTNAME}\nServer: PipeWire"
        anon, _ = anonymize(data)
        assert REAL_HOSTNAME not in anon
        assert REAL_USER not in anon
        assert "PipeWire" in anon

    def test_journal_errors_anonymized(self):
        data = f"Feb 18 {REAL_HOSTNAME} kernel: OOM in /home/{REAL_USER}/app"
        anon, _ = anonymize(data)
        assert REAL_HOSTNAME not in anon
        assert REAL_USER not in anon

    def test_full_diag_no_leaks(self):
        anon, _ = anonymize(str(self._make_diag()))
        assert REAL_HOSTNAME not in anon
        assert REAL_HOME not in anon


# ══════════════════════════════════════════════════════════
#  WARSTWA 3: HITL → LLM prompt
# ══════════════════════════════════════════════════════════

class TestHITLAnonymizationLayer:

    @patch("fixfedora.providers.llm.openai")
    def test_llm_prompt_no_hostname(self, mock_openai, mock_cfg):
        from fixfedora.agent.hitl import run_hitl_session

        captured = []

        def capture(**kwargs):
            for msg in kwargs.get("messages", []):
                captured.append(msg.get("content", ""))
            resp = MagicMock()
            resp.choices[0].message.content = "q"
            resp.usage.total_tokens = 10
            return resp

        mock_openai.OpenAI.return_value.chat.completions.create.side_effect = capture

        diagnostics = {
            "system": {
                "os_release": f"NAME=Fedora\nHOSTNAME={REAL_HOSTNAME}",
                "journal_errors_24h": f"Feb 18 {REAL_HOSTNAME} error in /home/{REAL_USER}",
            }
        }

        with patch("builtins.input", side_effect=["y", "q"]):
            run_hitl_session(diagnostics=diagnostics, config=mock_cfg, show_data=False)

        for content in captured:
            assert REAL_HOSTNAME not in content, f"Hostname wyciekł do LLM: {content[:200]}"

    @patch("fixfedora.providers.llm.openai")
    def test_llm_prompt_no_username(self, mock_openai, mock_cfg):
        from fixfedora.agent.hitl import run_hitl_session

        captured = []

        def capture(**kwargs):
            for msg in kwargs.get("messages", []):
                captured.append(msg.get("content", ""))
            resp = MagicMock()
            resp.choices[0].message.content = "q"
            resp.usage.total_tokens = 10
            return resp

        mock_openai.OpenAI.return_value.chat.completions.create.side_effect = capture

        diagnostics = {
            "system": {
                "os_release": "NAME=Fedora",
                "dnf_history": f"user {REAL_USER} ran dnf",
            }
        }

        with patch("builtins.input", side_effect=["y", "q"]):
            run_hitl_session(diagnostics=diagnostics, config=mock_cfg, show_data=False)

        pattern = rf"\b{re.escape(REAL_USER)}\b"
        for content in captured:
            assert not re.search(pattern, content), f"Username wyciekł do LLM"

    def test_user_rejects_send_no_llm_call(self, mock_cfg):
        """Gdy użytkownik odpowie 'n', LLM nie powinien być wywołany."""
        from fixfedora.agent.hitl import run_hitl_session

        with patch("fixfedora.providers.llm.openai") as mock_openai:
            mock_openai.OpenAI.return_value.chat.completions.create.return_value = MagicMock()

            with patch("builtins.input", return_value="n"):
                run_hitl_session(
                    diagnostics={"system": {"os_release": "Fedora"}},
                    config=mock_cfg,
                    show_data=True,
                )

            mock_openai.OpenAI.return_value.chat.completions.create.assert_not_called()


# ══════════════════════════════════════════════════════════
#  WARSTWA 4: Autonomous – output komend → LLM
# ══════════════════════════════════════════════════════════

class TestAutonomousAnonymizationLayer:

    def test_command_output_anonymized(self):
        raw = (
            f"User Name: {REAL_USER}\n"
            f"Host Name: {REAL_HOSTNAME}\n"
            f"Config: /home/{REAL_USER}/.config\n"
            "Server: PipeWire 1.4.7"
        )
        anon, _ = anonymize(raw)
        assert REAL_HOSTNAME not in anon
        assert REAL_USER not in anon
        assert "PipeWire 1.4.7" in anon

    @patch("fixfedora.providers.llm.openai")
    def test_exec_output_anonymized_before_llm(self, mock_openai, mock_cfg):
        from fixfedora.agent.autonomous import run_autonomous_session
        from fixfedora.config import FixFedoraConfig

        auto_cfg = FixFedoraConfig(
            provider="gemini",
            api_key="AIzaSy_FAKE_TOKEN_FOR_TESTING_1234567890",
            model="gemini-2.5-flash-preview-04-17",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            agent_mode="autonomous",
            session_timeout=60,
            show_anonymized_data=False,
            enable_web_search=False,
        )

        captured_messages = []
        call_count = [0]

        def capture(**kwargs):
            call_count[0] += 1
            captured_messages.extend(kwargs.get("messages", []))
            resp = MagicMock()
            if call_count[0] == 1:
                resp.choices[0].message.content = json.dumps({
                    "analysis": "test",
                    "severity": "low",
                    "action": "EXEC",
                    "command": f"echo 'host={REAL_HOSTNAME} user={REAL_USER}'",
                    "reason": "test",
                    "next_step": "done",
                })
            else:
                resp.choices[0].message.content = json.dumps({
                    "analysis": "done",
                    "severity": "low",
                    "action": "DONE",
                    "command": "",
                    "reason": "finished",
                    "next_step": "none",
                })
            resp.usage.total_tokens = 50
            return resp

        mock_openai.OpenAI.return_value.chat.completions.create.side_effect = capture

        with patch("builtins.input", return_value="yes"):
            run_autonomous_session(
                diagnostics={"system": {"os_release": "NAME=Fedora"}},
                config=auto_cfg,
                show_data=False,
                max_fixes=2,
            )

        for msg in captured_messages:
            content = msg.get("content", "")
            if "Wykonano:" in content:
                assert REAL_HOSTNAME not in content, (
                    f"Hostname wyciekł w output komendy: {content[:300]}"
                )
                assert REAL_USER not in content, (
                    f"Username wyciekł w output komendy: {content[:300]}"
                )


# ══════════════════════════════════════════════════════════
#  WARSTWA 5: Orchestrator → LLM
# ══════════════════════════════════════════════════════════

class TestOrchestratorAnonymizationLayer:

    @patch("fixfedora.providers.llm.openai")
    def test_diagnostics_anonymized_in_prompt(self, mock_openai, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator

        captured = []

        def capture(**kwargs):
            for msg in kwargs.get("messages", []):
                captured.append(msg.get("content", ""))
            resp = MagicMock()
            resp.choices[0].message.content = json.dumps({
                "new_problems": [], "explanation": "ok"
            })
            resp.usage.total_tokens = 50
            return resp

        mock_openai.OpenAI.return_value.chat.completions.create.side_effect = capture

        diagnostics = {
            "system": {
                "os_release": f"NAME=Fedora\nHOSTNAME={REAL_HOSTNAME}",
                "journal_errors_24h": f"Feb 18 {REAL_HOSTNAME} error /home/{REAL_USER}",
            },
            "audio": {
                "pactl_info": f"User Name: {REAL_USER}\nHost Name: {REAL_HOSTNAME}",
            },
        }

        orch = FixOrchestrator(config=mock_cfg)
        orch.load_from_diagnostics(diagnostics)

        for content in captured:
            assert REAL_HOSTNAME not in content, f"Hostname wyciekł w orchestrate diagnose"
            assert REAL_USER not in content, f"Username wyciekł w orchestrate diagnose"

    @patch("fixfedora.providers.llm.openai")
    def test_stdout_stderr_anonymized_in_evaluate(self, mock_openai, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator
        from fixfedora.orchestrator.graph import Problem
        from fixfedora.orchestrator.executor import ExecutionResult

        captured = []

        def capture(**kwargs):
            for msg in kwargs.get("messages", []):
                captured.append(msg.get("content", ""))
            resp = MagicMock()
            resp.choices[0].message.content = json.dumps({
                "verdict": "resolved", "confidence": 0.95,
                "new_problems": [], "explanation": "ok"
            })
            resp.usage.total_tokens = 50
            return resp

        mock_openai.OpenAI.return_value.chat.completions.create.side_effect = capture

        orch = FixOrchestrator(config=mock_cfg)
        problem = Problem(id="p1", description="test", severity="info", fix_commands=[])

        result = ExecutionResult(
            command="pactl info",
            returncode=0,
            stdout=f"User Name: {REAL_USER}\nHost Name: {REAL_HOSTNAME}\nCookie: 6245:357a",
            stderr=f"warning: /home/{REAL_USER}/.config missing",
            executed=True,
        )

        orch._evaluate_and_rediagnose(problem, result)

        for content in captured:
            assert REAL_HOSTNAME not in content, f"Hostname wyciekł w evaluate stdout"
            assert REAL_USER not in content, f"Username wyciekł w evaluate stderr"


# ══════════════════════════════════════════════════════════
#  WARSTWA 6: Granica LLM – żadne surowe dane nie trafiają
# ══════════════════════════════════════════════════════════

class TestLLMBoundaryNoLeaks:
    """Testy granicy LLM – weryfikacja że żadne surowe dane nie trafiają do API."""

    def test_anonymize_before_any_llm_call(self):
        """Dane muszą być anonimizowane przed jakimkolwiek wywołaniem LLM."""
        sensitive = _make_sensitive_string()
        anon, report = anonymize(sensitive)
        _assert_no_sensitive(anon, "llm_boundary")
        assert len(report.replacements) >= 3

    def test_anonymize_idempotent(self):
        """Podwójna anonimizacja nie powinna powodować problemów."""
        data = f"host={REAL_HOSTNAME} ip=192.168.1.100"
        anon1, _ = anonymize(data)
        anon2, _ = anonymize(anon1)
        assert anon1 == anon2

    def test_anonymize_preserves_technical_info(self):
        """Dane techniczne (nie wrażliwe) muszą być zachowane dla LLM."""
        data = (
            f"host={REAL_HOSTNAME} "
            "systemctl status pipewire -- Active: running "
            "sof-firmware version 2024.03 "
            "kernel 6.8.9-300.fc40.x86_64"
        )
        anon, _ = anonymize(data)
        assert "systemctl" in anon
        assert "pipewire" in anon
        assert "sof-firmware" in anon
        assert "6.8.9-300.fc40.x86_64" in anon

    def test_nested_sensitive_in_dict(self):
        """Wrażliwe dane zagnieżdżone w dict muszą być anonimizowane."""
        data = {
            "level1": {
                "level2": {
                    "hostname": REAL_HOSTNAME,
                    "ip": "192.168.5.100",
                    "token": "sk-abc123def456ghi789jkl012mno345pqr",
                }
            }
        }
        anon, _ = anonymize(str(data))
        assert REAL_HOSTNAME not in anon
        assert "192.168.5.100" not in anon
        assert "sk-abc123def456ghi789jkl012mno345pqr" not in anon

    def test_multiline_journal_log_anonymized(self):
        """Wieloliniowe logi journald muszą być w pełni anonimizowane."""
        log = "\n".join([
            f"Feb 18 {REAL_HOSTNAME} systemd[1]: Started service",
            f"Feb 18 {REAL_HOSTNAME} kernel: [drm] error",
            f"Feb 18 {REAL_HOSTNAME} pipewire[1234]: mod.client-node: detected old client",
            f"Feb 18 {REAL_HOSTNAME} (python3)[5678]: service failed /home/{REAL_USER}/app",
        ])
        anon, report = anonymize(log)
        assert REAL_HOSTNAME not in anon
        assert REAL_USER not in anon
        assert "systemd" in anon
        assert "pipewire" in anon
        assert report.replacements.get("Hostname", 0) >= 4

    def test_dmesg_output_anonymized(self):
        """Output dmesg z adresami PCI/USB musi być anonimizowany."""
        dmesg = (
            f"[    5.123] {REAL_HOSTNAME} snd_hda_intel: no codecs found\n"
            "[    5.456] usb 2-2: device not accepting address 3\n"
            "[ 1234.567] sof-audio-pci: probe failed with error -19"
        )
        anon, _ = anonymize(dmesg)
        assert REAL_HOSTNAME not in anon
        assert "snd_hda_intel" in anon
        assert "sof-audio-pci" in anon

    def test_env_file_content_anonymized(self):
        """Zawartość pliku .env z tokenami musi być anonimizowana."""
        env_content = (
            f"LLM_PROVIDER=openrouter\n"
            f"OPENROUTER_API_KEY=sk-or-v1-abc123def456ghi789jkl012mno345pqr678stu901vwx\n"
            f"GEMINI_API_KEY=AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n"
            f"DB_PASSWORD=supersecret123\n"
        )
        anon, report = anonymize(env_content)
        assert "sk-or-v1-abc123def456ghi789jkl012mno345pqr678stu901vwx" not in anon
        assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in anon
        assert "supersecret123" not in anon
        assert len(report.replacements) >= 2

    def test_sensor_output_not_anonymized(self):
        """Dane z czujników temperatury nie zawierają wrażliwych danych."""
        sensors = (
            "coretemp-isa-0000\n"
            "Package id 0:  +73.0°C  (high = +100.0°C)\n"
            "Core 0:        +60.0°C\n"
        )
        anon, report = anonymize(sensors)
        assert "+73.0°C" in anon
        assert len(report.replacements) == 0

    def test_anonymization_report_summary_format(self):
        data = f"host={REAL_HOSTNAME} ip=192.168.1.1 mac=aa:bb:cc:dd:ee:ff"
        _, report = anonymize(data)
        summary = report.summary()
        assert "wystąpień" in summary
        assert "✓" in summary


def _make_sensitive_string() -> str:
    return (
        f"host={REAL_HOSTNAME} user={REAL_USER} home={REAL_HOME}/.config "
        "ip=192.168.10.55 mac=aa:bb:cc:dd:ee:ff "
        "sk-abc123def456ghi789jkl012mno345pqr password=mysecretpass123 "
        "UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    )
