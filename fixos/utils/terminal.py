"""
Terminal rendering utilities – shared between hitl, orchestrator, cli.

Provides:
- _C          : ANSI color constants (auto-disabled when no TTY)
- render_md() : print markdown-formatted LLM text with ANSI colors
- colorize()  : inline **bold** / `code` colorization
- print_cmd_block()  : pretty command preview box
- print_result_box() : stdout/stderr in framed boxes
- print_problem_header() : colored severity header for a problem
- render_tree_colored()  : colorized problem graph tree
"""

from __future__ import annotations

import re
import sys
from typing import Optional


# ── Color support detection ────────────────────────────────────────────────

def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class _C:
    """ANSI color codes – no-op when terminal has no color support."""
    _on = _supports_color()

    RED     = "\033[91m"  if _on else ""
    GREEN   = "\033[92m"  if _on else ""
    YELLOW  = "\033[93m"  if _on else ""
    BLUE    = "\033[94m"  if _on else ""
    MAGENTA = "\033[95m"  if _on else ""
    CYAN    = "\033[96m"  if _on else ""
    WHITE   = "\033[97m"  if _on else ""
    BOLD    = "\033[1m"   if _on else ""
    DIM     = "\033[2m"   if _on else ""
    RESET   = "\033[0m"   if _on else ""
    BG_DARK = "\033[40m"  if _on else ""


# ── Inline colorization ────────────────────────────────────────────────────

def colorize(line: str) -> str:
    """Apply inline markdown: `code` → cyan, **bold** → bold white."""
    line = re.sub(
        r'`([^`]+)`',
        lambda m: f"{_C.CYAN}`{m.group(1)}`{_C.RESET}",
        line,
    )
    line = re.sub(
        r'\*\*([^*]+)\*\*',
        lambda m: f"{_C.BOLD}{_C.WHITE}{m.group(1)}{_C.RESET}",
        line,
    )
    return line


# ── Markdown renderer ──────────────────────────────────────────────────────

def render_md(text: str) -> None:
    """
    Print LLM markdown reply to terminal with ANSI colorization.

    Handles:
    - ``` code blocks ``` with dark background
    - # / ## headings
    - ━━━ / === / --- section dividers
    - 🔴 🟡 🟢 severity lines
    - **bold**, `inline code`
    - [N] / [A] / [S] / [Q] action items
    - - / * bullet lists
    - **Komenda:** / **Co robi:** labels
    """
    in_code_block = False
    code_lang = ""

    for raw_line in text.splitlines():
        line = raw_line

        # ── Code block fence ──────────────────────────────────────
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line.strip()[3:].strip()
                label = code_lang or "code"
                pad = max(0, 48 - len(label))
                print(f"{_C.BG_DARK}{_C.DIM}  ┌─ {label} {'─' * pad}┐{_C.RESET}")
            else:
                in_code_block = False
                print(f"{_C.BG_DARK}{_C.DIM}  └{'─' * 54}┘{_C.RESET}")
            continue

        if in_code_block:
            print(f"{_C.BG_DARK}{_C.CYAN}  │ {_C.GREEN}{line}{_C.RESET}")
            continue

        # ── Headings # / ## ────────────────────────────────────────
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            if level == 1:
                print(f"\n{_C.CYAN}{_C.BOLD}  {'═' * 56}{_C.RESET}")
                print(f"{_C.CYAN}{_C.BOLD}  {title.upper()}{_C.RESET}")
                print(f"{_C.CYAN}{_C.BOLD}  {'═' * 56}{_C.RESET}")
            elif level == 2:
                print(f"\n{_C.CYAN}{_C.BOLD}  ── {title} {'─' * max(0, 50 - len(title))}{_C.RESET}")
            else:
                print(f"{_C.CYAN}  {title}{_C.RESET}")
            continue

        # ── Section dividers (━━━ TEXT ━━━ / === / ---) ────────────
        stripped = line.strip()
        if re.match(r'^[━═─]{3,}', stripped):
            # Extract text between dividers if present
            inner = re.sub(r'^[━═─\s]+|[━═─\s]+$', '', stripped)
            if inner:
                pad = max(0, 52 - len(inner))
                print(f"\n{_C.CYAN}{_C.BOLD}  ━━━ {inner} {'━' * pad}{_C.RESET}")
            else:
                print(f"{_C.CYAN}{_C.DIM}  {'─' * 56}{_C.RESET}")
            continue

        # ── Severity lines ─────────────────────────────────────────
        if stripped.startswith("🔴"):
            print(f"{_C.RED}{_C.BOLD}{colorize(line)}{_C.RESET}")
            continue
        if stripped.startswith("🟡"):
            print(f"{_C.YELLOW}{_C.BOLD}{colorize(line)}{_C.RESET}")
            continue
        if stripped.startswith("🟢"):
            print(f"{_C.GREEN}{_C.BOLD}{colorize(line)}{_C.RESET}")
            continue
        if stripped.startswith("✅"):
            print(f"{_C.GREEN}{colorize(line)}{_C.RESET}")
            continue
        if stripped.startswith("❌"):
            print(f"{_C.RED}{colorize(line)}{_C.RESET}")
            continue
        if stripped.startswith("⚠️") or stripped.startswith("⚠"):
            print(f"{_C.YELLOW}{colorize(line)}{_C.RESET}")
            continue

        # ── Action items [N] / [A] / [S] / [Q] ────────────────────
        if re.match(r'^\s*\[([\dASDQ?!])\]', line):
            print(f"{_C.YELLOW}{colorize(line)}{_C.RESET}")
            continue

        # ── **Komenda:** / **Co robi:** labels ─────────────────────
        if "**Komenda:**" in line or "**Co robi:**" in line:
            print(f"{_C.CYAN}{colorize(line)}{_C.RESET}")
            continue

        # ── Bullet list items (- / *) ──────────────────────────────
        if re.match(r'^\s*[-*]\s+', line):
            bullet_line = re.sub(r'^(\s*)([-*])(\s+)', r'\1\2\3', line)
            print(f"{_C.WHITE}{colorize(bullet_line)}{_C.RESET}")
            continue

        # ── Numbered list items ────────────────────────────────────
        if re.match(r'^\s*\d+\.\s+', line):
            print(f"{_C.WHITE}{colorize(line)}{_C.RESET}")
            continue

        # ── Empty line ─────────────────────────────────────────────
        if not stripped:
            print()
            continue

        # ── Regular line ───────────────────────────────────────────
        print(colorize(line))


# ── Command preview box ────────────────────────────────────────────────────

def print_cmd_block(cmd: str, comment: str = "", dry_run: bool = False) -> None:
    """Print a framed command preview block."""
    label = "DRY-RUN" if dry_run else "KOMENDA"
    color = _C.DIM if dry_run else _C.CYAN
    print()
    print(f"{color}{_C.BOLD}  ┌─ {label} {'─' * (50 - len(label))}┐{_C.RESET}")
    print(f"{color}  │  {_C.GREEN if not dry_run else _C.DIM}{cmd}{_C.RESET}")
    if comment:
        wrapped = _wrap(comment, 50)
        for i, part in enumerate(wrapped):
            prefix = "  │  📝 " if i == 0 else "  │     "
            print(f"{_C.DIM}{prefix}{part}{_C.RESET}")
    print(f"{color}{_C.BOLD}  └{'─' * 54}┘{_C.RESET}")


# ── Result boxes ───────────────────────────────────────────────────────────

def print_stdout_box(stdout: str, max_lines: int = 30) -> None:
    """Print stdout in a framed dark box."""
    lines = stdout.strip().splitlines()
    print(f"{_C.BG_DARK}{_C.DIM}  ┌─ stdout {'─' * 45}┐{_C.RESET}")
    for line in lines[:max_lines]:
        print(f"{_C.BG_DARK}  │ {_C.GREEN}{line}{_C.RESET}")
    if len(lines) > max_lines:
        print(f"{_C.BG_DARK}  │ {_C.DIM}... ({len(lines) - max_lines} więcej linii){_C.RESET}")
    print(f"{_C.BG_DARK}{_C.DIM}  └{'─' * 54}┘{_C.RESET}")


def print_stderr_box(stderr: str, max_lines: int = 15) -> None:
    """Print stderr in a framed dark box."""
    lines = stderr.strip().splitlines()
    print(f"{_C.BG_DARK}{_C.DIM}  ┌─ stderr {'─' * 45}┐{_C.RESET}")
    for line in lines[:max_lines]:
        print(f"{_C.BG_DARK}  │ {_C.RED}{line}{_C.RESET}")
    if len(lines) > max_lines:
        print(f"{_C.BG_DARK}  │ {_C.DIM}... ({len(lines) - max_lines} więcej linii){_C.RESET}")
    print(f"{_C.BG_DARK}{_C.DIM}  └{'─' * 54}┘{_C.RESET}")


# ── Problem header ─────────────────────────────────────────────────────────

SEVERITY_COLOR = {
    "critical": _C.RED,
    "warning":  _C.YELLOW,
    "info":     _C.GREEN,
}
SEVERITY_ICON = {
    "critical": "🔴",
    "warning":  "🟡",
    "info":     "🟢",
}
STATUS_ICON = {
    "pending":     "⏳",
    "in_progress": "🔄",
    "resolved":    "✅",
    "failed":      "❌",
    "blocked":     "🚫",
    "skipped":     "⏭️ ",
}


def print_problem_header(
    problem_id: str,
    description: str,
    severity: str,
    status: Optional[str] = None,
    attempts: int = 0,
    max_attempts: int = 3,
) -> None:
    """Print a colored problem header block."""
    color = SEVERITY_COLOR.get(severity, _C.WHITE)
    icon = SEVERITY_ICON.get(severity, "⚪")
    status_str = ""
    if status:
        s_icon = STATUS_ICON.get(status, "?")
        status_str = f"  {_C.DIM}[{s_icon} {status}]{_C.RESET}"
    attempt_str = ""
    if attempts > 0:
        attempt_str = f"  {_C.DIM}(próba {attempts}/{max_attempts}){_C.RESET}"

    print()
    print(f"{color}{_C.BOLD}  {'─' * 56}{_C.RESET}")
    print(f"{color}{_C.BOLD}  {icon} [{problem_id}]{_C.RESET}{status_str}{attempt_str}")
    # Wrap long descriptions
    for part in _wrap(description, 54):
        print(f"{color}  {part}{_C.RESET}")
    print(f"{color}{_C.BOLD}  {'─' * 56}{_C.RESET}")


# ── Graph tree renderer ────────────────────────────────────────────────────

def render_tree_colored(nodes: dict, execution_order: list[str]) -> str:
    """
    Render a ProblemGraph as a colorized ANSI string.
    nodes: dict[str, Problem]
    """
    lines: list[str] = []
    visited: set[str] = set()

    def _render(pid: str, indent: int = 0) -> None:
        if pid in visited or pid not in nodes:
            return
        visited.add(pid)
        p = nodes[pid]
        color = SEVERITY_COLOR.get(p.severity, _C.WHITE)
        sev_icon = SEVERITY_ICON.get(p.severity, "⚪")
        stat_icon = STATUS_ICON.get(p.status, "?")
        prefix = "  " * indent + ("└─ " if indent > 0 else "  ")
        desc = p.description[:70] + ("…" if len(p.description) > 70 else "")
        lines.append(
            f"{prefix}{color}{_C.BOLD}{sev_icon} [{p.id}]{_C.RESET} "
            f"{color}{desc}{_C.RESET}  {_C.DIM}{stat_icon}{_C.RESET}"
        )
        for child_id in p.may_cause:
            _render(child_id, indent + 1)

    # Roots first (no caused_by)
    roots = [p for p in nodes.values() if not p.caused_by]
    for root in roots:
        _render(root.id)

    # Orphaned (caused_by set but parent not in graph)
    for p in nodes.values():
        if p.id not in visited:
            color = SEVERITY_COLOR.get(p.severity, _C.WHITE)
            sev_icon = SEVERITY_ICON.get(p.severity, "⚪")
            stat_icon = STATUS_ICON.get(p.status, "?")
            desc = p.description[:70] + ("…" if len(p.description) > 70 else "")
            lines.append(
                f"  {_C.DIM}◦{_C.RESET} {color}{_C.BOLD}{sev_icon} [{p.id}]{_C.RESET} "
                f"{color}{desc}{_C.RESET}  {_C.DIM}{stat_icon}{_C.RESET}"
            )

    return "\n".join(lines) if lines else f"  {_C.DIM}(brak problemów){_C.RESET}"


# ── Helpers ────────────────────────────────────────────────────────────────

def _wrap(text: str, width: int) -> list[str]:
    """Simple word-wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).lstrip()
    if current:
        lines.append(current)
    return lines or [""]
