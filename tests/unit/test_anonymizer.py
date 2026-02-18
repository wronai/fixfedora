"""
Testy jednostkowe – anonymizer (v2.2 fixes).
Pokrywa: pyenv paths, kolejność zastąpień, pełne ścieżki /home.
"""

from __future__ import annotations

import getpass
import socket

import pytest

from fixos.utils.anonymizer import anonymize, AnonymizationReport


class TestHomePaths:
    """Testy anonimizacji ścieżek /home – fix v2.2."""

    def test_pyenv_full_path_anonymized(self):
        """Pełna ścieżka /home/user/.pyenv/versions/... musi być zamaskowana."""
        username = getpass.getuser()
        data = f"/home/{username}/.pyenv/versions/3.12.0/bin/python3.12"
        anon, report = anonymize(data)
        assert username not in anon
        assert "/home/[USER]" in anon

    def test_deep_nested_home_path(self):
        """Głęboko zagnieżdżona ścieżka /home/user/a/b/c/d musi być zamaskowana."""
        data = "/home/jankowalski/projects/myapp/src/utils/helper.py"
        anon, _ = anonymize(data)
        assert "jankowalski" not in anon
        assert "/home/[USER]" in anon

    def test_multiple_home_paths_all_masked(self):
        """Wiele ścieżek /home w jednym stringu – wszystkie muszą być zamaskowane."""
        data = (
            "python at /home/alice/.pyenv/versions/3.11/bin/python "
            "config at /home/alice/.config/fixos/settings.conf "
            "log at /home/alice/.local/share/fixos/session.log"
        )
        anon, report = anonymize(data)
        assert "alice" not in anon
        assert anon.count("/home/[USER]") >= 1

    def test_home_path_with_spaces_in_context(self):
        """Ścieżka /home/user/... w kontekście z innymi słowami."""
        data = "executable: /home/tom/.local/bin/fixos version 2.2"
        anon, _ = anonymize(data)
        assert "tom" not in anon

    def test_home_path_in_error_message(self):
        """Ścieżka /home/user w komunikacie błędu."""
        data = "FileNotFoundError: /home/testuser/.config/app.conf not found"
        anon, _ = anonymize(data)
        assert "testuser" not in anon
        assert "/home/[USER]" in anon

    def test_home_path_already_anonymized_not_double_replaced(self):
        """Już zanonimizowana ścieżka /home/[USER] nie powinna być podwójnie zastąpiona."""
        data = "/home/[USER]/some/path"
        anon, report = anonymize(data)
        assert "/home/[USER]" in anon
        assert "/home/[USER]/[USER]" not in anon

    def test_non_home_paths_not_affected(self):
        """Ścieżki poza /home nie powinny być zmieniane."""
        data = "config at /etc/fixos/config and /usr/local/bin/fixos"
        anon, report = anonymize(data)
        assert "/etc/fixos/config" in anon
        assert "/usr/local/bin/fixos" in anon

    def test_literal_home_dir_replaced_first(self):
        """Dosłowny katalog domowy (~) powinien być zastąpiony przed regex."""
        import os
        home = os.path.expanduser("~")
        data = f"path: {home}/.config/fixos"
        anon, report = anonymize(data)
        assert home not in anon

    def test_username_replaced_after_paths(self):
        """Username jako słowo powinien być zastąpiony nawet po zastąpieniu ścieżek."""
        username = getpass.getuser()
        data = f"user {username} logged in from /home/{username}/.ssh/id_rsa"
        anon, report = anonymize(data)
        assert username not in anon


class TestAnonymizerOrder:
    """Testy kolejności zastąpień – fix v2.2."""

    def test_hostname_replaced_before_username(self):
        """Hostname zastępowany przed username (hostname może zawierać username)."""
        hostname = socket.gethostname()
        data = f"connected to {hostname}"
        anon, report = anonymize(data)
        assert hostname not in anon
        assert "[HOSTNAME]" in anon

    def test_home_path_replaced_before_username_word(self):
        """Ścieżka /home/user zastąpiona zanim username jako słowo."""
        username = getpass.getuser()
        data = f"/home/{username}/file.txt and user {username} is active"
        anon, _ = anonymize(data)
        assert username not in anon

    def test_report_categories_present(self):
        """Raport powinien zawierać kategorie dla każdego zastąpienia."""
        username = getpass.getuser()
        hostname = socket.gethostname()
        data = (
            f"host={hostname} user={username} "
            f"ip=192.168.1.1 mac=aa:bb:cc:dd:ee:ff "
            f"uuid=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        )
        _, report = anonymize(data)
        assert isinstance(report, AnonymizationReport)
        assert report.original_length > 0
        assert report.anonymized_length > 0
        assert len(report.replacements) >= 3

    def test_report_summary_format(self):
        """Raport summary powinien zawierać czytelne linie."""
        data = "ip=192.168.1.1"
        _, report = anonymize(data)
        summary = report.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestAnonymizerEdgeCases:
    """Testy przypadków brzegowych."""

    def test_empty_string(self):
        anon, report = anonymize("")
        assert anon == ""
        assert len(report.replacements) == 0

    def test_none_converted_to_string(self):
        anon, _ = anonymize(None)
        assert isinstance(anon, str)

    def test_dict_converted_to_string(self):
        anon, _ = anonymize({"key": "value", "ip": "192.168.1.1"})
        assert isinstance(anon, str)
        assert "192.168.1.1" not in anon

    def test_very_long_path(self):
        """Bardzo długa ścieżka nie powinna powodować błędów."""
        data = "/home/user/" + "subdir/" * 20 + "file.txt"
        anon, _ = anonymize(data)
        assert isinstance(anon, str)

    def test_path_with_special_chars(self):
        """Ścieżka ze spacją i specjalnymi znakami."""
        data = "file at /home/jan/My Documents/report.pdf"
        anon, _ = anonymize(data)
        assert isinstance(anon, str)

    def test_api_token_sk_or_masked(self):
        """Token OpenRouter sk-or-v1-... musi być zamaskowany."""
        data = "using key sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890"
        anon, report = anonymize(data)
        assert "sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890" not in anon
        assert report.replacements.get("Tokeny API", 0) > 0

    def test_api_token_gemini_masked(self):
        """Token Gemini AIzaSy... musi być zamaskowany."""
        data = "GEMINI_API_KEY=AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        anon, report = anonymize(data)
        assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in anon

    def test_uuid_hardware_masked(self):
        """UUID hardware identifiers muszą być zamaskowane."""
        data = "disk UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890 mounted at /mnt"
        anon, report = anonymize(data)
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in anon
        assert report.replacements.get("UUID (serial/hardware)", 0) > 0

    def test_mac_address_masked(self):
        """Adresy MAC muszą być zamaskowane."""
        data = "interface eth0 hwaddr aa:bb:cc:dd:ee:ff"
        anon, report = anonymize(data)
        assert "aa:bb:cc:dd:ee:ff" not in anon
        assert "XX:XX:XX:XX:XX:XX" in anon

    def test_ipv4_partial_octets_preserved(self):
        """Pierwsze dwa oktety IPv4 powinny być zachowane."""
        data = "connected to 192.168.1.100"
        anon, _ = anonymize(data)
        assert "192.168" in anon
        assert "192.168.1.100" not in anon

    def test_password_in_env_masked(self):
        """Hasła w zmiennych środowiskowych muszą być zamaskowane."""
        data = "DB_PASSWORD=supersecret123 API_KEY=mytoken456"
        anon, report = anonymize(data)
        assert "supersecret123" not in anon
        assert report.replacements.get("Hasła/sekrety", 0) > 0
