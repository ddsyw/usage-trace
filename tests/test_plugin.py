from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "usage-trace" / "SKILL.md"
README = ROOT / "README.md"
README_CN = ROOT / "README-CN.md"
DOC = ROOT / "docs" / "skill-install.md"


def test_skill_exists_with_cli_contract():
    text = SKILL.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "name: usage-trace" in text
    assert "usage-trace --keyword" in text
    assert "--profile auto" in text
    assert "README-CN.md" in text
    assert "Cursor" in text


def test_docs_are_cursor_skill_only():
    for path in (README, README_CN, DOC):
        text = path.read_text(encoding="utf-8")
        assert "Cursor" in text or "cursor" in text
        assert "~/.cursor/skills/usage-trace" in text or ".cursor\\skills\\usage-trace" in text
        assert "codex plugin" not in text
        assert "Claude Code" not in text
        assert "/plugin marketplace add" not in text
        assert "~/.cursor/plugins/local" not in text


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
