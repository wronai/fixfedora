#!/usr/bin/env python3
import sys

enhancements = r'''def add_shared_options(func):
    """Shared options for both scan and fix commands"""
    func = click.option("--disc", is_flag=True, default=False,
                       help="Analiza zajętości dysku + grupowanie przyczyn")(func)
    func = click.option("--disk", "disc", is_flag=True, default=False,
                       help="Analiza zajętości dysku (alias do --disc)")(func)
    func = click.option("--dry-run", is_flag=True, default=False,
                       help="Symuluj wykonanie komend bez faktycznego uruchamiania")(func)
    func = click.option("--interactive/--no-interactive", default=True,
                       help="Tryb interaktywny (pytaj przed każdą akcją)")(func)
    func = click.option("--json", "json_output", is_flag=True, default=False,
                       help="Wyjście w formacie JSON")(func)
    func = click.option("--llm-fallback/--no-llm-fallback", default=True,
                       help="Użyj LLM gdy heurystyki nie wystarczą")(func)
    return func

# Enhanced fix command - replace the existing fix function with this
@cli.command()
@add_common_options
@click.option("--mode", type=click.Choice(["hitl", "autonomous"]), default=None,
              help="Tryb: hitl (domyślny) lub autonomous")
@click.option("--timeout", default=300, show_default=True,
              help="Timeout sesji agenta (sekundy)")
@click.option("--modules", "-M", default=None,
              help="Moduły diagnostyki: audio,thumbnails,hardware,system")
@click.option("--no-show-data", is_flag=True, default=False,
              help="Nie pokazuj danych diagnostycznych (tylko podsumowanie)")
@click.option("--output", "-o", default=None, help="Zapisz log sesji do JSON")
@click.option("--max-fixes", default=10, show_default=True,
              help="Maksymalna liczba napraw w sesji")
@add_shared_options
def fix(provider, token, model, no_banner, mode, timeout, modules, no_show_data, output, max_fixes,
        disc, dry_run, interactive, json_output, llm_fallback):
    """
    Przeprowadza pełną diagnostykę i uruchamia sesję naprawczą z LLM.

    \b
    Tryby:
      hitl        – Human-in-the-Loop (pyta o każdą akcję) [domyślny]
      autonomous  – Agent sam wykonuje komendy (UWAGA: wymaga potwierdzenia)

    \b
    Opcje dyskowe:
      --disc      – Analiza zajętości dysku + grupowanie przyczyn
      --dry-run   – Symulacja bez wykonywania akcji
      --interactive – Tryb interaktywny (domyślnie włączony)
      --json      – Wyjście w formacie JSON
      --llm-fallback – Użyj LLM gdy heurystyki nie wystarczą

    \b
    Przykłady:
      fixos fix                              # domyślnie hitl + Gemini z .env
      fixos fix --disc                       # z analizą dysku
      fixos fix --disc --dry-run             # analiza dysku bez wykonywania
      fixos fix --mode autonomous            # tryb autonomiczny
      fixos fix --modules audio,thumbnails   # tylko audio i thumbnails
      fixos fix --provider openai --token sk-...
    """
    if not no_banner:
        click.echo(click.style(BANNER, fg="cyan"))

    # Load configuration
    cfg = FixOsConfig.load(
        provider=provider,
        api_key=token,
        model=model,
        agent_mode=mode,
        session_timeout=timeout,
        show_anonymized_data=not no_show_data,
    )

    # Override mode if provided
    if mode:
        cfg.agent_mode = mode

    errors = cfg.validate()
    if errors:
        # No API key - propose interactive provider selection
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
    if disc:
        click.echo(click.style("  💾 Analiza dysku: Włączona", fg="blue"))

    # Diagnostics
    selected_modules = modules.split(",") if modules else None
    click.echo(click.style("\n🔍 Zbieranie diagnostyki...", fg="yellow"))

    def progress(name, desc):
        click.echo(f"  → {desc}...")

    data = get_full_diagnostics(selected_modules, progress_callback=progress)
    
    # Add disk analysis if --disc flag is used
    if disc:
        click.echo(click.style("💾 Analizowanie zajętości dysku...", fg="blue"))
        try:
            from .diagnostics.disk_analyzer import DiskAnalyzer
            analyzer = DiskAnalyzer()
            disk_analysis = analyzer.analyze_disk_usage()
            
            if "error" not in disk_analysis:
                data["disk_analysis"] = disk_analysis
                
                # Show disk status
                status_color = {
                    "critical": "red",
                    "warning": "yellow", 
                    "moderate": "blue",
                    "healthy": "green"
                }.get(disk_analysis.get("status", "unknown"), "gray")
                
                click.echo(click.style(
                    f"  📊 Dysk: {disk_analysis['usage_percent']:.1f}% zajęty "
                    f"({disk_analysis['used_gb']:.1f}GB / {disk_analysis['total_gb']:.1f}GB)",
                    fg=status_color
                ))
                
                # Show cleanup suggestions
                suggestions = disk_analysis.get("suggestions", [])
                if suggestions:
                    safe_suggestions = [s for s in suggestions if s.get("safe", False)]
                    total_safe_gb = sum(s.get("size_gb", 0) for s in safe_suggestions)
                    
                    if total_safe_gb > 0.1:
                        click.echo(click.style(
                            f"  🧹 Można bezpiecznie zwolnić: {total_safe_gb:.1f}GB w {len(safe_suggestions)} akcjach",
                            fg="green"
                        ))
            else:
                click.echo(click.style(f"  ⚠️  Błąd analizy dysku: {disk_analysis['error']}", fg="red"))
                
        except ImportError:
            click.echo(click.style("  ⚠️  Moduł analizy dysku nie jest dostępny", fg="yellow"))
        except Exception as e:
            click.echo(click.style(f"  ⚠️  Błąd podczas analizy dysku: {str(e)}", fg="red"))

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

    # Handle disk analysis mode
    if disc and "disk_analysis" in data:
        return handle_disk_cleanup_mode(data["disk_analysis"], cfg, dry_run, interactive, json_output, llm_fallback)

    # Run appropriate agent mode
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


def handle_disk_cleanup_mode(disk_analysis: Dict[str, Any], cfg, dry_run: bool, 
                           interactive: bool, json_output: bool, llm_fallback: bool):
    """Handle disk cleanup mode with interactive planning"""
    from .interactive.cleanup_planner import CleanupPlanner
    
    suggestions = disk_analysis.get("suggestions", [])
    if not suggestions:
        click.echo(click.style("✅ Brak sugestii czyszczenia dysku.", fg="green"))
        return
    
    # Create cleanup plan
    planner = CleanupPlanner()
    plan = planner.create_cleanup_plan(suggestions)
    
    if json_output:
        import json
        click.echo(json.dumps(plan, indent=2, default=str))
        return
    
    # Display plan summary
    summary = plan["summary"]
    click.echo(click.style(f"\n📊 Plan czyszczenia dysku:", fg="cyan"))
    click.echo(f"  🔢 Akcje: {summary['total_actions']}")
    click.echo(f"  💾 Miejsce: {summary['total_size_gb']:.1f} GB")
    click.echo(f"  ✅ Bezpieczne: {summary['safe_size_gb']:.1f} GB")
    click.echo(f"  📂 Kategorie: {summary['categories_count']}")
    
    # Show categories
    for category_id, category_data in plan["categories"].items():
        info = category_data["info"]
        click.echo(f"\n{info['icon']} {info['name']}:")
        click.echo(f"  📁 Akcje: {category_data['actions_count']}")
        click.echo(f"  💾 Miejsce: {category_data['total_size_gb']:.1f} GB")
        
        # Show top actions
        for action in category_data["actions"][:3]:
            safe_icon = "✅" if action["safe"] else "⚠️"
            priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(action["priority"], "⚪")
            click.echo(f"    {safe_icon} {priority_icon} {action['description']} ({action['size_gb']:.1f}GB)")
    
    # Show recommendations
    recommendations = plan.get("recommendations", [])
    if recommendations:
        click.echo(click.style(f"\n💡 Rekomendacje:", fg="yellow"))
        for rec in recommendations:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(rec["priority"], "gray")
            click.echo(click.style(f"  🎯 {rec['title']}", fg=priority_color))
            click.echo(f"     {rec['description']}")
    
    if dry_run:
        click.echo(click.style("\n🔍 Tryb DRY-RUN - żadne akcje nie zostaną wykonane", fg="yellow"))
        return
    
    if interactive:
        selection = planner.interactive_selection(plan)
        click.echo(click.style(f"\n✅ Wybrano {selection['total_selected']} akcji do wykonania", fg="green"))
        click.echo(click.style(f"💾 Szacowane miejsce: {selection['estimated_space_gb']:.1f} GB", fg="green"))
        
        # Execute selected actions
        execute_cleanup_actions(selection["selected_actions"], cfg, llm_fallback)
    else:
        # Auto-execute safe actions
        safe_actions = [a for a in plan["prioritized_actions"] if a.get("safe", False)]
        if safe_actions:
            click.echo(click.style(f"\n🤖 Automatyczne wykonanie {len(safe_actions)} bezpiecznych akcji", fg="blue"))
            execute_cleanup_actions(safe_actions, cfg, llm_fallback)
        else:
            click.echo(click.style("\n⚠️  Brak bezpiecznych akcji do automatycznego wykonania", fg="yellow"))


def execute_cleanup_actions(actions: List[Dict], cfg, llm_fallback: bool):
    """Execute cleanup actions with safety checks"""
    from .orchestrator.executor import CommandExecutor
    
    executor = CommandExecutor(
        default_timeout=60,
        require_confirmation=False,  # Already confirmed
        dry_run=False
    )
    
    successful = []
    failed = []
    
    for i, action in enumerate(actions, 1):
        click.echo(f"\n[{i}/{len(actions)}] {action['description']}")
        
        if not action.get("safe", False):
            if not click.confirm(f"⚠️  Ta akcja nie jest bezpieczna. Kontynuować?"):
                click.echo("⏭️  Pominięto")
                continue
        
        try:
            result = executor.execute_command(action["command"], shell=True)
            if result["exit_code"] == 0:
                click.echo(click.style(f"✅ Sukces: {action['description']}", fg="green"))
                successful.append(action)
            else:
                click.echo(click.style(f"❌ Błąd: {action['description']}", fg="red"))
                click.echo(f"   {result.get('stderr', 'Unknown error')}")
                failed.append(action)
        except Exception as e:
            click.echo(click.style(f"❌ Wyjątek: {str(e)}", fg="red"))
            failed.append(action)
    
    # Summary
    click.echo(click.style(f"\n📊 Podsumowanie:", fg="cyan"))
    click.echo(f"✅ Sukces: {len(successful)}")
    click.echo(f"❌ Błędy: {len(failed)}")
    
    if successful:
        total_freed = sum(a.get("size_gb", 0) for a in successful)
        click.echo(click.style(f"💾 Zwolniono miejsca: ~{total_freed:.1f} GB", fg="green"))
    
    if failed and llm_fallback:
        click.echo(click.style("\n🤖 Próba naprawy błędów za pomocą LLM...", fg="yellow"))
        # Implement LLM fallback for failed actions
        try_llm_fallback_for_failures(failed, cfg)


def try_llm_fallback_for_failures(failed_actions: List[Dict], cfg):
    """Use LLM to analyze and suggest fixes for failed cleanup actions"""
    try:
        from .providers.llm import LLMClient
        
        llm = LLMClient(cfg)
        
        for action in failed_actions[:3]:  # Limit to first 3 failures
            prompt = f"""
Cleanup action failed:
- Description: {action['description']}
- Command: {action['command']}
- Path: {action['path']}

Please suggest alternative approaches to clean this up safely.
Respond with JSON format: {{"alternative_commands": ["cmd1", "cmd2"], "explanation": "..."}}
"""
            
            response = llm.chat([{"role": "user", "content": prompt}], max_tokens=200)
            click.echo(click.style(f"💡 Sugestia LLM dla {action['description']}:", fg="blue"))
            click.echo(f"   {response[:200]}...")
            
    except Exception as e:
        click.echo(click.style(f"⚠️  LLM fallback nieudany: {str(e)}", fg="red"))

# Enhanced scan command - add these options to existing scan command
@cli.command()
@click.option("--audio", "modules", flag_value="audio", help="Tylko diagnostyka dźwięku")
@click.option("--thumbnails", "modules", flag_value="thumbnails", help="Tylko podglądy plików")
@click.option("--hardware", "modules", flag_value="hardware", help="Tylko sprzęt")
@click.option("--system", "modules", flag_value="system", help="Tylko system")
@click.option("--all", "modules", flag_value="all", default=True, help="Wszystkie moduły (domyślnie)")
@add_shared_options
@click.option("--output", "-o", default=None, help="Zapisz wyniki do pliku")
def scan(modules, output, show_raw, no_banner, disc, dry_run, interactive, json_output, llm_fallback):
    """
    Przeprowadza diagnostykę systemu.

    \b
    Nowe opcje:
      --disc          – Analiza zajętości dysku
      --dry-run       – Symulacja (dla kompatybilności)
      --interactive   – Tryb interaktywny (dla kompatybilności)
      --json          – Wyjście w formacie JSON
      --llm-fallback  – Użyj LLM gdy heurystyki nie wystarczą

    \b
    Przykłady:
      fixos scan                    # pełna diagnostyka
      fixos scan --disc              # z analizą dysku
      fixos scan --disc --json      # analiza dysku w JSON
      fixos scan --audio             # tylko diagnostyka dźwięku
    """
    if not no_banner:
        click.echo(click.style(BANNER, fg="cyan"))

    selected_modules = [modules] if modules else None
    click.echo(click.style("🔍 Zbieranie diagnostyki...", fg="yellow"))

    def progress(name, desc):
        click.echo(f"  → {desc}...")

    data = get_full_diagnostics(selected_modules, progress_callback=progress)
    
    # Add disk analysis if --disc flag is used
    if disc:
        click.echo(click.style("💾 Analizowanie zajętości dysku...", fg="blue"))
        try:
            from .diagnostics.disk_analyzer import DiskAnalyzer
            analyzer = DiskAnalyzer()
            disk_analysis = analyzer.analyze_disk_usage()
            
            if "error" not in disk_analysis:
                data["disk_analysis"] = disk_analysis
                
                if json_output:
                    import json
                    click.echo(json.dumps(disk_analysis, indent=2, default=str))
                else:
                    # Display disk analysis summary
                    click.echo(click.style(f"\n📊 Analiza dysku:", fg="cyan"))
                    click.echo(f"  📈 Użycie: {disk_analysis['usage_percent']:.1f}%")
                    click.echo(f"  💾 Zajęte: {disk_analysis['used_gb']:.1f} GB")
                    click.echo(f"  🆓 Wolne: {disk_analysis['free_gb']:.1f} GB")
                    click.echo(f"  📁 Status: {disk_analysis['status']}")
                    
                    # Show top cleanup suggestions
                    suggestions = disk_analysis.get("suggestions", [])
                    if suggestions:
                        click.echo(click.style(f"\n🧹 Sugestie czyszczenia:", fg="yellow"))
                        for suggestion in suggestions[:5]:
                            safe_icon = "✅" if suggestion.get("safe") else "⚠️"
                            click.echo(f"  {safe_icon} {suggestion['description']} ({suggestion.get('size_gb', 0):.1f}GB)")
            else:
                click.echo(click.style(f"❌ Błąd analizy dysku: {disk_analysis['error']}", fg="red"))
                
        except ImportError:
            click.echo(click.style("⚠️  Moduł analizy dysku nie jest dostępny", fg="yellow"))
        except Exception as e:
            click.echo(click.style(f"⚠️  Błąd podczas analizy dysku: {str(e)}", fg="red"))

    if show_raw:
        import json
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        # Display regular diagnostic summary
        click.echo(click.style("✅ Diagnostyka zakończona.", fg="green"))
        
    if output:
        try:
            import json
            Path(output).write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            click.echo(click.style(f"💾 Zapisano: {output}", fg="green"))
        except Exception as e:
            click.echo(f"⚠️  Błąd zapisu: {e}")
'''

import re

with open("fixos/cli.py", "r", encoding="utf-8") as f:
    text = f.read()

# Make sure imports are there
if "from typing import Dict, Any, Optional" not in text:
    text = text.replace("from pathlib import Path\n", "from pathlib import Path\nfrom typing import Dict, Any, Optional, List\n")

if "from typing import Dict, Any, Optional, List" not in text:
    text = text.replace("from typing import Dict, Any, Optional\n", "from typing import Dict, Any, Optional, List\n")


# Add shared options definition
shared_opts = """
def add_shared_options(func):
    \"\"\"Shared options for both scan and fix commands\"\"\"
    func = click.option("--disc", is_flag=True, default=False,
                       help="Analiza zajętości dysku + grupowanie przyczyn")(func)
    func = click.option("--disk", "disc", is_flag=True, default=False,
                       help="Analiza zajętości dysku (alias do --disc)")(func)
    func = click.option("--dry-run", is_flag=True, default=False,
                       help="Symuluj wykonanie komend bez faktycznego uruchamiania")(func)
    func = click.option("--interactive/--no-interactive", default=True,
                       help="Tryb interaktywny (pytaj przed każdą akcją)")(func)
    func = click.option("--json", "json_output", is_flag=True, default=False,
                       help="Wyjście w formacie JSON")(func)
    func = click.option("--llm-fallback/--no-llm-fallback", default=True,
                       help="Użyj LLM gdy heurystyki nie wystarczą")(func)
    return func
"""

if "def add_shared_options" not in text:
    text = text.replace("def add_common_options(fn):\n    for opt in reversed(COMMON_OPTIONS):\n        fn = opt(fn)\n    return fn", "def add_common_options(fn):\n    for opt in reversed(COMMON_OPTIONS):\n        fn = opt(fn)\n    return fn\n" + shared_opts)


parts_scan = text.split("#  fixos scan")
parts_fix = parts_scan[1].split("#  fixos fix")
parts_token = parts_fix[1].split("#  fixos token")

before_scan = parts_scan[0]
after_token = parts_token[1]

# enhancements str has the parts:
enh_parts = enhancements.split("# Enhanced scan command - add these options to existing scan command")
fix_part = enh_parts[0].split("# Enhanced fix command - replace the existing fix function with this")[1].strip()
scan_part = enh_parts[1].strip()

new_text = (
    before_scan +
    "#  fixos scan\n# ══════════════════════════════════════════════════════════\n\n" +
    scan_part + "\n\n" +
    "def _print_quick_issues(data: dict):\n    " + parts_fix[0].split("def _print_quick_issues(data: dict):\n    ")[1] +
    "#  fixos fix\n# ══════════════════════════════════════════════════════════\n\n" +
    fix_part + "\n\n" +
    "#  fixos token" + after_token
)

with open("fixos/cli.py", "w", encoding="utf-8") as f:
    f.write(new_text)

print("Patch applied successfully")
