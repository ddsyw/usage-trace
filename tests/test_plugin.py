import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / ".codex-plugin" / "plugin.json"
SKILL = ROOT / "skills" / "usage-trace" / "SKILL.md"


def test_codex_plugin_manifest_exists_and_points_to_skills():
    manifest = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))

    assert manifest["name"] == "usage-trace"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["repository"] == "https://github.com/ddsyw/usage-trace"
    assert manifest["interface"]["displayName"] == "usage-trace"
    assert "Trace Java field usage" in manifest["interface"]["shortDescription"]
    assert "usage-trace --keyword orderId" in manifest["interface"]["defaultPrompt"][0]


def test_usage_trace_skill_exists_with_cli_contract():
    text = SKILL.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "name: usage-trace" in text
    assert "usage-trace --keyword" in text
    assert "--profile auto" in text
    assert "README-CN.md" in text
