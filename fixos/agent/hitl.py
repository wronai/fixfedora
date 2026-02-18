"""
Tryb Human-in-the-Loop (HITL) – użytkownik zatwierdza każdą akcję.
LLM proponuje, człowiek decyduje, skrypt wykonuje.

UX:
- Każda komenda widoczna przed wykonaniem (z komentarzem co robi)
- stdout/stderr w bloku markdown po wykonaniu
- Zawsze lista dostępnych akcji z numerami
- Opcja [D] opisania własnego problemu przez użytkownika
- Cross-platform: Linux, macOS, Windows
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from ..providers.llm import LLMClient, LLMError
from ..utils.anonymizer import anonymize, display_anonymized_preview
from ..utils.web_search import search_all, format_results_for_llm
from ..utils.terminal import _C, render_md as _render_md, colorize as _colorize_inline
from ..config import FixOsConfig
from ..platform_utils import (
    is_dangerous, elevate_cmd, run_command,
    setup_signal_timeout, cancel_signal_timeout,
    get_os_info, get_package_manager,
)


SYSTEM_PROMPT = """You are an expert Linux/Windows/macOS system diagnostics assistant.

You receive anonymized diagnostic data OR a user-described problem. Your tasks:

1. DIAGNOSE – identify ALL problems (🔴 critical → 🟡 important → 🟢 minor)
2. SOLUTIONS – for each problem provide a CONCRETE command with a brief explanation
3. FORMAT – always use this exact format:

━━━ DIAGNOZA ━━━
🔴 Problem 1: [description]
   **Komenda:** `command to run`
   **Co robi:** one-sentence explanation

🟡 Problem 2: [description]
   **Komenda:** `command`
   **Co robi:** explanation

Always end with:
━━━ DOSTĘPNE AKCJE ━━━
[1] Fix problem 1 – `command`
[2] Fix problem 2 – `command`
[A] Fix all automatically
[S] Skip all
[D] Describe a new problem
[Q] End session

IMPORTANT: Adapt commands to the detected OS (Linux/Windows/macOS).
"""


class SessionTimeout(Exception):
    pass


def _timeout(signum, frame):
    raise SessionTimeout()


@dataclass
class CmdResult:
    cmd: str
    comment: str
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    skipped: bool = False
    timestamp: float = field(default_factory=time.time)


def _sep(char: str = "─", width: int = 65):
    print(char * width)


def _print_cmd_preview(cmd: str, comment: str = ""):
    """Shows command in a clear block before execution."""
    print()
    _sep("┄")
    print("  🔧 KOMENDA DO WYKONANIA")
    print()
    print("  ```bash")
    print(f"  {cmd}")
    print("  ```")
    if comment:
        print()
        print(f"  📝 Co robi: {comment}")
    _sep("┄")


def _print_cmd_result(result: CmdResult):
    """Shows command result with colorized markdown."""
    if result.skipped:
        print(f"  {_C.DIM}⏭️  Pominięto: {_C.CYAN}`{result.cmd}`{_C.RESET}")
        return

    if result.ok:
        status = f"{_C.GREEN}{_C.BOLD}✅{_C.RESET}"
    else:
        status = f"{_C.RED}{_C.BOLD}❌ (kod {result.returncode}){_C.RESET}"

    print()
    print(f"  {status} {_C.CYAN}`{result.cmd}`{_C.RESET}")
    print()

    if result.stdout.strip():
        lines = result.stdout.strip().splitlines()
        print(f"{_C.BG_DARK}{_C.DIM}  ┌─ stdout {'─' * 47}┐{_C.RESET}")
        for line in lines[:40]:
            print(f"{_C.BG_DARK}  │ {_C.GREEN}{line}{_C.RESET}")
        if len(lines) > 40:
            print(f"{_C.BG_DARK}  │ {_C.DIM}... ({len(lines) - 40} więcej linii){_C.RESET}")
        print(f"{_C.BG_DARK}{_C.DIM}  └{'─' * 54}┘{_C.RESET}")
    elif not result.ok and not result.stderr.strip():
        print(f"  {_C.DIM}(brak stdout){_C.RESET}")

    if result.stderr.strip() and not result.ok:
        print()
        print(f"  {_C.YELLOW}{_C.BOLD}⚠️  Stderr:{_C.RESET}")
        print(f"{_C.BG_DARK}{_C.DIM}  ┌─ stderr {'─' * 47}┐{_C.RESET}")
        for line in result.stderr.strip().splitlines()[:15]:
            print(f"{_C.BG_DARK}  │ {_C.RED}{line}{_C.RESET}")
        print(f"{_C.BG_DARK}{_C.DIM}  └{'─' * 54}┘{_C.RESET}")
    print()


def _run_cmd(cmd: str, comment: str = "") -> CmdResult:
    """Runs a command with full transparency and markdown output."""
    cmd = elevate_cmd(cmd)
    danger = is_dangerous(cmd)
    if danger:
        print(f"\n  ⛔ ZABLOKOWANO: {danger}")
        print(f"  Komenda: `{cmd}`")
        return CmdResult(cmd=cmd, comment=comment, ok=False,
                         stdout="", stderr=f"Zablokowano: {danger}", returncode=-99)
    _print_cmd_preview(cmd, comment)
    print("  Wykonać? [Y/n]: ", end="", flush=True)
    ans = input().strip().lower()
    if ans in ("n", "no", "nie"):
        return CmdResult(cmd=cmd, comment=comment, ok=False,
                         stdout="", stderr="Pominięto.", returncode=-1, skipped=True)
    print("  ⏳ Wykonuję...", end="", flush=True)
    ok, stdout, stderr, rc = run_command(cmd, timeout=120)
    print("\r" + " " * 30 + "\r", end="")
    result = CmdResult(cmd=cmd, comment=comment, ok=ok,
                       stdout=stdout, stderr=stderr, returncode=rc)
    _print_cmd_result(result)
    return result


def _extract_fixes(reply: str) -> list[tuple[str, str]]:
    """Extracts (command, comment) pairs from LLM reply."""
    fixes: list[tuple[str, str]] = []
    for m in re.finditer(
        r"\*\*Komenda:\*\*\s*`([^`]+)`(?:[^\n]*?\*\*Co robi:\*\*\s*(.+?))?(?=\n|$)",
        reply, re.IGNORECASE,
    ):
        cmd = m.group(1).strip()
        if cmd:
            fixes.append((cmd, (m.group(2) or "").strip()))
    if not fixes:
        for m in re.finditer(r"→\s*Fix:\s*`([^`]+)`", reply, re.IGNORECASE):
            fixes.append((m.group(1).strip(), ""))
    if not fixes:
        for m in re.finditer(r"\[(\d+)\][^`\n]+`([^`]+)`", reply):
            fixes.append((m.group(2).strip(), f"Fix #{m.group(1)}"))
    if not fixes:
        for m in re.finditer(r"EXEC:\s*`([^`]+)`", reply, re.IGNORECASE):
            fixes.append((m.group(1).strip(), ""))
    return fixes


def _print_action_menu(
    fixes: list[tuple[str, str]],
    rem_time: str,
    tokens: int,
):
    """Prints the interactive numbered action menu."""
    print()
    _sep("═")
    print(f"  📋 DOSTĘPNE AKCJE  |  ⏰ {rem_time}  |  ~{tokens} tokenów")
    _sep("─")
    if fixes:
        for i, (cmd, comment) in enumerate(fixes, 1):
            label = comment if comment else (cmd[:55] + "..." if len(cmd) > 55 else cmd)
            print(f"  [{i}] {label}")
            print(f"       ```bash")
            print(f"       {cmd}")
            print(f"       ```")
        print()
        print(f"  [A]  Wykonaj wszystkie ({len(fixes)} komend)")
        print(f"  [S]  Pomiń wszystkie")
    else:
        print("  (brak zaproponowanych komend)")
    print()
    print(f"  [D]           Opisz własny problem / co chcesz zmienić")
    print(f"  [!cmd]        Wykonaj własną komendę")
    print(f"  [search <q>]  Szukaj zewnętrznie")
    print(f"  [?]           Zapytaj o więcej szczegółów")
    print(f"  [Q]           Zakończ sesję")
    _sep("═")


def _ask_user_problem() -> str:
    """Interactively asks the user to describe their problem."""
    print()
    _sep("═")
    print("  💬 OPISZ SWÓJ PROBLEM")
    _sep("─")
    print("  Napisz co chcesz naprawić, zmienić lub co nie działa.")
    print("  Możesz pisać po polsku lub angielsku.")
    print()
    print("  Przykłady:")
    print("    - 'brak dźwięku po aktualizacji'")
    print("    - 'chcę przyspieszyć uruchamianie systemu'")
    print("    - 'wifi nie działa po uśpieniu'")
    print("    - 'chcę zainstalować sterowniki NVIDIA'")
    print("    - 'dysk jest prawie pełny, co usunąć'")
    print("    - 'jak skonfigurować firewall'")
    _sep("─")
    print()
    try:
        return input("  Twój problem: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def run_hitl_session(
    diagnostics: dict,
    config: FixOsConfig,
    show_data: bool = True,
):
    """Runs interactive HITL session with full transparency."""
    llm = LLMClient(config)
    os_info = get_os_info()
    pkg_manager = get_package_manager() or "unknown"

    anon_str, report = anonymize(str(diagnostics))
    if show_data:
        display_anonymized_preview(anon_str, report)
        print("\n  Czy wysłać te dane do LLM? [Y/n]: ", end="")
        ans = input().strip().lower()
        if ans in ("n", "no", "nie"):
            print("  Anulowano.")
            return

    setup_signal_timeout(config.session_timeout, _timeout)
    start_ts = time.time()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"OS: {os_info['system']} {os_info['release']} | "
                f"Package manager: {pkg_manager}\n\n"
                f"Anonymized diagnostic data:\n```\n{anon_str}\n```\n\n"
                f"Perform full analysis and list all detected problems."
            ),
        },
    ]

    executed: list[CmdResult] = []
    web_search_count = 0
    MAX_WEB_SEARCHES = 3
    last_fixes: list[tuple[str, str]] = []

    def remaining() -> int:
        return config.session_timeout - int(time.time() - start_ts)

    def fmt_time(s: int) -> str:
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    print()
    _sep("═")
    print(f"  👤 HUMAN-IN-THE-LOOP  |  Model: {config.model}")
    print(f"  🖥️  OS: {os_info['system']} {os_info['release']}  |  PM: {pkg_manager}")
    print(f"  ⏰ Sesja: max {fmt_time(config.session_timeout)}")
    _sep("═")

    try:
        while True:
            rem = remaining()
            if rem <= 0:
                raise SessionTimeout()

            print(f"\n  🧠 Analizuję...", end="", flush=True)
            try:
                reply = llm.chat(messages, max_tokens=2500, temperature=0.2)
                messages.append({"role": "assistant", "content": reply})
            except LLMError as e:
                print(f"\n  ❌ Błąd LLM: {e}")
                if config.enable_web_search and web_search_count < MAX_WEB_SEARCHES:
                    web_search_count += 1
                    print("  🔎 Szukam zewnętrznie...")
                    results = search_all("linux system diagnostics repair", config.serpapi_key)
                    if results:
                        print(format_results_for_llm(results))
                break
            print("\r" + " " * 30 + "\r", end="")

            print()
            _sep("─")
            _render_md(reply)
            _sep("─")

            last_fixes = _extract_fixes(reply)

            low_conf = any(p in reply.lower() for p in [
                "nie wiem", "nie jestem pewien", "i don't know",
                "not sure", "cannot determine",
            ])
            if low_conf and config.enable_web_search and web_search_count < MAX_WEB_SEARCHES:
                print("\n  💡 LLM niepewny – szukać zewnętrznie? [y/N]: ", end="")
                if input().strip().lower() in ("y", "yes", "tak"):
                    web_search_count += 1
                    topic = _extract_search_topic(reply)
                    results = search_all(topic, config.serpapi_key)
                    if results:
                        web_ctx = format_results_for_llm(results)
                        print(web_ctx)
                        messages.append({"role": "user",
                                         "content": f"External sources:\n{web_ctx}\nUpdate analysis."})
                        continue

            _print_action_menu(last_fixes, fmt_time(rem), llm.total_tokens)

            try:
                user_in = input(f"\n  fixos [{fmt_time(rem)}] ❯ ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Sesja przerwana.")
                break

            if not user_in:
                continue

            lo = user_in.lower()

            # [Q] Quit
            if lo in ("q", "quit", "exit", "koniec"):
                print("\n  ✅ Sesja zakończona.")
                break

            # [D] Describe own problem
            if lo == "d":
                problem = _ask_user_problem()
                if problem:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"User describes a new problem:\n"
                            f"{problem}\n\n"
                            f"Analyze this problem and provide numbered list of commands to fix it."
                        ),
                    })
                continue

            # [S] Skip all
            if lo in ("s", "skip", "pomiń", "pomin"):
                messages.append({"role": "user",
                                  "content": "Skip these fixes. What else can we check?"})
                continue

            # [A] Execute all
            if lo in ("a", "all", "wszystkie"):
                if not last_fixes:
                    print("  Brak komend do wykonania.")
                    continue
                print(f"\n  ▶️  Wykonuję wszystkie {len(last_fixes)} komend...\n")
                summary_lines = []
                for cmd, comment in last_fixes:
                    result = _run_cmd(cmd, comment)
                    executed.append(result)
                    anon_out, _ = anonymize(result.stdout + result.stderr)
                    status = "✅ sukces" if result.ok else f"❌ błąd (kod {result.returncode})"
                    summary_lines.append(f"- `{cmd}`: {status}")
                messages.append({
                    "role": "user",
                    "content": (
                        f"Executed all commands:\n" +
                        "\n".join(summary_lines) +
                        "\n\nEvaluate results and suggest next steps."
                    ),
                })
                continue

            # [N] Execute specific fix by number
            if user_in.isdigit():
                idx = int(user_in) - 1
                if 0 <= idx < len(last_fixes):
                    cmd, comment = last_fixes[idx]
                    result = _run_cmd(cmd, comment)
                    executed.append(result)
                    anon_out, _ = anonymize(result.stdout)
                    anon_err, _ = anonymize(result.stderr)
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Executed: `{cmd}`\n"
                            f"Success: {result.ok}\n"
                            f"Stdout:\n```\n{anon_out[:800]}\n```\n"
                            f"Stderr:\n```\n{anon_err[:300]}\n```\n"
                            f"What next?"
                        ),
                    })
                else:
                    print(f"  Brak opcji [{user_in}]. Dostępne: 1–{len(last_fixes)}")
                continue

            # [!cmd] Direct command execution
            if user_in.startswith("!"):
                cmd = user_in[1:].strip()
                result = _run_cmd(cmd, "Komenda użytkownika")
                executed.append(result)
                anon_out, _ = anonymize(result.stdout + "\n" + result.stderr)
                messages.append({
                    "role": "user",
                    "content": f"User ran: `{cmd}`\nResult: {anon_out[:600]}\nWhat next?"
                })
                continue

            # [search <q>] Web search
            if lo.startswith("search "):
                query = user_in[7:].strip()
                results = search_all(query, config.serpapi_key)
                if results:
                    web_ctx = format_results_for_llm(results)
                    print(web_ctx)
                    messages.append({
                        "role": "user",
                        "content": f"Search results for '{query}':\n{web_ctx}\nWhat do you think?"
                    })
                else:
                    print("  Brak wyników.")
                continue

            # Free text → send to LLM
            messages.append({"role": "user", "content": user_in})

    except SessionTimeout:
        print(f"\n\n  ⏰ Sesja wygasła (limit: {fmt_time(config.session_timeout)}).")
    finally:
        cancel_signal_timeout()

    elapsed = int(time.time() - start_ts)
    ok_count = sum(1 for r in executed if r.ok)
    print(f"\n  📊 Sesja: {len(messages)-2} tur | {fmt_time(elapsed)} | "
          f"~{llm.total_tokens} tokenów | {ok_count}/{len(executed)} komend OK")


def _extract_search_topic(llm_reply: str) -> str:
    """Extracts search keywords from LLM reply."""
    tech_terms = re.findall(
        r"\b(sof-firmware|pipewire|alsa|thumbnails?|nautilus|"
        r"dnf|apt|systemctl|journalctl|codec|driver|nvidia|amd|"
        r"snd_hda|intel_sst|avs|wireplumber|pulseaudio|bluetooth|wifi)\b",
        llm_reply, re.IGNORECASE
    )
    if tech_terms:
        return " ".join(dict.fromkeys(tech_terms[:4]))
    first_sentence = llm_reply.split(".")[0][:80]
    return first_sentence or "linux system diagnostics"
