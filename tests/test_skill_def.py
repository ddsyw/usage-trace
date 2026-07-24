from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "usage-trace" / "SKILL.md"
DOC = ROOT / "docs" / "skill-install.md"
INSTALLER = ROOT / "scripts" / "install-skill.sh"
AGENT_LEGACY = ROOT / ".claude" / "agents" / "usage-trace.md"
LEGACY_INSTALLER = ROOT / "scripts" / "install-claude-agent.sh"
LEGACY_DOC = ROOT / "docs" / "claude-code-agent.md"


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
        "分析当前项目的 orderId",
        "git+https://github.com/ddsyw/usage-trace.git",
        "Cursor",
    ]:
        assert needle in text, f"skill missing: {needle}"
    assert "Codex / Claude Code / Cursor" not in text
    assert "Claude Code" not in text
    assert "Plugin packaging is not required" in text or "plugin packaging is not required" in text.lower()


def test_skill_install_doc_exists():
    text = DOC.read_text(encoding="utf-8")
    for needle in [
        "Cursor",
        "~/.cursor/skills/usage-trace",
        "分析当前项目的 orderId",
        "usage-trace --keyword orderId --root .",
        "git+https://github.com/ddsyw/usage-trace.git",
        "skill",
    ]:
        assert needle in text, f"skill install doc missing: {needle}"
    assert "codex plugin" not in text
    assert "Claude Code" not in text
    assert "install-claude-agent" not in text
    assert "~/.cursor/plugins/local" not in text


def test_skill_installer_exists():
    text = INSTALLER.read_text(encoding="utf-8")
    for needle in [
        "user",
        "project",
        "cursor-user",
        "SKILL.md",
        "skills/usage-trace",
        "--symlink",
        "--copy",
        "--skip-cli",
        "pip install -e",
        ".cursor/skills",
    ]:
        assert needle in text, f"installer missing: {needle}"
    assert "codex-user" not in text
    assert "claude-user" not in text


def test_legacy_agent_artifacts_removed():
    assert not LEGACY_INSTALLER.exists()
    assert not LEGACY_DOC.exists()
    assert not AGENT_LEGACY.exists(), "subagent definition should be removed; use skill only"


def test_plugin_packaging_removed():
    for path in [
        ROOT / ".cursor-plugin",
        ROOT / ".codex-plugin",
        ROOT / ".claude-plugin",
        ROOT / ".agents" / "plugins",
        ROOT / "plugins",
        ROOT / "scripts" / "sync-plugin-copies.sh",
    ]:
        assert not path.exists(), f"expected removed packaging path still present: {path}"
