# usage-trace plugin (thin wrapper)

Thin multi-platform plugin wrapper used by the repo marketplaces:

| Platform | Marketplace manifest | Plugin manifest |
|----------|----------------------|-----------------|
| Codex | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json` |
| Claude Code | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` |
| Cursor | `.cursor-plugin/marketplace.json` | `.cursor-plugin/plugin.json` |

Ships the **skill** at `skills/usage-trace/SKILL.md`.
Keep this copy in sync with repository root `skills/usage-trace/SKILL.md`.

### End-user install

Install this plugin from the marketplace in Codex / Claude Code, or copy this directory to
`~/.cursor/plugins/local/usage-trace` for Cursor (see `docs/skill-install.md`), then ask:

```text
分析当前项目的 orderId
```

The skill auto-matches natural-language analysis requests. If the local CLI is
missing, the skill tells the agent to:

```bash
python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
```

### Maintainer notes

Plugin manifests under this directory must stay in sync with root manifests
(same `name`, `version`, description, Chinese keywords).