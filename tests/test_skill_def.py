from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "usage-trace" / "SKILL.md"
THIN_SKILL = ROOT / "plugins" / "usage-trace" / "skills" / "usage-trace" / "SKILL.md"
DOC = ROOT / "docs" / "skill-install.md"
INSTALLER = ROOT / "scripts" / "install-skill.sh"
LEGACY_INSTALLER = ROOT / "scripts" / "install-claude-agent.sh"
AGENT_LEGACY = ROOT / ".claude" / "agents" / "usage-trace.md"


def test_skill_file_exists_with_frontmatter():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: usage-trace" in text
    assert "查找字段使用情况" in text or "追踪调用链" in text


def test_skill_mentions_cli_and_workflow():
    text = SKILL.read_text(encoding="utf-8")
    for needle in [
        "usage-trace --keyword",
        "--profile auto",
        ".usage-trace/",
        "report.html",
        "Workflow",
    ]:
        assert needle in text, f"skill missing: {needle}"


def test_skill_copies_stay_in_sync():
    assert SKILL.read_text(encoding="utf-8") == THIN_SKILL.read_text(encoding="utf-8")


def test_skill_install_doc_exists():
    text = DOC.read_text(encoding="utf-8")
    for needle in [
        "install-skill.sh",
        "~/.claude/skills",
        "usage-trace --keyword orderId --root .",
        "skill",
    ]:
        assert needle in text, f"skill install doc missing: {needle}"


def test_skill_installer_exists():
    text = INSTALLER.read_text(encoding="utf-8")
    for needle in ["user", "project", "codex-user", "SKILL.md", "skills/usage-trace"]:
        assert needle in text, f"installer missing: {needle}"


def test_legacy_agent_installer_redirects_to_skill():
    text = LEGACY_INSTALLER.read_text(encoding="utf-8")
    assert "install-skill.sh" in text
    assert "deprecated" in text.lower()


def test_no_claude_subagent_definition():
    assert not AGENT_LEGACY.exists(), "subagent definition should be removed; use skill only"
