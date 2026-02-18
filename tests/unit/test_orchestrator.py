"""
Testy jednostkowe – Problem Graph, CommandExecutor, FixOrchestrator.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from fixfedora.orchestrator.graph import Problem, ProblemGraph
from fixfedora.orchestrator.executor import (
    CommandExecutor, DangerousCommandError, CommandTimeoutError, ExecutionResult
)


# ══════════════════════════════════════════════════════════
#  Problem + ProblemGraph
# ══════════════════════════════════════════════════════════

class TestProblem:
    def test_is_actionable_pending(self):
        p = Problem(id="p1", description="test", severity="warning", fix_commands=["echo ok"])
        assert p.is_actionable()

    def test_is_actionable_resolved(self):
        p = Problem(id="p1", description="test", severity="warning", fix_commands=[], status="resolved")
        assert not p.is_actionable()

    def test_is_actionable_max_attempts(self):
        p = Problem(id="p1", description="test", severity="warning", fix_commands=[], attempts=3, max_attempts=3)
        assert not p.is_actionable()

    def test_to_summary_keys(self):
        p = Problem(id="p1", description="test", severity="critical", fix_commands=["dnf install x"])
        s = p.to_summary()
        assert s["id"] == "p1"
        assert s["severity"] == "critical"
        assert "fix_commands" in s


class TestProblemGraph:
    def test_add_and_get(self):
        g = ProblemGraph()
        p = Problem(id="p1", description="test", severity="warning", fix_commands=[])
        g.add(p)
        assert g.get("p1") is p

    def test_next_actionable_no_deps(self):
        g = ProblemGraph()
        p = Problem(id="p1", description="test", severity="critical", fix_commands=[])
        g.add(p)
        assert g.next_actionable() is p

    def test_next_actionable_blocked_by_dep(self):
        g = ProblemGraph()
        p1 = Problem(id="p1", description="root", severity="critical", fix_commands=[], status="pending")
        p2 = Problem(id="p2", description="child", severity="warning", fix_commands=[], caused_by=["p1"])
        g.add(p1)
        g.add(p2)
        # p2 jest zablokowane przez p1
        actionable = g.next_actionable()
        assert actionable.id == "p1"

    def test_next_actionable_dep_resolved(self):
        g = ProblemGraph()
        p1 = Problem(id="p1", description="root", severity="critical", fix_commands=[], status="resolved")
        p2 = Problem(id="p2", description="child", severity="warning", fix_commands=[], caused_by=["p1"])
        g.add(p1)
        g.add(p2)
        actionable = g.next_actionable()
        assert actionable.id == "p2"

    def test_all_done_when_all_resolved(self):
        g = ProblemGraph()
        g.add(Problem(id="p1", description="a", severity="info", fix_commands=[], status="resolved"))
        g.add(Problem(id="p2", description="b", severity="info", fix_commands=[], status="failed"))
        assert g.all_done()

    def test_all_done_false_when_pending(self):
        g = ProblemGraph()
        g.add(Problem(id="p1", description="a", severity="info", fix_commands=[], status="pending"))
        assert not g.all_done()

    def test_pending_count(self):
        g = ProblemGraph()
        g.add(Problem(id="p1", description="a", severity="info", fix_commands=[], status="pending"))
        g.add(Problem(id="p2", description="b", severity="info", fix_commands=[], status="resolved"))
        assert g.pending_count() == 1

    def test_render_tree_not_empty(self):
        g = ProblemGraph()
        g.add(Problem(id="p1", description="Brak dźwięku", severity="critical", fix_commands=[]))
        tree = g.render_tree()
        assert "p1" in tree
        assert "Brak dźwięku" in tree
        assert "🔴" in tree

    def test_topological_order_critical_first(self):
        g = ProblemGraph()
        g.add(Problem(id="p_info", description="info", severity="info", fix_commands=[]))
        g.add(Problem(id="p_crit", description="critical", severity="critical", fix_commands=[]))
        g.add(Problem(id="p_warn", description="warning", severity="warning", fix_commands=[]))
        # critical powinno być pierwsze
        assert g.execution_order[0] == "p_crit"

    def test_child_linked_to_parent(self):
        g = ProblemGraph()
        parent = Problem(id="p1", description="parent", severity="critical", fix_commands=[], status="resolved")
        child = Problem(id="p2", description="child", severity="warning", fix_commands=[], caused_by=["p1"])
        g.add(parent)
        g.add(child)
        assert "p1" in child.caused_by


# ══════════════════════════════════════════════════════════
#  CommandExecutor
# ══════════════════════════════════════════════════════════

class TestCommandExecutor:
    def test_is_dangerous_rm_rf_root(self):
        ex = CommandExecutor()
        dangerous, reason = ex.is_dangerous("rm -rf /")
        assert dangerous
        assert reason

    def test_is_dangerous_safe_command(self):
        ex = CommandExecutor()
        dangerous, _ = ex.is_dangerous("dnf install sof-firmware")
        assert not dangerous

    def test_is_dangerous_dd_disk(self):
        ex = CommandExecutor()
        dangerous, _ = ex.is_dangerous("dd if=/dev/zero of=/dev/sda")
        assert dangerous

    def test_is_dangerous_fork_bomb(self):
        ex = CommandExecutor()
        dangerous, _ = ex.is_dangerous(":(){ :|:& };:")
        assert dangerous

    def test_needs_sudo_dnf(self):
        ex = CommandExecutor()
        assert ex.needs_sudo("dnf install x")

    def test_needs_sudo_systemctl(self):
        ex = CommandExecutor()
        assert ex.needs_sudo("systemctl restart pipewire")

    def test_needs_sudo_already_has_sudo(self):
        ex = CommandExecutor()
        assert not ex.needs_sudo("sudo dnf install x")

    def test_needs_sudo_echo(self):
        ex = CommandExecutor()
        assert not ex.needs_sudo("echo hello")

    def test_add_sudo(self):
        ex = CommandExecutor()
        assert ex.add_sudo("dnf install x") == "sudo dnf install x"
        assert ex.add_sudo("echo hello") == "echo hello"
        assert ex.add_sudo("sudo dnf install x") == "sudo dnf install x"

    def test_dry_run_returns_preview(self):
        ex = CommandExecutor(dry_run=True)
        result = ex.execute_sync("echo hello", add_sudo=False, check_idempotent=False)
        assert not result.executed
        assert "DRY-RUN" in result.preview

    def test_execute_sync_safe_command(self):
        ex = CommandExecutor(dry_run=False)
        result = ex.execute_sync("echo hello_fixfedora", add_sudo=False, check_idempotent=False)
        assert result.executed
        assert result.success
        assert "hello_fixfedora" in result.stdout

    def test_execute_sync_raises_on_dangerous(self):
        ex = CommandExecutor(dry_run=False)
        with pytest.raises(DangerousCommandError):
            ex.execute_sync("rm -rf /", add_sudo=False, check_idempotent=False)

    def test_execution_result_success(self):
        r = ExecutionResult(command="echo", returncode=0, stdout="ok", executed=True)
        assert r.success

    def test_execution_result_failure(self):
        r = ExecutionResult(command="false", returncode=1, executed=True)
        assert not r.success

    def test_execution_result_not_executed(self):
        r = ExecutionResult(command="echo", returncode=0, executed=False)
        assert not r.success

    def test_to_context_keys(self):
        r = ExecutionResult(command="echo ok", returncode=0, stdout="ok", executed=True)
        ctx = r.to_context()
        assert "command" in ctx
        assert "returncode" in ctx
        assert "success" in ctx


# ══════════════════════════════════════════════════════════
#  FixOrchestrator (z mock LLM)
# ══════════════════════════════════════════════════════════

class TestFixOrchestrator:
    @pytest.fixture
    def mock_cfg(self):
        from fixfedora.config import FixFedoraConfig
        return FixFedoraConfig(
            provider="gemini",
            api_key="AIzaSy_FAKE_TOKEN_FOR_TESTING_1234567890",
            model="gemini-2.5-flash-preview-04-17",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            agent_mode="hitl",
            session_timeout=60,
            show_anonymized_data=False,
            enable_web_search=False,
        )

    def test_load_from_dict(self, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator
        orch = FixOrchestrator(config=mock_cfg)
        problems = orch.load_from_dict([
            {"id": "p1", "description": "Brak SOF firmware", "severity": "critical",
             "fix_commands": ["sudo dnf install sof-firmware"]},
            {"id": "p2", "description": "PipeWire failed", "severity": "warning",
             "fix_commands": ["systemctl --user restart pipewire"]},
        ])
        assert len(problems) == 2
        assert orch.graph.get("p1") is not None
        assert orch.graph.get("p2") is not None

    def test_graph_render_after_load(self, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator
        orch = FixOrchestrator(config=mock_cfg)
        orch.load_from_dict([
            {"id": "p1", "description": "Brak dźwięku", "severity": "critical",
             "fix_commands": ["sudo dnf install sof-firmware"]},
        ])
        tree = orch.graph.render_tree()
        assert "p1" in tree
        assert "Brak dźwięku" in tree

    def test_run_sync_dry_run_no_confirm(self, mock_cfg):
        """Dry-run nie wymaga potwierdzenia i nie wykonuje komend."""
        from fixfedora.orchestrator import FixOrchestrator
        from fixfedora.orchestrator.executor import CommandExecutor

        executor = CommandExecutor(dry_run=True)
        orch = FixOrchestrator(config=mock_cfg, executor=executor)
        orch.load_from_dict([
            {"id": "p1", "description": "test", "severity": "info",
             "fix_commands": ["echo test"]},
        ])

        # W dry-run: auto-confirm, LLM evaluate mockujemy
        with patch.object(orch, "_evaluate_and_rediagnose", return_value=[]) as mock_eval:
            # Ustaw problem jako resolved po wykonaniu
            def fake_eval(problem, result):
                problem.status = "resolved"
                return []
            mock_eval.side_effect = fake_eval

            summary = orch.run_sync(confirm_fn=lambda p, c: True)

        assert summary["total"] == 1

    @patch("fixfedora.providers.llm.openai")
    def test_load_from_diagnostics_mock_llm(self, mock_openai, mock_cfg):
        """load_from_diagnostics parsuje JSON z LLM."""
        from fixfedora.orchestrator import FixOrchestrator

        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = """{
  "new_problems": [
    {
      "id": "p_sof",
      "description": "Brak sof-firmware",
      "severity": "critical",
      "fix_commands": ["sudo dnf install sof-firmware"],
      "related_to": []
    }
  ],
  "explanation": "SOF firmware missing"
}"""
        mock_resp.usage.total_tokens = 100
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_resp

        orch = FixOrchestrator(config=mock_cfg)
        problems = orch.load_from_diagnostics({"system": {"os_release": "Fedora 40"}})

        assert len(problems) == 1
        assert problems[0].id == "p_sof"
        assert problems[0].severity == "critical"

    def test_parse_json_clean(self, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator
        orch = FixOrchestrator(config=mock_cfg)
        data = orch._parse_json('{"key": "value"}')
        assert data["key"] == "value"

    def test_parse_json_with_markdown_fence(self, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator
        orch = FixOrchestrator(config=mock_cfg)
        raw = "```json\n{\"key\": \"value\"}\n```"
        data = orch._parse_json(raw)
        assert data["key"] == "value"

    def test_parse_json_invalid_raises(self, mock_cfg):
        from fixfedora.orchestrator import FixOrchestrator
        orch = FixOrchestrator(config=mock_cfg)
        with pytest.raises(ValueError):
            orch._parse_json("not json at all")
