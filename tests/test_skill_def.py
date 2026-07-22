import json
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


PLUGIN_MANIFESTS = [
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / "plugins" / "usage-trace" / ".codex-plugin" / "plugin.json",
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / "plugins" / "usage-trace" / ".claude-plugin" / "plugin.json",
    ROOT / ".cursor-plugin" / "plugin.json",
    ROOT / "plugins" / "usage-trace" / ".cursor-plugin" / "plugin.json",
]

MARKETPLACES = [
    ROOT / ".agents" / "plugins" / "marketplace.json",
    ROOT / ".claude-plugin" / "marketplace.json",
    ROOT / ".cursor-plugin" / "marketplace.json",
]


def test_plugin_manifests_exist_and_share_version():
    versions = set()
    for path in PLUGIN_MANIFESTS:
        assert path.is_file(), f"missing plugin manifest: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("name") == "usage-trace"
        assert data.get("version"), f"missing version in {path}"
        versions.add(data["version"])
        blob = json.dumps(data, ensure_ascii=False)
        assert "查找字段使用情况" in blob or "字段使用情况" in blob or "追踪调用链" in blob
    assert len(versions) == 1, f"plugin versions diverged: {versions}"


def test_marketplaces_point_at_thin_plugin():
    for path in MARKETPLACES:
        assert path.is_file(), f"missing marketplace: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = json.dumps(data, ensure_ascii=False)
        assert "plugins/usage-trace" in raw or "./plugins/usage-trace" in raw


def test_paired_plugin_manifests_stay_in_sync():
    pairs = [
        (ROOT / ".codex-plugin" / "plugin.json", ROOT / "plugins" / "usage-trace" / ".codex-plugin" / "plugin.json"),
        (ROOT / ".claude-plugin" / "plugin.json", ROOT / "plugins" / "usage-trace" / ".claude-plugin" / "plugin.json"),
        (ROOT / ".cursor-plugin" / "plugin.json", ROOT / "plugins" / "usage-trace" / ".cursor-plugin" / "plugin.json"),
    ]
    for root_path, thin_path in pairs:
        root = json.loads(root_path.read_text(encoding="utf-8"))
        thin = json.loads(thin_path.read_text(encoding="utf-8"))
        assert root["name"] == thin["name"]
        assert root["version"] == thin["version"]
        assert root["description"] == thin["description"]
