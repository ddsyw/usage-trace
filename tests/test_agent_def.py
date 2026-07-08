from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent / ".claude" / "agents" / "usage-trace.md"
DOC = Path(__file__).resolve().parent.parent / "docs" / "claude-code-agent.md"
INSTALLER = Path(__file__).resolve().parent.parent / "scripts" / "install-claude-agent.sh"


def test_agent_file_exists():
    assert AGENT.exists()


def test_agent_mentions_each_phase_and_tools():
    text = AGENT.read_text(encoding="utf-8")
    for needle in ["discover.py", "trace.py", "tables.py", "graph.py", "render.py",
                   "storeNo", "report.html", "Bash", "Read", "Grep"]:
        assert needle in text, f"agent def missing: {needle}"


def test_agent_prefers_installed_cli_for_target_projects():
    text = AGENT.read_text(encoding="utf-8")
    assert "usage-trace --keyword" in text
    assert "--profile auto" in text
    assert "python src/usage_trace.py --keyword" not in text


def test_claude_code_install_doc_exists():
    text = DOC.read_text(encoding="utf-8")
    for needle in [
        ".claude/agents",
        "~/.claude/agents",
        "usage-trace --keyword orderId --root .",
        "open .usage-trace/orderId-report.html",
    ]:
        assert needle in text, f"Claude Code doc missing: {needle}"


def test_claude_code_installer_exists():
    text = INSTALLER.read_text(encoding="utf-8")
    for needle in ["project", "user", ".claude/agents", "usage-trace.md"]:
        assert needle in text, f"installer missing: {needle}"
