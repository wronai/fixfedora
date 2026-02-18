"""
Anonimizacja wrażliwych danych systemowych z podglądem dla użytkownika.
"""

from __future__ import annotations

import re
import socket
import getpass
import os
from dataclasses import dataclass, field


@dataclass
class AnonymizationReport:
    """Raport anonimizacji – co zostało zmaskowane."""
    original_length: int = 0
    anonymized_length: int = 0
    replacements: dict[str, int] = field(default_factory=dict)

    def add(self, category: str, count: int = 1):
        self.replacements[category] = self.replacements.get(category, 0) + count

    def summary(self) -> str:
        if not self.replacements:
            return "  Nie znaleziono wrażliwych danych."
        lines = []
        for cat, count in sorted(self.replacements.items()):
            lines.append(f"  ✓ {cat}: {count} wystąpień")
        return "\n".join(lines)


def _get_sensitive() -> dict:
    result = {}
    try:
        result["hostname"] = socket.gethostname()
    except Exception:
        result["hostname"] = None
    try:
        result["username"] = getpass.getuser()
    except Exception:
        result["username"] = None
    try:
        result["home"] = os.path.expanduser("~")
    except Exception:
        result["home"] = None
    return result


def anonymize(data_str: str) -> tuple[str, AnonymizationReport]:
    """
    Anonimizuje wrażliwe dane.

    Returns:
        Tuple (zanonimizowany_string, raport)
    """
    if not isinstance(data_str, str):
        data_str = str(data_str)

    report = AnonymizationReport(original_length=len(data_str))
    sensitive = _get_sensitive()

    # 1. Hostname
    if sensitive.get("hostname"):
        count = data_str.count(sensitive["hostname"])
        if count:
            data_str = data_str.replace(sensitive["hostname"], "[HOSTNAME]")
            report.add("Hostname", count)

    # 2. Username (konkretna nazwa)
    if sensitive.get("username"):
        pattern = rf"\b{re.escape(sensitive['username'])}\b"
        matches = len(re.findall(pattern, data_str))
        if matches:
            data_str = re.sub(pattern, "[USER]", data_str)
            report.add("Username", matches)

    # 3. Katalog domowy
    if sensitive.get("home"):
        count = data_str.count(sensitive["home"])
        if count:
            data_str = data_str.replace(sensitive["home"], "/home/[USER]")
            report.add("Ścieżka domowa", count)

    # 4. Adresy IPv4 (zachowaj 2 pierwsze oktety)
    ipv4_pattern = r"\b(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}\b"
    matches = len(re.findall(ipv4_pattern, data_str))
    if matches:
        data_str = re.sub(ipv4_pattern, r"\1.XXX.XXX", data_str)
        report.add("Adresy IPv4", matches)

    # 5. Adresy MAC
    mac_pattern = r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"
    matches = len(re.findall(mac_pattern, data_str))
    if matches:
        data_str = re.sub(mac_pattern, "XX:XX:XX:XX:XX:XX", data_str)
        report.add("Adresy MAC", matches)

    # 6. Ścieżki /home/<user>
    home_pattern = r"/home/[^\s/\"':]+"
    matches = len(re.findall(home_pattern, data_str))
    if matches:
        data_str = re.sub(home_pattern, "/home/[USER]", data_str)
        report.add("Ścieżki /home", matches)

    # 7. Tokeny API (sk-, xai-, AIzaSy-, Bearer)
    token_pattern = r"(?<![A-Za-z0-9])(?:sk-|xai-|AIzaSy[A-Za-z0-9_-]+|Bearer\s+)[A-Za-z0-9\-_.]{15,}"
    matches = len(re.findall(token_pattern, data_str))
    if matches:
        data_str = re.sub(token_pattern, "[API_TOKEN_REDACTED]", data_str)
        report.add("Tokeny API", matches)

    # 8. Hasła/sekrety w zmiennych
    secret_pattern = r"(?i)(password|passwd|secret|token|api_key|apikey|auth)\s*[=:]\s*\S+"
    matches = len(re.findall(secret_pattern, data_str))
    if matches:
        data_str = re.sub(secret_pattern, r"\1=[REDACTED]", data_str)
        report.add("Hasła/sekrety", matches)

    # 9. UUIDs (mogą identyfikować sprzęt)
    uuid_pattern = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    matches = len(re.findall(uuid_pattern, data_str))
    if matches:
        data_str = re.sub(uuid_pattern, "[UUID-REDACTED]", data_str)
        report.add("UUID (serial/hardware)", matches)

    # 10. Serial numbers (typowy format np. PF1234567)
    serial_pattern = r"\b(?:S/N|Serial|SN)[\s:]+[A-Z0-9]{6,20}\b"
    matches = len(re.findall(serial_pattern, data_str, re.IGNORECASE))
    if matches:
        data_str = re.sub(serial_pattern, "Serial: [SERIAL-REDACTED]", data_str, flags=re.IGNORECASE)
        report.add("Numery seryjne", matches)

    report.anonymized_length = len(data_str)
    return data_str, report


def display_anonymized_preview(data_str: str, report: AnonymizationReport, max_lines: int = 60):
    """
    Wyświetla użytkownikowi zanonimizowane dane przed wysłaniem do LLM.
    """
    print("\n" + "═" * 65)
    print("  📋 DANE DIAGNOSTYCZNE (zanonimizowane) – wysyłane do LLM")
    print("═" * 65)

    lines = data_str.splitlines()
    if len(lines) > max_lines:
        shown = lines[:max_lines // 2] + ["  ... [skrócono] ..."] + lines[-(max_lines // 2):]
    else:
        shown = lines

    for line in shown:
        print(f"  {line}")

    print("\n" + "─" * 65)
    print("  🔒 Anonimizacja – co zostało ukryte:")
    print(report.summary())
    print(f"  Rozmiar: {report.original_length} → {report.anonymized_length} znaków")
    print("─" * 65)
