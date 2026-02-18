"""
Anonimizacja wrażliwych danych systemowych z podglądem dla użytkownika.
"""

from __future__ import annotations

import re
import socket
import getpass
import os
from dataclasses import dataclass, field
from .terminal import _C


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

    # 2. Katalog domowy (pełna ścieżka – PRZED zastąpieniem username)
    if sensitive.get("home"):
        count = data_str.count(sensitive["home"])
        if count:
            data_str = data_str.replace(sensitive["home"], "/home/[USER]")
            report.add("Ścieżka domowa", count)

    # 3. Ścieżki /home/<user>/... – dowolna głębokość (po literalnym zastąpieniu)
    home_pattern = r"/home/(?!\[USER\])[^\s\"'\\]+"
    matches = len(re.findall(home_pattern, data_str))
    if matches:
        data_str = re.sub(home_pattern, "/home/[USER]/...", data_str)
        report.add("Ścieżki /home", matches)

    # 4. Username (konkretna nazwa) – po zastąpieniu ścieżek
    if sensitive.get("username"):
        pattern = rf"\b{re.escape(sensitive['username'])}\b"
        matches = len(re.findall(pattern, data_str))
        if matches:
            data_str = re.sub(pattern, "[USER]", data_str)
            report.add("Username", matches)

    # 5. Adresy IPv4 (zachowaj 2 pierwsze oktety)
    ipv4_pattern = r"\b(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}\b"
    matches = len(re.findall(ipv4_pattern, data_str))
    if matches:
        data_str = re.sub(ipv4_pattern, r"\1.XXX.XXX", data_str)
        report.add("Adresy IPv4", matches)

    # 6. Adresy MAC
    mac_pattern = r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"
    matches = len(re.findall(mac_pattern, data_str))
    if matches:
        data_str = re.sub(mac_pattern, "XX:XX:XX:XX:XX:XX", data_str)
        report.add("Adresy MAC", matches)

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


def display_anonymized_preview(data_str: str, report: AnonymizationReport, max_lines: int = 80):
    """
    Wyświetla użytkownikowi zanonimizowane dane przed wysłaniem do LLM.
    Formatuje jako czytelny markdown z kolorami ANSI.
    """
    print(f"\n{_C.CYAN}{_C.BOLD}{'\u2550' * 65}{_C.RESET}")
    print(f"{_C.CYAN}{_C.BOLD}  📋 DANE DIAGNOSTYCZNE (zanonimizowane) – wysyłane do LLM{_C.RESET}")
    print(f"{_C.CYAN}{_C.BOLD}{'\u2550' * 65}{_C.RESET}")

    formatted = _format_diagnostics_markdown(data_str)

    lines = formatted.splitlines()
    if len(lines) > max_lines:
        half = max_lines // 2
        shown = (
            lines[:half]
            + [f"  {_C.DIM}...{_C.RESET}",
               f"  {_C.DIM}[skrócono – pełne dane wysyłane do LLM]{_C.RESET}",
               f"  {_C.DIM}...{_C.RESET}"]
            + lines[-half:]
        )
    else:
        shown = lines

    max_width = 100
    for line in shown:
        rendered = _colorize_md_line(line)
        # Strip ANSI for length check, truncate raw if needed
        raw_len = len(re.sub(r'\033\[[^m]*m', '', rendered))
        if raw_len > max_width:
            # Truncate the original line (before colorizing) then re-colorize
            rendered = _colorize_md_line(line[:max_width - 3] + "...")
        print(f"  {rendered}")

    print(f"\n{_C.DIM}{'\u2500' * 65}{_C.RESET}")
    print(f"{_C.BOLD}  🔒 Anonimizacja – co zostało ukryte:{_C.RESET}")
    for rep_line in report.summary().splitlines():
        print(f"{_C.GREEN}  {rep_line}{_C.RESET}")
    print(f"  {_C.DIM}Rozmiar: {report.original_length:,} → {report.anonymized_length:,} znaków{_C.RESET}")
    print(f"{_C.DIM}{'\u2500' * 65}{_C.RESET}")


def _colorize_md_line(line: str) -> str:
    """Apply ANSI colors to a single markdown-formatted diagnostic line."""
    stripped = line.lstrip()

    # ### Section heading
    if stripped.startswith("### "):
        title = stripped[4:]
        return f"{_C.CYAN}{_C.BOLD}{line[:len(line)-len(stripped)]}### {title}{_C.RESET}"

    # ``` fence lines
    if stripped.startswith("```"):
        return f"{_C.DIM}{line}{_C.RESET}"

    # - **key**: `value`  or  - **key**: value
    if stripped.startswith("- **"):
        # bold key
        line = re.sub(r'\*\*([^*]+)\*\*', lambda m: f"{_C.BOLD}{_C.WHITE}{m.group(1)}{_C.RESET}", line)
        # inline code value
        line = re.sub(r'`([^`]+)`', lambda m: f"{_C.CYAN}`{m.group(1)}`{_C.RESET}", line)
        return line

    # indented code content (inside ``` blocks rendered as plain lines)
    if line.startswith("  ") and stripped and not stripped.startswith("-") and not stripped.startswith("#"):
        return f"{_C.GREEN}{line}{_C.RESET}"

    # ... truncation markers
    if stripped.startswith("..."):
        return f"{_C.DIM}{line}{_C.RESET}"

    # inline code anywhere
    line = re.sub(r'`([^`]+)`', lambda m: f"{_C.CYAN}`{m.group(1)}`{_C.RESET}", line)
    return line


def _format_diagnostics_markdown(data_str: str) -> str:
    """Formatuje dane diagnostyczne jako czytelny markdown."""
    import ast
    
    # Próbuj sparsować jako dict
    try:
        # Usuń 'zanonimizowane' znaczniki jeśli są
        clean = data_str.replace('[HOSTNAME]', 'HOSTNAME').replace('[USER]', 'USER')
        data = ast.literal_eval(clean)
        if isinstance(data, dict):
            return _dict_to_markdown(data)
    except (SyntaxError, ValueError):
        pass
    
    # Fallback: formatuj jako kod
    return f"```\n{data_str}\n```"


def _dict_to_markdown(data: dict, indent: int = 0) -> str:
    """Rekurencyjnie konwertuje dict na markdown."""
    lines = []
    prefix = "  " * indent
    
    for key, value in data.items():
        if isinstance(value, dict):
            # Nagłówek sekcji
            section_title = _format_key_title(key)
            lines.append(f"\n{prefix}### {section_title}")
            lines.append(_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], dict):
                # Lista dictów - skróć
                lines.append(f"{prefix}- **{key}**: [{len(value)} elementów]")
            elif len(value) > 10:
                # Długa lista - pokaż pierwsze i ostatnie
                lines.append(f"{prefix}- **{key}**:")
                for item in value[:5]:
                    lines.append(f"{prefix}  - {item}")
                lines.append(f"{prefix}  ... ({len(value) - 10} więcej)")
                for item in value[-5:]:
                    lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}- **{key}**: {value}")
        elif isinstance(value, str) and len(value) > 200:
            # Długi string - skróć
            lines.append(f"{prefix}- **{key}**:")
            lines.append(f"{prefix}  ```")
            for line in value.split("\n")[:15]:
                lines.append(f"{prefix}  {line[:80]}")
            if value.count("\n") > 15:
                lines.append(f"{prefix}  ... ({value.count(chr(10)) - 15} więcej linii)")
            lines.append(f"{prefix}  ```")
        elif isinstance(value, str) and "\n" in value:
            # Wieloliniowy string jako blok kodu
            lines.append(f"{prefix}- **{key}**:")
            lines.append(f"{prefix}  ```")
            for line in value.split("\n")[:10]:
                lines.append(f"{prefix}  {line}")
            if value.count("\n") > 10:
                lines.append(f"{prefix}  ... ({value.count(chr(10)) - 10} więcej)")
            lines.append(f"{prefix}  ```")
        else:
            # Prosta wartość
            val_str = str(value)
            if len(val_str) > 60:
                val_str = val_str[:57] + "..."
            lines.append(f"{prefix}- **{key}**: `{val_str}`")
    
    return "\n".join(lines)


def _format_key_title(key: str) -> str:
    """Formatuje klucz dict jako czytelny tytuł."""
    titles = {
        "system": "🖥️ System",
        "audio": "🔊 Dźwięk",
        "thumbnails": "🖼️ Podglądy plików",
        "hardware": "🔧 Sprzęt",
        "disks": "💾 Dyski",
        "top_processes": "📊 Top procesy",
    }
    return titles.get(key, key.replace("_", " ").title())
