"""
Tryb Human-in-the-Loop (HITL) – użytkownik zatwierdza każdą akcję.
LLM proponuje, człowiek decyduje, skrypt wykonuje.
"""

from __future__ import annotations

import signal
import subprocess
import time
from typing import Optional

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style
    _HAS_PROMPT = True
except ImportError:
    _HAS_PROMPT = False

from ..providers.llm import LLMClient, LLMError
from ..utils.anonymizer import anonymize, display_anonymized_preview
from ..utils.web_search import search_all, format_results_for_llm
from ..config import FixFedoraConfig


SYSTEM_PROMPT = """Jesteś ekspertem diagnostyki Fedora Linux (specjalizacja: Lenovo Yoga, audio SOF/PipeWire, thumbnails).

Otrzymujesz anonimizowane dane diagnostyczne. Twoje zadania:

1. DIAGNOZA – zidentyfikuj WSZYSTKIE problemy w danych (sorted by severity: 🔴 krytyczne → 🟡 ważne → 🟢 drobne)
2. ROZWIĄZANIA – dla każdego problemu podaj KONKRETNĄ komendę Fedora (dnf/systemctl/etc)
3. POTWIERDZENIE – zawsze pytaj przed wykonaniem (tryb HITL)
4. WYJAŚNIENIE – krótko tłumacz co dana komenda robi i dlaczego

Format odpowiedzi diagnostycznej:
━━━ DIAGNOZA ━━━
🔴 Problem 1: [opis]
   → Fix: `komenda`
🟡 Problem 2: [opis]
   → Fix: `komenda`

Co robimy? (wpisz numer / 'all' / 'skip' / '!komenda' / 'search <zapytanie>' / 'q')

Jeśli pytasz o komendę do wykonania, użyj DOKŁADNIE formatu:
EXEC: `<komenda>`
"""


class SessionTimeout(Exception):
    pass


def _timeout(signum, frame):
    raise SessionTimeout()


def _run_cmd_safely(cmd: str) -> tuple[bool, str]:
    """Wykonuje komendę z potwierdzeniem, dodaje sudo gdy potrzeba."""
    needs_sudo = any(
        cmd.strip().startswith(p)
        for p in ["dnf", "rpm", "systemctl", "firewall-cmd", "setenforce",
                  "chmod 0", "chown", "rm -rf", "mkfs", "fdisk", "parted"]
    )
    if needs_sudo and not cmd.strip().startswith("sudo"):
        cmd = "sudo " + cmd.strip()

    print(f"\n  ┌─ KOMENDA DO WYKONANIA ─────────────────────")
    print(f"  │  {cmd}")
    print(f"  └────────────────────────────────────────────")
    confirm = input("  Potwierdzam (Y/n): ").strip().lower()
    if confirm not in ("y", "yes", ""):
        return False, "Anulowano."

    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        out = proc.stdout.strip() or proc.stderr.strip() or "(brak outputu)"
        ok = proc.returncode == 0
        icon = "✅" if ok else f"❌ (kod {proc.returncode})"
        print(f"  {icon}")
        if out:
            preview = out[:400] + ("..." if len(out) > 400 else "")
            print(f"  Output:\n{preview}")
        return ok, out
    except subprocess.TimeoutExpired:
        return False, "[TIMEOUT 120s]"
    except Exception as e:
        return False, f"[WYJĄTEK: {e}]"


def run_hitl_session(
    diagnostics: dict,
    config: FixFedoraConfig,
    show_data: bool = True,
):
    """
    Uruchamia interaktywną sesję HITL.
    """
    llm = LLMClient(config)

    # Anonimizuj i opcjonalnie pokaż dane
    anon_str, report = anonymize(str(diagnostics))
    if show_data:
        display_anonymized_preview(anon_str, report)
        print("\n  Czy wysłać te dane do LLM? [Y/n]: ", end="")
        ans = input().strip().lower()
        if ans in ("n", "no", "nie"):
            print("  Anulowano.")
            return

    # Konfiguracja timeout
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(config.session_timeout)
    start_ts = time.time()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Oto dane diagnostyczne systemu Fedora (zanonimizowane):\n\n"
                f"```\n{anon_str}\n```\n\n"
                f"Przeprowadź pełną analizę i wskaż wszystkie wykryte problemy."
            ),
        },
    ]

    # Styl prompt
    style = Style.from_dict({"prompt": "#00cc00 bold", "info": "#888888"}) if _HAS_PROMPT else None
    session = PromptSession(style=style) if _HAS_PROMPT else None

    def remaining() -> int:
        return config.session_timeout - int(time.time() - start_ts)

    def fmt_time(s: int) -> str:
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    print("\n" + "═" * 65)
    print(f"  👤 Tryb: HUMAN-IN-THE-LOOP  |  Model: {config.model}")
    print(f"  ⏰ Sesja: max {fmt_time(config.session_timeout)}")
    print("  Komendy: [numer] fix | 'all' | 'skip' | '!cmd' | 'search <q>' | 'q'")
    print("═" * 65 + "\n")

    web_search_count = 0
    MAX_WEB_SEARCHES = 3

    try:
        while True:
            rem = remaining()
            if rem <= 0:
                raise SessionTimeout()

            # Wywołanie LLM
            print("  🧠 LLM analizuje...", end="", flush=True)
            try:
                reply = llm.chat(messages, max_tokens=2500, temperature=0.25)
                messages.append({"role": "assistant", "content": reply})
            except LLMError as e:
                print(f"\n  ❌ {e}")
                # Fallback: web search
                if config.enable_web_search and web_search_count < MAX_WEB_SEARCHES:
                    web_search_count += 1
                    print("  🔎 LLM niedostępny – szukam w zewnętrznych źródłach...")
                    results = search_all("fedora system diagnostics", config.serpapi_key)
                    if results:
                        print(format_results_for_llm(results))
                break

            print("\r" + " " * 30 + "\r", end="")

            # Sprawdź czy LLM sugeruje "nie wiem" → web search
            low_conf_phrases = [
                "nie wiem", "nie jestem pewien", "brak informacji",
                "nie mam wystarczających", "skonsultuj się",
                "I don't know", "not sure", "cannot determine"
            ]
            llm_uncertain = any(p.lower() in reply.lower() for p in low_conf_phrases)

            print(f"\n{'─' * 65}")
            print(reply)
            print(f"{'─' * 65}")
            print(f"  ⏰ {fmt_time(rem)}  |  Tokeny: ~{llm.total_tokens}")

            # Jeśli LLM niepewny i web search włączony
            if llm_uncertain and config.enable_web_search and web_search_count < MAX_WEB_SEARCHES:
                print("\n  💡 LLM wskazał niepewność – szukam zewnętrznie? [y/N]: ", end="")
                if input().strip().lower() in ("y", "yes", "tak"):
                    web_search_count += 1
                    # Wyciągnij temat z ostatniej wiadomości
                    topic = _extract_search_topic(reply)
                    results = search_all(topic, config.serpapi_key)
                    if results:
                        web_context = format_results_for_llm(results)
                        print(web_context)
                        messages.append({
                            "role": "user",
                            "content": (
                                f"Znalazłem następujące zewnętrzne źródła – "
                                f"użyj ich do uzupełnienia analizy:\n\n{web_context}"
                            ),
                        })
                        continue

            # Input użytkownika
            try:
                if session:
                    user_in = session.prompt(
                        HTML(f"\n<prompt>fixfedora</prompt> <info>[{fmt_time(rem)}]</info> ❯ ")
                    ).strip()
                else:
                    user_in = input(f"\nfixfedora [{fmt_time(rem)}] ❯ ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Sesja przerwana.")
                break

            if not user_in:
                continue

            # Komendy specjalne
            if user_in.lower() in ("q", "quit", "exit", "koniec"):
                print("\n  ✅ Sesja zakończona.")
                break

            if user_in.startswith("!"):
                # Bezpośrednie wykonanie komendy
                cmd = user_in[1:].strip()
                ok, out = _run_cmd_safely(cmd)
                messages.append({
                    "role": "user",
                    "content": f"Wykonałem: `{cmd}`\nWynik: {out}\nCo teraz?"
                })
                continue

            if user_in.lower().startswith("search "):
                # Manualne wyszukiwanie zewnętrzne
                query = user_in[7:].strip()
                results = search_all(query, config.serpapi_key)
                if results:
                    web_context = format_results_for_llm(results)
                    print(web_context)
                    messages.append({
                        "role": "user",
                        "content": f"Wyniki wyszukiwania dla '{query}':\n{web_context}\nCo sądzisz?"
                    })
                else:
                    print("  Brak wyników.")
                continue

            # Sprawdź czy LLM zaproponował EXEC: `komenda`
            import re
            exec_match = re.search(r"EXEC:\s*`([^`]+)`", reply)
            if user_in.isdigit() and exec_match:
                cmd = exec_match.group(1)
                ok, out = _run_cmd_safely(cmd)
                messages.append({
                    "role": "user",
                    "content": f"Wykonałem `{cmd}`. Wynik: {'sukces' if ok else 'błąd'}.\n{out}\nCo dalej?"
                })
                continue

            # Standardowy input do LLM
            messages.append({"role": "user", "content": user_in})

    except SessionTimeout:
        print(f"\n\n  ⏰ Sesja wygasła (limit: {fmt_time(config.session_timeout)}).")
    finally:
        signal.alarm(0)

    elapsed = int(time.time() - start_ts)
    print(f"\n  📊 Sesja: {len(messages)-2} tur | {fmt_time(elapsed)} | ~{llm.total_tokens} tokenów")


def _extract_search_topic(llm_reply: str) -> str:
    """Wyciąga słowa kluczowe do wyszukiwania z odpowiedzi LLM."""
    # Szukaj konkretnych terminów technicznych
    import re
    tech_terms = re.findall(
        r"\b(sof-firmware|pipewire|alsa|thumbnails?|nautilus|"
        r"dnf|rpm|systemctl|journalctl|lenovo|yoga|codec|driver|"
        r"snd_hda|intel_sst|avs|wireplumber|pulseaudio)\b",
        llm_reply, re.IGNORECASE
    )
    if tech_terms:
        return " ".join(dict.fromkeys(tech_terms[:4]))
    # Fallback: pierwsze zdanie
    first_sentence = llm_reply.split(".")[0][:80]
    return first_sentence or "fedora diagnostics"
