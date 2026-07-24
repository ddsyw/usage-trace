# AGENTS.md

usage-trace is a Python CLI that traces a keyword's full usage across Java/Spring, Python, or C# codebases and produces a single offline HTML report. End users install it as a **Cursor skill**; natural-language prompts like `分析当前项目的 orderId` should auto-load the skill.

## Quick start (dev)

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
profiles/               analysis profiles (java-*, python-*, csharp-*)
templates/              HTML report template
tests/                  unit tests, e2e tests, and fixture projects
skills/                 Cursor skill definition (SKILL.md)
scripts/                maintainer install helpers
docs/                   guides (skill-install.md)
```

## Operations

- **End users:** install the Cursor skill (`~/.cursor/skills/usage-trace/SKILL.md`), then ask in natural language (e.g. `分析当前项目的 orderId`). Skill auto-matches; CLI is installed via pip from GitHub if missing.
- Ops guide: `docs/skill-install.md`.
- Maintainer helpers: `bash scripts/install.sh` (Cursor skill dirs + editable CLI).
- Skill authority: only `skills/usage-trace/SKILL.md` (no plugin copies).

## Conventions

- Keep changes scoped to the module being touched; don't refactor unrelated code.
- The report must be a single offline HTML file with no external HTTP assets.
- No multi-platform plugin packaging; Cursor skill-only distribution.
- Skill description should include Chinese auto-trigger phrases such as `分析当前项目的 orderId`, `查找字段使用情况`, `追踪调用链`.
