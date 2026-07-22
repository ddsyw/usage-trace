# Deprecated: Claude Code Agent

`usage-trace` is packaged as a **skill + CLI**, not a Claude Code subagent.

See **[skill-install.md](./skill-install.md)** for the full operations guide
(CLI install, skill install, marketplace plugins, FAQ).

The historical agent definition at `.claude/agents/usage-trace.md` has been
removed. Use:

```bash
# 1) CLI (required)
python3 -m pip install -e .

# 2) skill (optional, for assistants)
bash scripts/install-skill.sh user
# or
bash scripts/install-skill.sh project .

# 3) optional Claude Code marketplace plugin (skill only)
# /plugin marketplace add ddsyw/usage-trace
# /plugin install usage-trace@usage-trace
```
