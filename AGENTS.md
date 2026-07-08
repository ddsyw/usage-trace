# AGENTS.md

usage-trace is a Python CLI that traces a keyword's full usage across a Java/Spring codebase and produces a single offline HTML report. It ships as a Codex plugin and a Claude Code subagent.

## Quick start

```bash
python3 -m pip install -e ".[dev]"
usage-trace --keyword storeNo --root tests/fixtures/java-spring
```

Report lands at `.usage-trace/<keyword>-report.html`.

## Commands

```bash
# tests
python3 -m pytest

# lint
python3 -m ruff check .

# compile check
python3 -m compileall -q src tests

# smoke test
python3 src/usage_trace.py --keyword storeNo --root tests/fixtures/java-spring
```

## Pipeline (src/)

A single `usage-trace` run orchestrates five phases in order:

1. `discover.py` — find keyword usage sites in the target project
2. `trace.py` — build the caller/callee call-chain graph
3. `tables.py` — resolve involved database tables (MyBatis XML, MyBatis annotations, JPA, raw SQL, Java string SQL)
4. `graph.py` — prune and layout the graph (node cap, layer assignment, grouping)
5. `render.py` — emit the offline HTML report from `templates/report.html.tmpl`

`usage_trace.py` is the orchestrator entry point. `common.py` holds shared helpers (profile loading, graph structure). `understand_rules.py` defines the Understand-Anything-style graph rules. Profiles live in `profiles/`.

## Project layout

```
src/                    CLI and analysis phases
profiles/               Java analysis profiles (java-spring.yml, java-generic.yml)
templates/              HTML report template
tests/                  unit tests, e2e tests, and fixture projects
skills/                 Codex skill definition (SKILL.md)
.claude/agents/         Claude Code subagent definition
.codex-plugin/          Codex plugin manifest
plugins/usage-trace/    thin plugin wrapper for marketplace install
.agents/plugins/        repo marketplace manifest
scripts/                install-claude-agent.sh
docs/                   guides
```

## Conventions

- Keep changes scoped to the module being touched; don't refactor unrelated code.
- The report must be a single offline HTML file with no external HTTP assets.
- When editing plugin.json or SKILL.md, update both copies (root `.codex-plugin/` and `plugins/usage-trace/.codex-plugin/`), and keep `skills/usage-trace/SKILL.md` in sync with `plugins/usage-trace/skills/usage-trace/SKILL.md`.
- All description fields should include Chinese trigger keywords (查找字段使用情况, 追踪调用链) so Chinese user queries reliably match the skill.
- `codex-find` is a backwards-compatible alias for `usage-trace`; both map to the same entry point.
