"""
Konfiguracja testów e2e / unit fixfedora.
Fixtures: mock LLM, mock diagnostics, simulated broken environments.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fixfedora.config import FixFedoraConfig


# ── Helpers ───────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _has_real_token() -> bool:
    """Sprawdza czy .env zawiera prawdziwy token API."""
    cfg = FixFedoraConfig.load()
    key = cfg.api_key or ""
    return len(key) > 10 and "TWOJ" not in key and "KLUCZ" not in key


# ══════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def real_api_available() -> bool:
    return _has_real_token()


@pytest.fixture(scope="session")
def test_config() -> FixFedoraConfig:
    """Konfiguracja testowa załadowana z .env."""
    return FixFedoraConfig.load()


@pytest.fixture
def mock_config() -> FixFedoraConfig:
    """Konfiguracja z fake tokenem do testów bez API."""
    cfg = FixFedoraConfig(
        provider="gemini",
        api_key="AIzaSy_FAKE_TOKEN_FOR_TESTING_ONLY_1234567",
        model="gemini-2.5-flash-preview-04-17",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        agent_mode="hitl",
        session_timeout=60,
        show_anonymized_data=False,
        enable_web_search=False,
    )
    return cfg


@pytest.fixture
def mock_llm_client(mock_config):
    """Mock LLMClient zwracający predefiniowane odpowiedzi."""
    with patch("fixfedora.providers.llm.openai") as mock_openai:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = """
━━━ DIAGNOZA ━━━
🔴 Problem 1: Brak kart dźwiękowych ALSA – brak sterownika SOF
   → Fix: `sudo dnf install sof-firmware`
🟡 Problem 2: PipeWire nie działa
   → Fix: `systemctl --user restart pipewire wireplumber`
🟢 Problem 3: Cache miniaturek pusty
   → Fix: `nautilus -q && rm -rf ~/.cache/thumbnails/*`
"""
        mock_response.usage.total_tokens = 350
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_response
        yield mock_openai


@pytest.fixture
def broken_audio_diagnostics() -> dict[str, Any]:
    """Dane diagnostyczne symulujące uszkodzony dźwięk (Lenovo Yoga)."""
    return {
        "system": {
            "kernel": "6.8.9-300.fc40.x86_64",
            "os_release": "NAME=Fedora\nVERSION=40\nID=fedora",
            "systemctl_failed": "  bluetooth.service  loaded failed failed Bluetooth service",
            "dnf_updates_pending": "3",
        },
        "audio": {
            "alsa_cards": "--- no soundcards ---",
            "alsa_devices": "aplay: device_list:274: no soundcards found...",
            "alsa_capture": "arecord: device_list:274: no soundcards found...",
            "sof_firmware": "[ERR]: ls: cannot access '/lib/firmware/intel/sof*': No such file or directory",
            "sof_modules": "",
            "pipewire_status": "● pipewire.service - PipeWire Multimedia Service\n   Active: failed (Result: exit-code)",
            "wireplumber_status": "● wireplumber.service\n   Active: failed (Result: exit-code)",
            "audio_packages": "pipewire-1.0.4-1.fc40.x86_64\npipewire-pulseaudio-1.0.4-1.fc40.x86_64",
            "sof_firmware_pkg": "package sof-firmware is not installed",
            "kernel_audio_dmesg": (
                "[ 5.123] snd_hda_intel: no codecs found!\n"
                "[ 5.456] sof-audio-pci-intel-tgl: probe failed with error -19"
            ),
            "lenovo_ideapad": "ideapad_laptop 28672 0",
        },
        "thumbnails": {
            "thumbnailers_installed": "",
            "thumbnail_cache_count": "0",
            "ffmpegthumbnailer": "ffmpegthumbnailer nie zainstalowany",
            "totem_thumb": "totem-video-thumbnailer nie znaleziony",
            "thumbnailer_packages": "",
            "desktop_env": "GNOME",
        },
        "hardware": {
            "dmi_product": "Yoga 7 14ARB7",
            "dmi_vendor": "LENOVO",
            "bios_version": "J2CN45WW",
            "cpu_model": "AMD Ryzen 5 7530U",
            "gpu_info": "00:02.0 Display controller: AMD/ATI",
        },
    }


@pytest.fixture
def broken_thumbnails_diagnostics() -> dict[str, Any]:
    """Dane diagnostyczne symulujące brak podglądów plików."""
    return {
        "system": {
            "kernel": "6.8.9-300.fc40.x86_64",
            "os_release": "NAME=Fedora\nVERSION=40\nID=fedora",
            "systemctl_failed": "",
        },
        "audio": {
            "alsa_cards": " 0 [PCH]: HDA-Intel - HDA Intel PCH",
            "pipewire_status": "Active: active (running)",
        },
        "thumbnails": {
            "desktop_env": "GNOME",
            "nautilus_version": "Nautilus 46.2",
            "thumbnailers_installed": "(brak outputu)",
            "gdk_pixbuf_loaders": "0",
            "thumbnailer_configs": "total 0",
            "thumbnail_cache_size": "4.0K\t/root/.cache/thumbnails/",
            "thumbnail_cache_count": "0",
            "thumbnail_fail_files": "47",  # Dużo failed thumbnails = problem
            "ffmpegthumbnailer": "ffmpegthumbnailer nie zainstalowany",
            "totem_thumb": "totem-video-thumbnailer nie znaleziony",
            "thumbnailer_packages": "",
            "gsettings_thumbnails": "'local-only'\nuint64 512",
            "gst_bad_good": "",
        },
        "hardware": {
            "dmi_product": "Yoga 7 14ARB7",
            "dmi_vendor": "LENOVO",
        },
    }


@pytest.fixture
def full_broken_diagnostics(broken_audio_diagnostics, broken_thumbnails_diagnostics) -> dict:
    """Dane diagnostyczne z wieloma jednoczesne problemami."""
    combined = dict(broken_audio_diagnostics)
    combined["thumbnails"] = broken_thumbnails_diagnostics["thumbnails"]
    combined["system"]["dnf_updates_pending"] = "15"
    combined["system"]["dmesg_errors"] = (
        "[drm:intel_dp_start_link_train] ERROR failed to start link training\n"
        "usb 2-2: device not accepting address 3, error -71"
    )
    return combined
