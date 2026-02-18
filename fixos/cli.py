"""
fixos CLI – wielopoziomowe komendy
  fixos scan          – diagnostyka systemu
  fixos fix           – diagnoza + sesja naprawcza
  fixos token         – zarządzanie tokenem API
  fixos config        – konfiguracja i ustawienia
  fixos providers     – lista dostępnych providerów LLM
  fixos test-llm      – test połączenia z LLM
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from .config import (
    FixOsConfig, get_providers_list, ENV_SEARCH_PATHS, PROVIDER_DEFAULTS,
    detect_provider_from_key, interactive_provider_setup,
)
from .diagnostics import get_full_diagnostics, DIAGNOSTIC_MODULES
from .utils.anonymizer import anonymize, display_anonymized_preview
from .agent.hitl import run_hitl_session
from .agent.autonomous import run_autonomous_session

BANNER = r"""
  ___  _       ___  ____
 / _(_)_  __  / _ \/ ___|
| |_| \ \/ / | | | \___ \
|  _| |>  <  | |_| |___) |
|_| |_/_/\_\  \___/|____/
  AI-powered OS Diagnostics  •  v2.0.0
"""

COMMON_OPTIONS = [
    click.option("--provider", "-p", default=None,
                 help="Provider LLM: gemini|openai|xai|openrouter|ollama"),
    click.option("--token", "-t", default=None, envvar="API_KEY",
                 help="Klucz API (override .env)"),
    click.option("--model", "-m", default=None,
                 help="Nazwa modelu LLM"),
    click.option("--no-banner", is_flag=True, default=False),
]


def add_common_options(fn):
    for opt in reversed(COMMON_OPTIONS):
        fn = opt(fn)
    return fn


# ══════════════════════════════════════════════════════════
#  GŁÓWNA GRUPA
# ══════════════════════════════════════════════════════════

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """
    fixos – AI-powered diagnostyka i naprawa Linux, Windows, macOS.

    \b
    Szybki start:
      fixos token set AIzaSy...   # zapisz token Gemini
      fixos fix                   # diagnostyka + naprawa
      fixos scan --audio          # tylko skan audio

    \b
    Więcej:
      fixos --help
      fixos fix --help
    """
    if ctx.invoked_subcommand is None:
        _print_welcome()


def _print_welcome():
    """Ekran powitalny fixos przy braku podkomendy."""
    click.echo(click.style(BANNER, fg="cyan"))

    cfg = FixOsConfig.load()
    has_key = bool(cfg.api_key)
    key_status = click.style("✅ skonfigurowany", fg="green") if has_key else click.style("❌ BRAK", fg="red")
    provider_info = f"{cfg.provider} ({cfg.model})"

    click.echo(click.style("═" * 60, fg="cyan"))
    click.echo(click.style("  📋 DOSTĘPNE KOMENDY", fg="cyan", bold=True))
    click.echo(click.style("═" * 60, fg="cyan"))
    click.echo()

    commands = [
        ("fixos fix",         "🔧", "Diagnostyka + sesja naprawcza z AI (HITL)"),
        ("fixos scan",        "🔍", "Diagnostyka systemu bez AI"),
        ("fixos orchestrate", "🎼", "Zaawansowana orkiestracja napraw (graf problemów)"),
        ("fixos llm",         "🤖", "Lista 12 providerów LLM + linki do kluczy API"),
        ("fixos token set",   "🔑", "Zapisz klucz API (auto-detekcja providera)"),
        ("fixos token show",  "👁️ ", "Pokaż aktualny token (zamaskowany)"),
        ("fixos config show", "⚙️ ", "Pokaż konfigurację"),
        ("fixos config init", "📄", "Utwórz plik .env z szablonu"),
        ("fixos providers",   "📡", "Lista providerów (skrócona)"),
        ("fixos test-llm",    "🧪", "Test połączenia z LLM"),
    ]

    for cmd, icon, desc in commands:
        cmd_styled = click.style(f"{cmd:<26}", fg="yellow")
        click.echo(f"  {icon}  {cmd_styled} {desc}")

    click.echo()
    click.echo(click.style("─" * 60, fg="cyan"))
    click.echo(click.style("  🔬 MODUŁY DIAGNOSTYKI", fg="cyan"))
    click.echo(click.style("─" * 60, fg="cyan"))
    modules_info = [
        ("system",     "🖥️ ", "CPU, RAM, dyski, usługi, aktualizacje"),
        ("audio",      "🔊", "ALSA, PipeWire, SOF firmware, mikrofon"),
        ("thumbnails", "🖼️ ", "Podglądy plików, cache, GStreamer"),
        ("hardware",   "🔧", "DMI, GPU, touchpad, kamera, bateria"),
        ("security",   "🔒", "Firewall, porty, SELinux, SSH, fail2ban"),
        ("resources",  "📊", "Dysk (co zajmuje), procesy, autostart"),
    ]
    for mod, icon, desc in modules_info:
        mod_styled = click.style(f"{mod:<12}", fg="white")
        click.echo(f"  {icon}  {mod_styled} {desc}")
    click.echo(click.style("  Użycie: fixos scan --modules security,resources", fg="cyan"))

    click.echo()
    click.echo(click.style("─" * 60, fg="cyan"))
    click.echo(click.style("  ⚙️  AKTUALNY STATUS", fg="cyan"))
    click.echo(click.style("─" * 60, fg="cyan"))
    click.echo(f"  Provider  : {provider_info}")
    click.echo(f"  API Key   : {key_status}")
    click.echo(f"  .env plik : {cfg.env_file_loaded or 'nie znaleziono'}")
    click.echo()

    if not has_key:
        click.echo(click.style("  💡 Szybki start:", fg="yellow", bold=True))
        click.echo(click.style("     fixos llm", fg="yellow") + "                    # wybierz provider i pobierz klucz")
        click.echo(click.style("     fixos token set <KLUCZ>", fg="yellow") + "      # zapisz klucz (auto-detekcja providera)")
        click.echo(click.style("     fixos fix", fg="yellow") + "                    # uruchom diagnostykę + naprawę")
        click.echo()
        click.echo(click.style("  ⚡ Lub po prostu:", fg="yellow"))
        click.echo(click.style("     fixos fix", fg="yellow") + "  # zapyta o provider interaktywnie")
    else:
        click.echo(click.style("  💡 Przykłady użycia:", fg="yellow", bold=True))
        click.echo(click.style("     fixos fix", fg="yellow") + "                           # pełna diagnostyka + naprawa")
        click.echo(click.style("     fixos fix --modules security,resources", fg="yellow") + " # bezpieczeństwo + zasoby")
        click.echo(click.style("     fixos scan --modules security", fg="yellow") + "        # tylko skan bezpieczeństwa")
        click.echo(click.style("     fixos orchestrate --dry-run", fg="yellow") + "          # podgląd napraw bez wykonania")
    click.echo()


# ══════════════════════════════════════════════════════════
#  fixos scan
# ══════════════════════════════════════════════════════════

@cli.command()
@click.option("--audio", "modules", flag_value="audio", help="Tylko diagnostyka dźwięku")
@click.option("--thumbnails", "modules", flag_value="thumbnails", help="Tylko podglądy plików")
@click.option("--hardware", "modules", flag_value="hardware", help="Tylko sprzęt")
@click.option("--system", "modules", flag_value="system", help="Tylko system")
@click.option("--all", "modules", flag_value="all", default=True, help="Wszystkie moduły (domyślnie)")
@click.option("--output", "-o", default=None, help="Zapisz raport do pliku JSON")
@click.option("--show-raw", is_flag=True, default=False, help="Pokaż surowe (zanonimizowane) dane")
@click.option("--no-banner", is_flag=True, default=False)
def scan(modules, output, show_raw, no_banner):
    """Przeprowadza diagnostykę systemu system bez uruchamiania LLM."""
    if not no_banner:
        click.echo(click.style(BANNER, fg="cyan"))

    selected = None if modules == "all" else [modules]

    click.echo(click.style("\n🔍 Zbieranie diagnostyki...", fg="yellow"))

    module_count = [0]
    def progress(name, desc):
        module_count[0] += 1
        click.echo(f"  [{module_count[0]}] {desc}...")

    data = get_full_diagnostics(selected, progress_callback=progress)

    anon_str, report = anonymize(str(data))
    click.echo(click.style("\n✅ Diagnostyka zakończona.", fg="green"))
    click.echo(f"\n🔒 Anonimizacja:\n{report.summary()}")

    if show_raw:
        display_anonymized_preview(anon_str, report)

    if output:
        try:
            Path(output).write_text(
                json.dumps({"anonymized": anon_str, "raw": data}, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            click.echo(click.style(f"\n💾 Zapisano: {output}", fg="green"))
        except Exception as e:
            click.echo(click.style(f"⚠️  Błąd zapisu: {e}", fg="yellow"))

    # Krótkie podsumowanie problemów
    _print_quick_issues(data)


def _print_quick_issues(data: dict):
    """Wyświetla szybki przegląd problemów z zebranych danych."""
    click.echo(click.style("\n📋 Szybki przegląd problemów:", fg="cyan"))
    issues = []

    # Sprawdź audio
    audio = data.get("audio", {})
    if "brak" in str(audio.get("alsa_cards", "")).lower() or not audio.get("alsa_cards","").strip() or audio.get("alsa_cards","") == "(brak outputu)":
        issues.append("🔴 Dźwięk: brak kart ALSA – prawdopodobnie brak sterownika SOF")
    if "failed" in str(audio.get("pipewire_status", "")).lower():
        issues.append("🔴 PipeWire: usługa failed")
    if "failed" in str(audio.get("wireplumber_status", "")).lower():
        issues.append("🟡 WirePlumber: usługa failed")

    # Sprawdź thumbnails
    thumb = data.get("thumbnails", {})
    thumb_count = str(thumb.get("thumbnail_cache_count", "0")).strip()
    if thumb_count == "0":
        issues.append("🟡 Thumbnails: pusty cache – brak podglądów")
    if "nie zainstalowany" in str(thumb.get("ffmpegthumbnailer", "")):
        issues.append("🟡 ffmpegthumbnailer: nie zainstalowany")
    if "nie znaleziony" in str(thumb.get("totem_thumb", "")):
        issues.append("🟡 totem-video-thumbnailer: nie znaleziony")

    # Sprawdź system
    sys_data = data.get("system", {})
    failed = str(sys_data.get("systemctl_failed", "")).strip()
    if failed and failed != "(brak outputu)" and "0 loaded" not in failed:
        issues.append(f"🔴 systemctl: usługi failed:\n    {failed[:200]}")

    if not issues:
        click.echo("  ✅ Brak oczywistych problemów w zebranych danych.")
    else:
        for issue in issues:
            click.echo(f"  {issue}")
        click.echo(f"\n  Uruchom 'fixos fix' aby naprawić z pomocą AI.")


# ══════════════════════════════════════════════════════════
#  fixos fix
# ══════════════════════════════════════════════════════════

@cli.command()
@add_common_options
@click.option("--mode", type=click.Choice(["hitl", "autonomous"]), default=None,
              help="Tryb agenta: hitl (domyślny) lub autonomous")
@click.option("--timeout", "-T", default=None, type=int,
              help="Timeout sesji w sekundach (domyślnie 3600)")
@click.option("--modules", "-M", default=None,
              help="Moduły diagnostyki: audio,thumbnails,hardware,system (domyślnie: all)")
@click.option("--no-show-data", is_flag=True, default=False,
              help="Nie pokazuj zanonimizowanych danych przed wysłaniem do LLM")
@click.option("--output", "-o", default=None, help="Zapisz raport diagnostyczny do JSON")
@click.option("--max-fixes", default=10, show_default=True,
              help="Maksymalna liczba automatycznych napraw (tryb autonomous)")
def fix(provider, token, model, no_banner, mode, timeout, modules, no_show_data, output, max_fixes):
    """
    Przeprowadza pełną diagnostykę i uruchamia sesję naprawczą z LLM.

    \b
    Tryby:
      hitl        – Human-in-the-Loop (pyta o każdą akcję) [domyślny]
      autonomous  – Agent sam wykonuje komendy (UWAGA: wymaga potwierdzenia)

    \b
    Przykłady:
      fixos fix                              # domyślnie hitl + Gemini z .env
      fixos fix --mode autonomous            # tryb autonomiczny
      fixos fix --modules audio,thumbnails   # tylko audio i thumbnails
      fixos fix --provider openai --token sk-...
    """
    if not no_banner:
        click.echo(click.style(BANNER, fg="cyan"))

    # Załaduj konfigurację
    cfg = FixOsConfig.load(
        provider=provider,
        api_key=token,
        model=model,
        agent_mode=mode,
        session_timeout=timeout,
        show_anonymized_data=not no_show_data,
    )

    # Override mode jeśli podany
    if mode:
        cfg.agent_mode = mode

    errors = cfg.validate()
    if errors:
        # Brak klucza API – zaproponuj interaktywny wybór providera
        click.echo(click.style("\n⚠️  Brak konfiguracji LLM.", fg="yellow"))
        new_cfg = interactive_provider_setup()
        if new_cfg is None:
            click.echo(click.style("❌ Anulowano. Użyj: fixos llm  aby zobaczyć dostępne providery.", fg="red"))
            sys.exit(1)
        cfg = new_cfg
        errors = cfg.validate()
        if errors:
            for err in errors:
                click.echo(click.style(f"❌ {err}", fg="red"))
            sys.exit(1)

    click.echo(click.style("\n⚙️  Konfiguracja:", fg="cyan"))
    click.echo(cfg.summary())

    # Diagnostyka
    selected_modules = modules.split(",") if modules else None
    click.echo(click.style("\n🔍 Zbieranie diagnostyki...", fg="yellow"))

    def progress(name, desc):
        click.echo(f"  → {desc}...")

    data = get_full_diagnostics(selected_modules, progress_callback=progress)

    if output:
        anon_str, _ = anonymize(str(data))
        try:
            Path(output).write_text(
                json.dumps({"anonymized": anon_str, "raw": data}, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            click.echo(click.style(f"💾 Raport: {output}", fg="green"))
        except Exception as e:
            click.echo(f"⚠️  Błąd zapisu: {e}")

    click.echo(click.style("✅ Diagnostyka gotowa.\n", fg="green"))

    # Uruchom odpowiedni tryb agenta
    if cfg.agent_mode == "autonomous":
        run_autonomous_session(
            diagnostics=data,
            config=cfg,
            show_data=cfg.show_anonymized_data,
            max_fixes=max_fixes,
        )
    else:
        run_hitl_session(
            diagnostics=data,
            config=cfg,
            show_data=cfg.show_anonymized_data,
        )


# ══════════════════════════════════════════════════════════
#  fixos token
# ══════════════════════════════════════════════════════════

@cli.group()
def token():
    """Zarządzanie tokenami API LLM."""
    pass


@token.command("set")
@click.argument("key")
@click.option("--provider", "-p", default=None, help="Provider (gemini/openai/xai/...)")
@click.option("--env-file", default=None, help="Ścieżka do pliku .env")
def token_set(key, provider, env_file):
    """
    Zapisuje token API do pliku .env.

    \b
    Przykłady:
      fixos token set AIzaSy...          # Gemini (domyślny)
      fixos token set sk-... --provider openai
      fixos token set xai-... --provider xai
    """
    target = Path(env_file) if env_file else Path.cwd() / ".env"

    # Wykryj provider po prefiksie klucza
    if not provider:
        if key.startswith("AIzaSy") or key.startswith("AI"):
            provider = "gemini"
        elif key.startswith("sk-or-"):
            provider = "openrouter"
        elif key.startswith("sk-ant-"):
            provider = "anthropic"
        elif key.startswith("sk-"):
            provider = "openai"
        elif key.startswith("xai-"):
            provider = "xai"
        elif key.startswith("gsk_"):
            provider = "groq"
        else:
            provider = "gemini"  # domyślny

    pdef = PROVIDER_DEFAULTS.get(provider, {})
    key_env = pdef.get("key_env", "API_KEY")

    # Wczytaj istniejący .env lub stwórz nowy
    lines = []
    if target.exists():
        lines = target.read_text(encoding="utf-8").splitlines()

    # Znajdź i zastąp lub dodaj
    key_line = f"{key_env}={key}"
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key_env}=") or line.startswith(f"# {key_env}="):
            lines[i] = key_line
            replaced = True
            break

    if not replaced:
        # Dodaj też LLM_PROVIDER jeśli nie ma
        if not any(l.startswith("LLM_PROVIDER=") for l in lines):
            lines.insert(0, f"LLM_PROVIDER={provider}")
        lines.append(key_line)

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)

    masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
    click.echo(click.style(f"✅ Token zapisany: {key_env}={masked}", fg="green"))
    click.echo(f"   Provider: {provider}")
    click.echo(f"   Plik: {target}")


@token.command("show")
def token_show():
    """Pokazuje aktualnie skonfigurowany token (zamaskowany)."""
    cfg = FixOsConfig.load()
    if cfg.api_key:
        key = cfg.api_key
        masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        click.echo(f"  Provider : {cfg.provider}")
        click.echo(f"  Token    : {masked}")
        click.echo(f"  Env plik : {cfg.env_file_loaded or 'brak'}")
    else:
        click.echo(click.style("  ❌ Brak tokena. Użyj: fixos token set <KLUCZ>", fg="red"))


@token.command("clear")
@click.option("--env-file", default=None)
def token_clear(env_file):
    """Usuwa token z pliku .env."""
    target = Path(env_file) if env_file else Path.cwd() / ".env"
    if not target.exists():
        click.echo("  Brak pliku .env.")
        return

    lines = target.read_text(encoding="utf-8").splitlines()
    key_patterns = [f"{p.get('key_env','API_KEY')}=" for p in PROVIDER_DEFAULTS.values()]
    new_lines = [l for l in lines if not any(l.startswith(p) for p in key_patterns)]
    target.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    click.echo(click.style("✅ Token usunięty.", fg="green"))


# ══════════════════════════════════════════════════════════
#  fixos config
# ══════════════════════════════════════════════════════════

@cli.group()
def config():
    """Zarządzanie konfiguracją fixos."""
    pass


@config.command("show")
def config_show():
    """Wyświetla aktualną konfigurację."""
    cfg = FixOsConfig.load()
    click.echo(click.style("\n⚙️  Aktualna konfiguracja:", fg="cyan"))
    click.echo(cfg.summary())
    errors = cfg.validate()
    if errors:
        click.echo(click.style("\n⚠️  Błędy konfiguracji:", fg="red"))
        for e in errors:
            click.echo(f"  • {e}")


@config.command("init")
@click.option("--force", is_flag=True, default=False, help="Nadpisz istniejący .env")
def config_init(force):
    """Tworzy plik .env na podstawie szablonu .env.example."""
    target = Path.cwd() / ".env"
    example = Path(__file__).parent.parent / ".env.example"

    if target.exists() and not force:
        click.echo(f"  Plik {target} już istnieje. Użyj --force aby nadpisać.")
        return

    if example.exists():
        import shutil
        shutil.copy(example, target)
    else:
        # Minimalny template
        target.write_text(
            "LLM_PROVIDER=gemini\n"
            "GEMINI_API_KEY=\n"
            "AGENT_MODE=hitl\n"
            "SESSION_TIMEOUT=3600\n"
            "SHOW_ANONYMIZED_DATA=true\n"
            "ENABLE_WEB_SEARCH=true\n",
            encoding="utf-8"
        )
    target.chmod(0o600)
    click.echo(click.style(f"✅ Utworzono {target}", fg="green"))
    click.echo(f"   Edytuj go: nano {target}")
    click.echo(f"   Następnie: fixos token set TWOJ_KLUCZ")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """
    Ustawia wartość w pliku .env.

    \b
    Przykłady:
      fixos config set AGENT_MODE autonomous
      fixos config set SESSION_TIMEOUT 1800
      fixos config set LLM_PROVIDER openai
    """
    target = Path.cwd() / ".env"
    lines = target.read_text(encoding="utf-8").splitlines() if target.exists() else []

    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(click.style(f"✅ {key}={value}", fg="green"))


# ══════════════════════════════════════════════════════════
#  fixos llm
# ══════════════════════════════════════════════════════════

@cli.command("llm")
@click.option("--free", is_flag=True, default=False, help="Pokaż tylko darmowe providery")
def llm_providers(free):
    """
    Lista providerów LLM z linkami do generowania kluczy API.

    \b
    Po wybraniu providera:
      1. Kliknij lub skopiuj URL z kolumny 'Klucz API'
      2. Zaloguj się i wygeneruj klucz
      3. Uruchom: fixos token set <TWÓJ_KLUCZ> --provider <PROVIDER>
    """
    providers_data = get_providers_list()
    if free:
        providers_data = [p for p in providers_data if p["free_tier"]]

    cfg = FixOsConfig.load()
    current = cfg.provider

    click.echo(click.style("\n🤖 DOSTĘPNI PROVIDERZY LLM", fg="cyan", bold=True))
    click.echo(click.style("═" * 72, fg="cyan"))

    for i, p in enumerate(providers_data, 1):
        is_current = p["name"] == current
        free_badge = click.style(" FREE", fg="green", bold=True) if p["free_tier"] else click.style(" PAID", fg="yellow")
        current_badge = click.style(" ◀ aktywny", fg="cyan", bold=True) if is_current else ""

        name_styled = click.style(f"{p['name']:<12}", fg="cyan" if is_current else "white", bold=is_current)
        click.echo(f"  {i:>2}. {name_styled}{free_badge}{current_badge}")
        click.echo(f"       {p['description']}")
        click.echo(f"       Model   : {p['model']}")
        click.echo(f"       Env var : {p['key_env']}")
        url_styled = click.style(p['key_url'], fg="blue", underline=True)
        click.echo(f"       Klucz   : {url_styled}")
        click.echo()

    click.echo(click.style("─" * 72, fg="cyan"))
    click.echo(click.style("  📋 JAK USTAWIĆ KLUCZ API:", fg="yellow", bold=True))
    click.echo()
    click.echo("  1. Skopiuj URL z kolumny 'Klucz API' i otwórz w przeglądarce")
    click.echo("  2. Zaloguj się i wygeneruj nowy klucz API")
    click.echo("  3. Uruchom jedną z poniższych komend:")
    click.echo()
    for p in providers_data:
        if p["key_env"] == "(brak – lokalny)":
            continue
        example_key = _example_key(p["name"])
        cmd = click.style(f"  fixos token set {example_key} --provider {p['name']}", fg="yellow")
        click.echo(cmd)
    click.echo()
    click.echo(click.style("  💡 Tip: ", fg="cyan") + "fixos llm --free   # pokaż tylko darmowe providery")
    click.echo()


def _example_key(provider: str) -> str:
    """Zwraca przykładowy format klucza dla danego providera."""
    examples = {
        "gemini":     "AIzaSy...",
        "openai":     "sk-...",
        "openrouter": "sk-or-v1-...",
        "xai":        "xai-...",
        "anthropic":  "sk-ant-...",
        "mistral":    "<KLUCZ_MISTRAL>",
        "groq":       "gsk_...",
        "together":   "<KLUCZ_TOGETHER>",
        "cohere":     "<KLUCZ_COHERE>",
        "deepseek":   "<KLUCZ_DEEPSEEK>",
        "cerebras":   "<KLUCZ_CEREBRAS>",
        "ollama":     "(brak – lokalny)",
    }
    return examples.get(provider, "<KLUCZ>")


# ══════════════════════════════════════════════════════════
#  fixos providers
# ══════════════════════════════════════════════════════════

@cli.command()
def providers():
    """Lista dostępnych providerów LLM (skrócona). Użyj 'fixos llm' po więcej."""
    providers_data = get_providers_list()
    click.echo(click.style("\n🤖 Dostępni providerzy LLM:", fg="cyan"))
    for p in providers_data:
        free = click.style("FREE", fg="green") if p["free_tier"] else click.style("PAID", fg="yellow")
        click.echo(f"  {p['name']:<12} [{free}]  {p['model']:<45} {p['key_env']}")
    click.echo("\nSzczegóły + linki do kluczy API:")
    click.echo("  fixos llm")
    click.echo("\nAby ustawić provider:")
    click.echo("  fixos config set LLM_PROVIDER gemini")
    click.echo("  fixos token set AIzaSy... --provider gemini")


# ══════════════════════════════════════════════════════════
#  fixos test-llm
# ══════════════════════════════════════════════════════════

@cli.command("test-llm")
@add_common_options
def test_llm(provider, token, model, no_banner):
    """Testuje połączenie z wybranym providerem LLM."""
    if not no_banner:
        click.echo(click.style(BANNER, fg="cyan"))

    cfg = FixOsConfig.load(provider=provider, api_key=token, model=model)
    errors = cfg.validate()
    if errors:
        for err in errors:
            click.echo(click.style(f"❌ {err}", fg="red"))
        sys.exit(1)

    click.echo(f"\n  Testuję: {cfg.provider} / {cfg.model}")
    click.echo(f"  URL: {cfg.base_url}")

    from .providers.llm import LLMClient, LLMError
    llm = LLMClient(cfg)
    try:
        resp = llm.chat(
            [{"role": "user", "content": "Odpowiedz jednym zdaniem po polsku: co to jest Linux, Windows, macOS?"}],
            max_tokens=100,
        )
        click.echo(click.style(f"\n  ✅ Połączenie działa!", fg="green"))
        click.echo(f"  Odpowiedź: {resp[:200]}")
    except Exception as e:
        click.echo(click.style(f"\n  ❌ Błąd: {e}", fg="red"))
        sys.exit(1)


# ══════════════════════════════════════════════════════════
#  fixos orchestrate
# ══════════════════════════════════════════════════════════

@cli.command()
@add_common_options
@click.option("--mode", type=click.Choice(["hitl", "autonomous"]), default=None,
              help="Tryb: hitl (domyślny) lub autonomous")
@click.option("--modules", "-M", default=None,
              help="Moduły diagnostyki: audio,thumbnails,hardware,system")
@click.option("--dry-run", is_flag=True, default=False,
              help="Symuluj wykonanie komend bez faktycznego uruchamiania")
@click.option("--max-iterations", default=50, show_default=True,
              help="Maksymalna liczba iteracji napraw")
@click.option("--output", "-o", default=None, help="Zapisz log sesji do JSON")
def orchestrate(provider, token, model, no_banner, mode, modules, dry_run, max_iterations, output):
    """
    Orkiestracja napraw z grafem kaskadowych problemów.

    \b
    Różnica od 'fix':
      - Buduje graf zależności między problemami (DAG)
      - Po każdej naprawie re-diagnozuje i wykrywa nowe problemy
      - LLM ocenia wynik każdej komendy (JSON structured output)
      - Transparentne drzewo problemów z linkowanymi przyczynami

    \b
    Przykłady:
      fixos orchestrate                    # pełna diagnostyka + naprawy
      fixos orchestrate --dry-run          # podgląd bez wykonywania
      fixos orchestrate --modules audio    # tylko problemy audio
      fixos orchestrate --mode autonomous  # bez pytania o każdą komendę
    """
    if not no_banner:
        click.echo(click.style(BANNER, fg="cyan"))

    cfg = FixOsConfig.load(
        provider=provider,
        api_key=token,
        model=model,
        agent_mode=mode,
    )
    if mode:
        cfg.agent_mode = mode

    errors = cfg.validate()
    if errors:
        click.echo(click.style("\n⚠️  Brak konfiguracji LLM.", fg="yellow"))
        new_cfg = interactive_provider_setup()
        if new_cfg is None:
            click.echo(click.style("❌ Anulowano. Użyj: fixos llm  aby zobaczyć dostępne providery.", fg="red"))
            sys.exit(1)
        cfg = new_cfg
        errors = cfg.validate()
        if errors:
            for err in errors:
                click.echo(click.style(f"❌ {err}", fg="red"))
            sys.exit(1)

    click.echo(click.style("\n⚙️  Konfiguracja:", fg="cyan"))
    click.echo(cfg.summary())
    if dry_run:
        click.echo(click.style("  🔍 Tryb: DRY-RUN (komendy nie będą wykonywane)", fg="yellow"))

    # Diagnostyka
    selected_modules = modules.split(",") if modules else None
    click.echo(click.style("\n🔍 Zbieranie diagnostyki...", fg="yellow"))

    def progress(name, desc):
        click.echo(f"  → {desc}...")

    data = get_full_diagnostics(selected_modules, progress_callback=progress)
    click.echo(click.style("✅ Diagnostyka gotowa.\n", fg="green"))

    # Inicjalizuj orkiestrator
    from .orchestrator import FixOrchestrator
    from .orchestrator.executor import CommandExecutor

    executor = CommandExecutor(
        default_timeout=120,
        require_confirmation=(cfg.agent_mode == "hitl"),
        dry_run=dry_run,
    )
    orch = FixOrchestrator(config=cfg, executor=executor)

    # Załaduj problemy przez LLM
    click.echo(click.style("🧠 LLM analizuje dane diagnostyczne...", fg="yellow"))
    problems = orch.load_from_diagnostics(data)

    if not problems:
        click.echo(click.style("  ✅ LLM nie wykrył problemów wymagających naprawy.", fg="green"))
        return

    from .utils.terminal import _C, render_tree_colored

    click.echo(click.style(f"\n📊 Graf problemów ({len(problems)} wykrytych):", fg="cyan"))
    print(render_tree_colored(orch.graph.nodes, orch.graph.execution_order))
    click.echo()

    # Główna pętla napraw
    summary = orch.run_sync()

    # Podsumowanie
    print(f"\n{_C.CYAN}{_C.BOLD}{'═' * 65}{_C.RESET}")
    print(f"{_C.CYAN}{_C.BOLD}  📊 PODSUMOWANIE SESJI{_C.RESET}")
    print(f"{_C.CYAN}{_C.BOLD}{'═' * 65}{_C.RESET}")
    by_status = summary.get("by_status", {})
    resolved = len(by_status.get("resolved", []))
    failed   = len(by_status.get("failed", []))
    skipped  = len(by_status.get("skipped", []))
    pending  = len(by_status.get("pending", []))
    elapsed  = summary.get("elapsed_seconds", 0)
    print(f"  {_C.GREEN}✅ Naprawiono  : {resolved}{_C.RESET}")
    print(f"  {_C.RED}❌ Nieudane    : {failed}{_C.RESET}")
    print(f"  {_C.YELLOW}⏭️  Pominięte   : {skipped}{_C.RESET}")
    print(f"  {_C.DIM}⏳ Pozostałe   : {pending}{_C.RESET}")
    print(f"  {_C.DIM}⏱️  Czas sesji  : {elapsed}s{_C.RESET}")
    print()
    print(f"{_C.CYAN}  Aktualny stan grafu:{_C.RESET}")
    print(render_tree_colored(orch.graph.nodes, orch.graph.execution_order))

    if output:
        try:
            Path(output).write_text(
                json.dumps({
                    "summary": summary,
                    "log": orch.session_log,
                    "graph": {pid: p.to_summary() for pid, p in orch.graph.nodes.items()},
                }, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            click.echo(click.style(f"\n💾 Log sesji: {output}", fg="green"))
        except Exception as e:
            click.echo(f"⚠️  Błąd zapisu: {e}")


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════

def main():
    cli()


if __name__ == "__main__":
    main()
