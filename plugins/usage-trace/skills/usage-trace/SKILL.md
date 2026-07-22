---
name: usage-trace
description: Trace keyword usage, call chains, and DB tables in Java/Spring, Python (SQLAlchemy), or C# (EF Core) with the local usage-trace CLI and produce an offline HTML report. Use when the user asks to find a field's usage, trace a call chain, or identify involved DB tables. Supports Chinese queries like 查找字段使用情况, 追踪调用链, 字段流向分析, 查找字段项目使用情况.
---

# usage-trace

Skill for keyword usage analysis across Java, Python, and C#. Prefer this skill (not a subagent) whenever the user wants to find where a field/identifier is used, how it flows through the project, or which database tables it touches.

Typical keywords: `orderId`, `storeNo`, `store_no`, `userId`, and similar business fields.

## What It Does

Runs the local `usage-trace` CLI against a project and writes **one offline HTML report** with:

- matched usage sites (with naming variants)
- caller/callee call chain
- involved database tables (when resolvable for the language/ORM)
- interactive graph dashboard (layer columns → class groups → methods)
- table / statement diagnostics and SQL snippets when resolvable

Supported:

- Java/Spring (`java-spring`) and plain Java (`java-generic`)
- Python SQLAlchemy (`python-sqlalchemy`) and plain Python (`python-generic`)
- C# EF Core (`csharp-ef`) and plain C# (`csharp-generic`)

`--profile auto` picks a profile from project markers and source content.

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `keyword` | yes | — | field / identifier, e.g. `orderId`, `store_no` |
| `root` | yes | current project when user says so | project root (Java/Python/C# markers or sources) |
| `output` | no | `.usage-trace/<keyword>-report.html` | relative to cwd |
| `depth` | no | `4` | hard-capped in CLI |
| `profile` | no | `auto` | see supported profiles above |
| `max-nodes` | no | `300` | graph node cap |

## Preferred Command

If `usage-trace` is on `PATH`:

```bash
usage-trace --keyword "<keyword>" --root "<target>" --profile auto --depth 4
```

Example:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4
```

If the CLI is not installed, run from the plugin or repository root:

```bash
python3 src/usage_trace.py --keyword "<keyword>" --root "<target>" --profile auto --depth 4
```

Missing deps:

```bash
python3 -m pip install -e .
# or: bash scripts/install.sh
```

Optional output path:

```bash
usage-trace --keyword orderId --root . --out .usage-trace/orderId-report.html
```

## Workflow

1. Extract `keyword` and target `root` from the user request.
2. Default report path: `.usage-trace/<keyword>-report.html` unless the user asks otherwise.
3. Run `usage-trace --keyword ... --root ... --profile auto --depth 4`.
4. Confirm the HTML file exists.
5. Summarize for the user:
   - major usage sites
   - main call-chain path (entry → service → repository/data → table when present)
   - involved tables / SQL when present
6. If the CLI is missing, install with `pip install -e .` (or `bash scripts/install.sh`) and retry.

## Notes

- Analysis is **local CLI**; this skill only tells the agent how to invoke it.
- Report is a **single offline HTML** (no external HTTP assets).
- Chinese triggers: 查找字段使用情况, 追踪调用链, 字段流向, 涉及哪些表.
- Also available as Codex / Claude Code / Cursor marketplace plugins shipping this skill.

## Install references

- Unified: `bash scripts/install.sh`
- Skill only: `bash scripts/install-skill.sh user`
- Ops guide: `docs/skill-install.md`

## Docs

- English: `README.md`
- Chinese: `README-CN.md`
- Ops: `docs/skill-install.md`
