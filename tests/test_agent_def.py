from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent / ".claude" / "agents" / "codex-find.md"


def test_agent_file_exists():
    assert AGENT.exists()


def test_agent_mentions_each_phase_and_tools():
    text = AGENT.read_text(encoding="utf-8")
    for needle in ["discover.py", "trace.py", "tables.py", "graph.py", "render.py",
                   "storeNo", "report.html", "Bash", "Read", "Grep"]:
        assert needle in text, f"agent def missing: {needle}"
