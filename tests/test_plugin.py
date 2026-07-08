import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / ".codex-plugin" / "plugin.json"
THIN_PLUGIN_JSON = ROOT / "plugins" / "usage-trace" / ".codex-plugin" / "plugin.json"
MARKETPLACE_JSON = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL = ROOT / "skills" / "usage-trace" / "SKILL.md"
THIN_SKILL = ROOT / "plugins" / "usage-trace" / "skills" / "usage-trace" / "SKILL.md"
README = ROOT / "README.md"
README_CN = ROOT / "README-CN.md"


def test_codex_plugin_manifest_exists_and_points_to_skills():
    manifest = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))

    assert manifest["name"] == "usage-trace"
    assert manifest["version"].startswith("0.1.0")
    assert manifest["skills"] == "./skills/"
    assert manifest["repository"] == "https://github.com/ddsyw/usage-trace"
    assert manifest["interface"]["displayName"] == "usage-trace"
    assert "Trace Java field usage" in manifest["interface"]["shortDescription"]
    assert "usage-trace --keyword orderId" in manifest["interface"]["defaultPrompt"][0]


def test_codex_repo_marketplace_points_to_thin_plugin_directory():
    root_manifest = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    thin_manifest = json.loads(THIN_PLUGIN_JSON.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    entry = marketplace["plugins"][0]

    assert marketplace["name"] == "usage-trace"
    assert marketplace["interface"]["displayName"] == "usage-trace"
    assert entry["name"] == "usage-trace"
    assert entry["version"] == root_manifest["version"]
    assert entry["source"] == {"source": "local", "path": "./plugins/usage-trace"}
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["category"] == root_manifest["interface"]["category"]
    assert thin_manifest["name"] == root_manifest["name"]
    assert thin_manifest["version"] == root_manifest["version"]
    assert thin_manifest["repository"] == root_manifest["repository"]
    assert thin_manifest["skills"] == "./skills/"
    assert THIN_SKILL.read_text(encoding="utf-8") == SKILL.read_text(encoding="utf-8")


def test_usage_trace_skill_exists_with_cli_contract():
    text = SKILL.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "name: usage-trace" in text
    assert "usage-trace --keyword" in text
    assert "--profile auto" in text
    assert "README-CN.md" in text


def test_codex_plugin_docs_use_official_plugins_command():
    for path in (README, README_CN):
        text = path.read_text(encoding="utf-8")

        assert "`/plugins`" in text
        assert "`/plugin`" not in text
