# usage-trace

[中文文档](README-CN.md)

`usage-trace` is a coding-agent **plugin + skill** for tracing a field or
identifier through Java, Python, or C# codebases. After installing the plugin in
Codex / Claude Code / Cursor, ask naturally:

```text
分析当前项目的 orderId
```

The skill auto-matches, ensures the local CLI is available, and writes a single
offline HTML report covering usage sites, call chains, and related database tables.

## Features

- Search keyword usages with generated naming variants.
- Build a caller/callee graph around matched methods.
- Classify layers such as Controller, Service, Repository, Entity, SQL, Table,
  and package/path-based layers.
- Resolve database table access from language-specific sources (MyBatis, JPA,
  SQLAlchemy, EF Core, raw SQL, string SQL, and more).
- Render a single self-contained offline HTML report.
- Marketplace plugins for Codex / Claude Code / Cursor with auto skill matching.
- Support Java, Python, and C# through `--profile auto`.
- Keep `codex-find` as a compatibility command while using `usage-trace` as the
  primary name.

## Install (plugin only)

### Codex

```bash
codex plugin marketplace add ddsyw/usage-trace --ref main
codex plugin add usage-trace@usage-trace
```

Or open `/plugins` in Codex and install from the `usage-trace` marketplace.

### Claude Code

```text
/plugin marketplace add ddsyw/usage-trace
/plugin install usage-trace@usage-trace
```

### Cursor

Local plugin install (recommended today):

**Windows PowerShell** (from this repository root):

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\plugins\local\usage-trace" | Out-Null
Copy-Item -Recurse -Force ".\plugins\usage-trace\*" "$env:USERPROFILE\.cursor\plugins\local\usage-trace\"
```

**macOS / Linux / Git Bash**:

```bash
mkdir -p ~/.cursor/plugins/local/usage-trace
cp -R plugins/usage-trace/. ~/.cursor/plugins/local/usage-trace/
```

Confirm:

```text
~/.cursor/plugins/local/usage-trace/.cursor-plugin/plugin.json
~/.cursor/plugins/local/usage-trace/skills/usage-trace/SKILL.md
```

Or follow Cursor Marketplace submission docs for the packaged plugin.

## Use (auto skill trigger)

In the target project, ask in plain language — no need to name the skill:

```text
分析当前项目的 orderId
```

```text
查找 storeNo 字段项目使用情况，生成报告并总结调用链和表
```

```text
Trace userId usage, call chain, and related tables
```

The agent should:

1. Load the `usage-trace` skill automatically
2. If `usage-trace` is missing, install the CLI once:
   ```bash
   python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
   ```
3. Run:
   ```bash
   usage-trace --keyword orderId --root . --profile auto --depth 4
   ```
4. Summarize `.usage-trace/orderId-report.html`

## What the agent runs (CLI reference)

```bash
usage-trace --keyword <identifier> --root <project> [options]
```

- `--keyword`: required keyword or field name, for example `orderId`.
- `--root`: required target project root (`.` for current project).
- `--profile`: language profile. Default is `auto`; profiles include
  `java-spring`, `java-generic`, `python-sqlalchemy`, `python-generic`,
  `csharp-ef`, `csharp-generic`.
- `--depth`: call-chain depth. Default is `4`; the code applies a hard cap.
- `--max-nodes`: maximum graph nodes rendered in the report. Default is `300`.
- `--variants`: comma-separated extra keyword variants to search.
- `--out`: optional output HTML path. Default is `.usage-trace/<keyword>-report.html`
  in the current directory.

Compatibility command:

```bash
codex-find --keyword orderId --root /path/to/your/project
```

## Report contents

The generated HTML report includes:

- a summary of matched usage counts and table counts
- an interactive layered call-chain dashboard with a default main-path view,
  left-side layer tabs, group frames, search, pan, zoom, and click-to-focus
  neighborhood highlighting
- Understand-Anything-style graph metadata: node type, complexity, tags,
  weighted edges, architecture layers, guided tour steps, and cross-layer
  relationship aggregation
- a collapsed network overview
- usage-site details with file, line, layer, hit type, and snippets
- database table details with operation type, source unit, source file,
  statement id, and SQL snippets
- MyBatis XML / SQL source diagnostics when present
- truncation notes and inferred-edge notes

The report is a single offline HTML file with no external HTTP assets.

## Support matrix

- Java/Spring:
  - keyword usage tracing
  - controller/service/repository/entity layer classification
  - MyBatis XML and annotation SQL
  - JPA repository/entity table mappings
  - raw SQL files and Java SQL string literals
- Plain Java:
  - keyword usage tracing
  - call-chain graph
  - package/path-based layer classification
  - MyBatis XML mapper SQL
  - raw SQL files and Java SQL string literals
- Python (SQLAlchemy / generic):
  - keyword usage + call-chain tracing (tree-sitter-python)
  - `__tablename__` / `Table()` and SQL string table hints
- C# (EF Core / generic):
  - keyword usage + call-chain tracing (tree-sitter-c-sharp)
  - `[Table]` / `ToTable` / `DbSet` and SQL string table hints

## Debug pipeline

The single `usage-trace` command orchestrates these phases:

1. `src/discover.py`: discover keyword usage sites
2. `src/trace.py`: build the call graph
3. `src/tables.py`: resolve database tables
4. `src/graph.py`: prune and layout graph nodes
5. `src/render.py`: render the offline HTML report

These scripts remain available for debugging individual phases.

## Development

```bash
git clone https://github.com/ddsyw/usage-trace.git
cd usage-trace
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m ruff check .
python3 -m compileall -q src tests
```

Smoke test:

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring
```

Maintainer helpers (not required for end users):

```bash
bash scripts/install.sh          # local skill dirs + editable CLI
bash scripts/install.sh sync     # sync thin plugin SKILL.md
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Project layout

```text
.agents/plugins/marketplace.json   Codex repo marketplace
.codex-plugin/plugin.json          Root Codex plugin manifest
.claude-plugin/                    Claude Code plugin + marketplace
.cursor-plugin/                    Cursor plugin + marketplace
docs/skill-install.md              Plugin install and usage guide
plugins/usage-trace/               Thin multi-platform plugin wrapper
profiles/                          analysis profiles (java/python/csharp)
scripts/                           Maintainer install/sync scripts
skills/usage-trace/SKILL.md        Skill definition (synced into plugin)
src/                               CLI and analysis phases
templates/report.html.tmpl         offline report template
tests/                             Unit, integration, and fixture tests
```

## Limitations

- The call graph is static and heuristic; reflection, runtime proxies, dynamic
  SQL generation, and complex dependency injection may require manual review.
- Very large projects may need a lower `--max-nodes` value or narrower keyword
  variants to keep reports readable.