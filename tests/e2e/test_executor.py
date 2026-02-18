"""
Testy e2e – CommandExecutor (integracja z prawdziwymi komendami).
Weryfikuje: -y injection, sudo logic, idempotency, dangerous blocking.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from fixos.orchestrator.executor import CommandExecutor, DangerousCommandError


@pytest.fixture
def ex_live():
    """Executor w trybie live (wykonuje komendy)."""
    return CommandExecutor(default_timeout=10, require_confirmation=False, dry_run=False)


@pytest.fixture
def ex_dry():
    """Executor w trybie dry-run."""
    return CommandExecutor(default_timeout=10, require_confirmation=False, dry_run=True)


class TestNonInteractiveInjection:
    """Testy wstrzykiwania -y do komend pakietów."""

    def test_apt_get_install_y_injected(self, ex_dry):
        result = ex_dry.execute_sync(
            "apt-get install curl", add_sudo=False, check_idempotent=False
        )
        assert "-y" in result.command

    def test_apt_install_y_injected(self, ex_dry):
        result = ex_dry.execute_sync(
            "apt install curl", add_sudo=False, check_idempotent=False
        )
        assert "-y" in result.command

    def test_dnf_install_y_injected(self, ex_dry):
        result = ex_dry.execute_sync(
            "dnf install sof-firmware", add_sudo=False, check_idempotent=False
        )
        assert "-y" in result.command

    def test_dnf_upgrade_y_injected(self, ex_dry):
        result = ex_dry.execute_sync(
            "dnf upgrade", add_sudo=False, check_idempotent=False
        )
        assert "-y" in result.command

    def test_apt_get_upgrade_y_injected(self, ex_dry):
        result = ex_dry.execute_sync(
            "apt-get upgrade", add_sudo=False, check_idempotent=False
        )
        assert "-y" in result.command

    def test_already_y_not_duplicated(self, ex_dry):
        result = ex_dry.execute_sync(
            "apt-get install -y curl", add_sudo=False, check_idempotent=False
        )
        assert result.command.count("-y") == 1

    def test_non_pkg_cmd_unchanged(self, ex_dry):
        result = ex_dry.execute_sync(
            "echo hello", add_sudo=False, check_idempotent=False
        )
        assert "-y" not in result.command
        assert result.command == "echo hello"

    def test_sudo_apt_get_y_injected(self, ex_dry):
        result = ex_dry.execute_sync(
            "sudo apt-get install ffmpegthumbnailer",
            add_sudo=False,
            check_idempotent=False,
        )
        assert "-y" in result.command
        assert result.command.startswith("sudo")


class TestSudoLogic:
    """Testy logiki sudo w executor."""

    def test_systemctl_user_no_sudo(self, ex_dry):
        result = ex_dry.execute_sync(
            "systemctl --user restart pipewire",
            add_sudo=True,
            check_idempotent=False,
        )
        assert not result.command.startswith("sudo")

    def test_systemctl_user_start_no_sudo(self, ex_dry):
        result = ex_dry.execute_sync(
            "systemctl --user start pulseaudio",
            add_sudo=True,
            check_idempotent=False,
        )
        assert not result.command.startswith("sudo")

    def test_systemctl_system_gets_sudo(self, ex_dry):
        result = ex_dry.execute_sync(
            "systemctl restart NetworkManager",
            add_sudo=True,
            check_idempotent=False,
        )
        assert result.command.startswith("sudo")

    def test_dnf_gets_sudo(self, ex_dry):
        result = ex_dry.execute_sync(
            "dnf install sof-firmware",
            add_sudo=True,
            check_idempotent=False,
        )
        assert result.command.startswith("sudo")

    def test_echo_no_sudo(self, ex_dry):
        result = ex_dry.execute_sync(
            "echo hello",
            add_sudo=True,
            check_idempotent=False,
        )
        assert not result.command.startswith("sudo")


class TestDangerousCommandBlocking:
    """Testy blokowania niebezpiecznych komend."""

    def test_rm_rf_root_blocked(self, ex_live):
        with pytest.raises(DangerousCommandError):
            ex_live.execute_sync("rm -rf /", add_sudo=False, check_idempotent=False)

    def test_mkfs_blocked(self, ex_live):
        with pytest.raises(DangerousCommandError):
            ex_live.execute_sync("mkfs.ext4 /dev/sda", add_sudo=False, check_idempotent=False)

    def test_wget_pipe_sh_blocked(self, ex_live):
        with pytest.raises(DangerousCommandError):
            ex_live.execute_sync(
                "wget http://example.com/script.sh | bash",
                add_sudo=False,
                check_idempotent=False,
            )

    def test_fork_bomb_blocked(self, ex_live):
        with pytest.raises(DangerousCommandError):
            ex_live.execute_sync(":(){ :|:& };:", add_sudo=False, check_idempotent=False)

    def test_safe_echo_not_blocked(self, ex_live):
        result = ex_live.execute_sync("echo hello", add_sudo=False, check_idempotent=False)
        assert result.executed is True
        assert result.returncode == 0
        assert "hello" in result.stdout


class TestLiveExecution:
    """Testy faktycznego wykonania bezpiecznych komend."""

    def test_echo_executes_correctly(self, ex_live):
        result = ex_live.execute_sync("echo fixos_test", add_sudo=False, check_idempotent=False)
        assert result.ok is True
        assert "fixos_test" in result.stdout
        assert result.returncode == 0

    def test_false_command_returns_nonzero(self, ex_live):
        result = ex_live.execute_sync("false", add_sudo=False, check_idempotent=False)
        assert result.ok is False
        assert result.returncode != 0

    def test_uname_returns_output(self, ex_live):
        result = ex_live.execute_sync("uname -s", add_sudo=False, check_idempotent=False)
        assert result.ok is True
        assert len(result.stdout) > 0

    def test_timeout_handling(self):
        ex = CommandExecutor(default_timeout=1, require_confirmation=False, dry_run=False)
        from fixos.orchestrator.executor import CommandTimeoutError
        with pytest.raises(CommandTimeoutError):
            ex.execute_sync("sleep 5", add_sudo=False, check_idempotent=False)

    def test_nonexistent_command_fails_gracefully(self, ex_live):
        result = ex_live.execute_sync(
            "nonexistent_command_xyz_12345", add_sudo=False, check_idempotent=False
        )
        assert result.ok is False

    def test_stdout_captured(self, ex_live):
        result = ex_live.execute_sync(
            "printf 'line1\\nline2\\nline3'", add_sudo=False, check_idempotent=False
        )
        assert result.ok is True
        assert "line1" in result.stdout
        assert "line2" in result.stdout

    def test_stderr_captured_on_error(self, ex_live):
        result = ex_live.execute_sync(
            "ls /nonexistent_path_xyz_12345", add_sudo=False, check_idempotent=False
        )
        assert result.ok is False
        assert len(result.stderr) > 0


class TestIdempotencyCheck:
    """Testy sprawdzania idempotentności przed wykonaniem."""

    def test_mkdir_skipped_if_exists(self, ex_live):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ex_live.execute_sync(
                f"mkdir -p {tmpdir}", add_sudo=False, check_idempotent=True
            )
            # Katalog już istnieje – powinien być pominięty
            assert result.executed is False
            assert "już wykonane" in result.stdout

    def test_mkdir_executed_if_not_exists(self, ex_live):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "fixos_test_new_dir")
            result = ex_live.execute_sync(
                f"mkdir -p {new_dir}", add_sudo=False, check_idempotent=True
            )
            assert result.executed is True
            assert os.path.isdir(new_dir)
