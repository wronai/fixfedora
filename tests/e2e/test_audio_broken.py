"""
Testy e2e – scenariusz uszkodzonego dźwięku (Lenovo Yoga / SOF firmware).
Używa mock LLM lub prawdziwego API (jeśli dostępny token w .env).
"""

from __future__ import annotations

import json
import os
import re
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests in this module if psutil not available (e.g. goal tool's env)
pytest.importorskip("psutil")

from fixfedora.utils.anonymizer import anonymize
from fixfedora.diagnostics.system_checks import diagnose_audio, diagnose_hardware


class TestAudioAnonymization:
    """Testy anonimizacji danych audio."""

    def test_anonymize_hostname(self, broken_audio_diagnostics):
        """Hostname nie powinien być w zanonimizowanych danych."""
        import socket
        hostname = socket.gethostname()
        data_str = str(broken_audio_diagnostics)
        data_str += f" hostname={hostname}"

        anon, report = anonymize(data_str)
        assert hostname not in anon
        assert "[HOSTNAME]" in anon
        assert report.replacements.get("Hostname", 0) > 0

    def test_anonymize_ipv4(self):
        """Adresy IP powinny być zamaskowane."""
        data = "connection to 192.168.1.100 failed, also 10.0.0.1"
        anon, report = anonymize(data)
        assert "192.168.1.100" not in anon
        assert "10.0.0.1" not in anon
        assert "XXX" in anon
        assert report.replacements.get("Adresy IPv4", 0) == 2

    def test_anonymize_mac(self):
        """Adresy MAC powinny być zamaskowane."""
        data = "device aa:bb:cc:dd:ee:ff connected"
        anon, report = anonymize(data)
        assert "aa:bb:cc:dd:ee:ff" not in anon
        assert "XX:XX:XX:XX:XX:XX" in anon

    def test_anonymize_api_token(self):
        """Tokeny API muszą być maskowane."""
        data = "using key AIzaSyABC123DEF456GHI789JKL-testtoken"
        anon, report = anonymize(data)
        assert "AIzaSyABC123DEF456GHI789JKL-testtoken" not in anon
        assert "[API_TOKEN_REDACTED]" in anon

    def test_anonymize_home_path(self):
        """Ścieżki /home/<user> powinny być maskowane."""
        data = "config at /home/jankowalski/.config and /home/admin/keys"
        anon, report = anonymize(data)
        assert "jankowalski" not in anon
        assert "/home/[USER]" in anon

    def test_anonymize_uuid(self):
        """UUID hardware identifiers powinny być maskowane."""
        data = "disk UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890 mounted"
        anon, report = anonymize(data)
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in anon


class TestAudioDiagnosticsDetection:
    """Testy wykrywania problemów audio z danych diagnostycznych."""

    def test_detect_missing_sof_firmware(self, broken_audio_diagnostics):
        """Powinien wykryć brak sof-firmware."""
        audio = broken_audio_diagnostics["audio"]
        sof = audio.get("sof_firmware", "")
        sof_pkg = audio.get("sof_firmware_pkg", "")

        # Brak firmware w systemie plików
        has_sof_files = "sof" in sof.lower() and "[ERR]" not in sof
        # Brak pakietu
        pkg_missing = "not installed" in sof_pkg.lower()

        assert not has_sof_files, "SOF firmware powinno być brakujące w tym scenariuszu"
        assert pkg_missing, "Pakiet sof-firmware powinien być niezainstalowany"

    def test_detect_no_alsa_cards(self, broken_audio_diagnostics):
        """Powinien wykryć brak kart ALSA."""
        audio = broken_audio_diagnostics["audio"]
        cards = audio.get("alsa_cards", "")
        assert "no soundcards" in cards.lower() or cards.strip() == ""

    def test_detect_pipewire_failed(self, broken_audio_diagnostics):
        """Powinien wykryć failed PipeWire."""
        audio = broken_audio_diagnostics["audio"]
        pw_status = audio.get("pipewire_status", "")
        assert "failed" in pw_status.lower()

    def test_detect_lenovo_hardware(self, broken_audio_diagnostics):
        """Powinien rozpoznać hardware Lenovo Yoga."""
        hw = broken_audio_diagnostics["hardware"]
        vendor = hw.get("dmi_vendor", "").upper()
        product = hw.get("dmi_product", "").upper()
        assert "LENOVO" in vendor
        assert "YOGA" in product

    def test_kernel_dmesg_sof_error(self, broken_audio_diagnostics):
        """Powinien wykryć błędy SOF w dmesg."""
        audio = broken_audio_diagnostics["audio"]
        dmesg = audio.get("kernel_audio_dmesg", "")
        assert "sof" in dmesg.lower() or "probe failed" in dmesg.lower()


class TestAudioDiagnosticsMockLLM:
    """Testy z mock LLM – weryfikacja że dane są poprawnie przesyłane."""

    def test_llm_receives_anonymized_data(self, broken_audio_diagnostics, mock_config):
        """LLM powinien otrzymywać zanonimizowane dane, nie surowe."""
        from fixfedora.utils.anonymizer import anonymize
        import socket

        # Dodaj wrażliwe dane do diagnostics
        data = dict(broken_audio_diagnostics)
        data["_test_hostname"] = socket.gethostname()

        anon_str, report = anonymize(str(data))

        # Hostname nie powinien być w danych wysyłanych do LLM
        hostname = socket.gethostname()
        assert hostname not in anon_str

    def test_anonymization_report_not_empty(self, broken_audio_diagnostics):
        """Raport anonimizacji powinien zawierać co najmniej jedną kategorię."""
        import socket, getpass
        data = str(broken_audio_diagnostics)
        data += f" host={socket.gethostname()} user={getpass.getuser()}"

        _, report = anonymize(data)
        assert len(report.replacements) > 0

    @patch("fixfedora.providers.llm.openai")
    def test_llm_called_with_sof_context(self, mock_openai, broken_audio_diagnostics, mock_config):
        """LLM powinien być wywołany z danymi zawierającymi info o SOF."""
        from fixfedora.providers.llm import LLMClient

        # Setup mock
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Zalecam: sudo dnf install sof-firmware"
        mock_resp.usage.total_tokens = 100
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_resp

        client = LLMClient(mock_config)
        anon_str, _ = anonymize(str(broken_audio_diagnostics))
        messages = [
            {"role": "system", "content": "Jesteś diagnostą Fedora."},
            {"role": "user", "content": f"Dane:\n{anon_str}"},
        ]
        reply = client.chat(messages)

        # Sprawdź że API zostało wywołane
        assert mock_openai.OpenAI.return_value.chat.completions.create.called
        # Sprawdź że odpowiedź zawiera sugestię
        assert "sof-firmware" in reply.lower()

    @patch("fixfedora.providers.llm.openai")
    def test_llm_rate_limit_retry(self, mock_openai, mock_config):
        """LLM powinien retry przy rate limit."""
        import openai as real_openai
        from fixfedora.providers.llm import LLMClient

        mock_create = mock_openai.OpenAI.return_value.chat.completions.create
        mock_openai.RateLimitError = real_openai.RateLimitError

        # Pierwsze dwa wywołania: rate limit, trzecie: sukces
        mock_success = MagicMock()
        mock_success.choices[0].message.content = "Sukces po retry"
        mock_success.usage.total_tokens = 50

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise real_openai.RateLimitError(
                    "rate limit", response=MagicMock(status_code=429), body={}
                )
            return mock_success

        mock_create.side_effect = side_effect

        with patch("time.sleep"):  # Nie czekaj w testach
            client = LLMClient(mock_config)
            reply = client.chat([{"role": "user", "content": "test"}])

        assert reply == "Sukces po retry"
        assert call_count[0] == 3


class TestAudioDiagnosticsReal:
    """Testy z prawdziwym API – uruchamiane tylko gdy token dostępny."""

    @pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY") or "TWOJ" in os.environ.get("GEMINI_API_KEY", ""),
        reason="Wymaga prawdziwego GEMINI_API_KEY w .env"
    )
    def test_real_llm_analyzes_audio(self, broken_audio_diagnostics, test_config):
        """Prawdziwy LLM powinien wykryć problemy SOF w danych audio."""
        from fixfedora.providers.llm import LLMClient
        from fixfedora.utils.anonymizer import anonymize

        client = LLMClient(test_config)
        anon_str, _ = anonymize(str(broken_audio_diagnostics))

        messages = [
            {
                "role": "system",
                "content": "Jesteś diagnostą Fedora. Krótko (max 5 zdań) wskaż główny problem audio."
            },
            {
                "role": "user",
                "content": f"Dane diagnostyczne Lenovo Yoga:\n{anon_str[:2000]}"
            }
        ]

        reply = client.chat(messages, max_tokens=200)

        # Odpowiedź powinna zawierać relevantne terminy
        relevant_terms = ["sof", "firmware", "alsa", "pipewire", "audio", "dźwięk", "sterownik"]
        reply_lower = reply.lower()
        found = [t for t in relevant_terms if t in reply_lower]

        assert len(found) >= 2, (
            f"LLM nie wykrył problemów audio. Odpowiedź: {reply[:300]}\n"
            f"Oczekiwane terminy: {relevant_terms}"
        )
        print(f"\n✅ LLM wykrył: {found}\nOdpowiedź: {reply[:300]}")
