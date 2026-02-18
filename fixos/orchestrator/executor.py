"""
CommandExecutor – bezpieczne wykonywanie komend systemowych.
Waliduje komendy przed wykonaniem, obsługuje timeout i resource limits.
"""

from __future__ import annotations

import asyncio
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Optional


class DangerousCommandError(Exception):
    def __init__(self, command: str, reason: str = ""):
        self.command = command
        self.reason = reason
        super().__init__(f"Niebezpieczna komenda: {command!r}" + (f" ({reason})" if reason else ""))


class CommandTimeoutError(Exception):
    def __init__(self, command: str, timeout: int):
        self.command = command
        self.timeout = timeout
        super().__init__(f"Timeout ({timeout}s) dla komendy: {command!r}")


@dataclass
class ExecutionResult:
    command: str
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    executed: bool = True
    preview: str = ""
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.executed and self.returncode == 0

    def to_context(self) -> dict:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout[:2000],
            "stderr": self.stderr[:1000],
            "success": self.success,
            "executed": self.executed,
        }


DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/(?!\w)", "rm -rf / jest destruktywne"),
    (r"rm\s+-rf\s+/(?:boot|etc|usr|lib|bin|sbin|sys|proc|dev)\b", "usuwanie katalogu systemowego"),
    (r"dd\s+if=.*of=/dev/(?:sd|nvme|vd|hd)[a-z](?!\d)", "nadpisywanie dysku przez dd"),
    (r"mkfs\.", "formatowanie systemu plików"),
    (r">\s*/dev/(?:sd|nvme|vd|hd)", "zapis bezpośrednio na urządzenie blokowe"),
    (r":\(\)\{.*\};:", "fork bomb"),
    (r"chmod\s+-R\s+777\s+/", "chmod 777 na katalogu głównym"),
    (r"chown\s+-R\s+.*\s+/(?!\w)", "chown na katalogu głównym"),
    (r"wget.*\|\s*(?:ba)?sh", "pobieranie i wykonywanie skryptu"),
    (r"curl.*\|\s*(?:ba)?sh", "pobieranie i wykonywanie skryptu"),
]

NEEDS_SUDO_PREFIXES = [
    "dnf", "rpm", "systemctl", "firewall-cmd", "setenforce",
    "chmod 0", "chown", "modprobe", "rmmod", "insmod",
    "mount", "umount", "fdisk", "parted", "lvextend",
    "useradd", "userdel", "usermod", "groupadd",
    "update-grub", "grub2-mkconfig",
]

IDEMPOTENT_CHECK: dict[str, str] = {
    r"dnf install (.+)": "rpm -q {0} &>/dev/null",
    r"systemctl enable (.+)": "systemctl is-enabled {0} &>/dev/null",
    r"systemctl start (.+)": "systemctl is-active {0} &>/dev/null",
    r"mkdir -p (.+)": "test -d {0}",
}


class CommandExecutor:
    """
    Bezpieczny executor komend z:
    - walidacją niebezpiecznych wzorców
    - automatycznym sudo dla komend systemowych
    - idempotentnym sprawdzaniem stanu przed wykonaniem
    - timeoutem i obsługą błędów
    """

    def __init__(
        self,
        default_timeout: int = 60,
        require_confirmation: bool = True,
        dry_run: bool = False,
    ):
        self.default_timeout = default_timeout
        self.require_confirmation = require_confirmation
        self.dry_run = dry_run

    def is_dangerous(self, command: str) -> tuple[bool, str]:
        """Sprawdza czy komenda jest potencjalnie destruktywna."""
        for pattern, reason in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True, reason
        return False, ""

    def needs_sudo(self, command: str) -> bool:
        cmd = command.strip()
        if cmd.startswith("sudo"):
            return False
        # systemctl --user must NOT run under sudo (breaks DBUS session bus)
        if cmd.startswith("systemctl") and "--user" in cmd:
            return False
        return any(cmd.startswith(p) for p in NEEDS_SUDO_PREFIXES)

    def add_sudo(self, command: str) -> str:
        if self.needs_sudo(command):
            return "sudo " + command.strip()
        return command

    def _make_noninteractive(self, command: str) -> str:
        """Dodaje flagi nieinteraktywne do komend menedżerów pakietów."""
        pkg_install = re.match(
            r"^(sudo\s+)?(apt-get|apt|dnf|yum)\s+(install|upgrade|dist-upgrade|update)\b",
            command.strip(),
            re.IGNORECASE,
        )
        if pkg_install and "-y" not in command and "--yes" not in command:
            # Wstaw -y po subkomendzie (np. "apt-get install" → "apt-get install -y")
            subcmd = pkg_install.group(3)
            command = command.replace(subcmd, f"{subcmd} -y", 1)
        return command

    def check_idempotent(self, command: str) -> Optional[str]:
        """Zwraca komendę sprawdzającą stan (jeśli znana), None jeśli nie dotyczy."""
        for pattern, check_tpl in IDEMPOTENT_CHECK.items():
            m = re.match(pattern, command.strip(), re.IGNORECASE)
            if m:
                try:
                    return check_tpl.format(*m.groups())
                except IndexError:
                    pass
        return None

    def execute_sync(
        self,
        command: str,
        timeout: Optional[int] = None,
        add_sudo: bool = True,
        check_idempotent: bool = True,
    ) -> ExecutionResult:
        """Synchroniczne wykonanie komendy."""
        timeout = timeout or self.default_timeout

        # Sprawdź niebezpieczne wzorce
        dangerous, reason = self.is_dangerous(command)
        if dangerous:
            raise DangerousCommandError(command, reason)

        # Dodaj sudo jeśli potrzeba
        if add_sudo:
            command = self.add_sudo(command)

        # Wymuś tryb nieinteraktywny dla menedżerów pakietów
        command = self._make_noninteractive(command)

        # Sprawdź idempotentność
        if check_idempotent:
            check_cmd = self.check_idempotent(command)
            if check_cmd:
                try:
                    result = subprocess.run(
                        check_cmd, shell=True, capture_output=True, timeout=5
                    )
                    if result.returncode == 0:
                        return ExecutionResult(
                            command=command,
                            returncode=0,
                            stdout="(już wykonane – stan aktualny)",
                            executed=False,
                        )
                except Exception:
                    pass

        if self.dry_run:
            return ExecutionResult(
                command=command,
                executed=False,
                preview=f"[DRY-RUN] {command}",
            )

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                command=command,
                returncode=proc.returncode,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                executed=True,
            )
        except subprocess.TimeoutExpired:
            raise CommandTimeoutError(command, timeout)
        except Exception as e:
            return ExecutionResult(
                command=command,
                executed=False,
                error=str(e),
            )

    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        add_sudo: bool = True,
    ) -> ExecutionResult:
        """Asynchroniczne wykonanie komendy."""
        timeout = timeout or self.default_timeout

        dangerous, reason = self.is_dangerous(command)
        if dangerous:
            raise DangerousCommandError(command, reason)

        if add_sudo:
            command = self.add_sudo(command)

        if self.dry_run:
            return ExecutionResult(
                command=command,
                executed=False,
                preview=f"[DRY-RUN] {command}",
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise CommandTimeoutError(command, timeout)

            return ExecutionResult(
                command=command,
                returncode=proc.returncode or 0,
                stdout=stdout_b.decode(errors="replace").strip(),
                stderr=stderr_b.decode(errors="replace").strip(),
                executed=True,
            )
        except (DangerousCommandError, CommandTimeoutError):
            raise
        except Exception as e:
            return ExecutionResult(
                command=command,
                executed=False,
                error=str(e),
            )
