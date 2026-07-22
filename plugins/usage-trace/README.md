# usage-trace plugin (thin wrapper)

Thin multi-platform plugin wrapper used by the repo marketplaces:

| Platform | Marketplace manifest | Plugin manifest |
|----------|----------------------|-----------------|
| Codex | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json` |
| Claude Code | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` |
| Cursor | `.cursor-plugin/marketplace.json` | `.cursor-plugin/plugin.json` |

Installs the **skill** at `skills/usage-trace/SKILL.md` (no Claude Code subagent).
Keep this copy of `SKILL.md` in sync with the repository root
`skills/usage-trace/SKILL.md`.

Plugin manifests under this directory must stay in sync with the matching root
manifests (same `name`, `version`, description, Chinese keywords).

**CLI is separate:** marketplace install only distributes the skill. Users still
need `pip install -e .` (or equivalent) so agents can run `usage-trace`.
