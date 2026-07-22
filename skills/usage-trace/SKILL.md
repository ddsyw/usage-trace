---
name: usage-trace
description: >
  Trace a field/identifier through the current project and produce an offline HTML
  report (usage sites, call chain, related DB tables). ALWAYS use this skill when the
  user asks to analyze a keyword/field in a project — including short prompts like
  "分析当前项目的 orderId", "分析 orderId", "查找 orderId 使用情况", "追踪 storeNo 调用链",
  "orderId 涉及哪些表", "trace storeNo", "find field usage", "where is userId used",
  or similar Chinese/English requests about 字段使用情况 / 调用链 / 字段流向 / 数据库表.
  Supports Java/Spring, Python (SQLAlchemy), and C# (EF Core).
---

# usage-trace

Use this skill whenever the user wants field/identifier usage analysis. Prefer it
automatically for short natural-language requests such as:

- `分析当前项目的 orderId`
- `查找 storeNo 字段项目使用情况`
- `追踪 userId 的调用链和涉及的数据库表`
- `Trace orderId usage and tables in this repo`

Do **not** wait for the user to mention "usage-trace" or "skill" by name.

Typical keywords: `orderId`, `storeNo`, `store_no`, `userId`, and similar business fields.

## What It Does

Runs the local `usage-trace` CLI against a project and writes **one offline HTML report** with:

- matched usage sites (with naming variants)
- caller/callee call chain
- involved database tables (when resolvable for the language/ORM)
- interactive graph dashboard (layer columns → class groups → methods)
- table / statement diagnostics and SQL snippets when resolvable

Supported profiles:

- Java/Spring (`java-spring`) and plain Java (`java-generic`)
- Python SQLAlchemy (`python-sqlalchemy`) and plain Python (`python-generic`)
- C# EF Core (`csharp-ef`) and plain C# (`csharp-generic`)

`--profile auto` picks a profile from project markers and source content.

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `keyword` | yes | — | field / identifier extracted from the user message, e.g. `orderId` |
| `root` | yes | `.` when the user says current project / 当前项目 | project root |
| `output` | no | `.usage-trace/<keyword>-report.html` | relative to cwd |
| `depth` | no | `4` | hard-capped in CLI |
| `profile` | no | `auto` | see supported profiles above |
| `max-nodes` | no | `300` | graph node cap |

## Ensure CLI is available

The skill is distributed by Codex / Claude Code / Cursor **plugins**. The analysis
engine is the local `usage-trace` command. Before the first run in a session, ensure
the CLI works:

```bash
usage-trace --help
```

If the command is missing, install once from GitHub (no local clone / install script required):

```bash
python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
```

Verify again with `usage-trace --help`. Prefer the same Python/environment the agent shell uses.

Fallback if the console script is still not on `PATH` after install:

```bash
python3 -m usage_trace --keyword "<keyword>" --root "<target>" --profile auto --depth 4
```

(If `python3 -m usage_trace` is unavailable, use `python3 -c "from usage_trace import main; raise SystemExit(main())"` only as a last resort, or re-check the pip install.)

## Preferred Command

```bash
usage-trace --keyword "<keyword>" --root "<target>" --profile auto --depth 4
```

Examples:

```bash
# User: 分析当前项目的 orderId
usage-trace --keyword orderId --root . --profile auto --depth 4

# User: Trace storeNo and related tables
usage-trace --keyword storeNo --root . --profile auto --depth 4
```

Optional output path:

```bash
usage-trace --keyword orderId --root . --out .usage-trace/orderId-report.html
```

## Workflow

1. Detect that this skill applies (field/usage/call-chain/table analysis intent).
2. Extract `keyword` from the user request (e.g. `orderId` from `分析当前项目的 orderId`).
3. Set `root` to `.` when the user says current project / 当前项目 / this repo; otherwise use the path they give.
4. Ensure the CLI is available (section above).
5. Run `usage-trace --keyword ... --root ... --profile auto --depth 4`.
6. Confirm the HTML report exists (default `.usage-trace/<keyword>-report.html`).
7. Summarize for the user:
   - major usage sites
   - main call-chain path (entry → service → repository/data → table when present)
   - involved tables / SQL when present
   - report file path

## Notes

- Install path for end users: marketplace / plugin install in Codex, Claude Code, or Cursor.
- Report is a **single offline HTML** (no external HTTP assets).
- Chinese triggers: 分析当前项目, 查找字段使用情况, 追踪调用链, 字段流向, 涉及哪些表.
- Compatibility command: `codex-find` is an alias of `usage-trace`.

## Docs

- English: `README.md`
- Chinese: `README-CN.md`
- Ops: `docs/skill-install.md`