# usage-trace

[中文文档](README-CN.md)

`usage-trace` is a local code-analysis CLI and coding-agent **skill** for tracing a
field or identifier through a Java codebase. Given a keyword such as `orderId` or
`storeNo`, it produces a single offline HTML report covering usage sites, call
chains, and related database tables.

The project is designed for day-to-day codebase investigation: when you need to
answer "where is this field used, what path does it flow through, and which table
does it touch?"

## Features

- Search keyword usages across Java projects with generated keyword variants.
- Build a caller/callee graph around matched methods.
- Classify layers such as Controller, Service, Repository, Entity, SQL, Table,
  and plain Java package-based layers.
- Resolve database table access from:
  - MyBatis XML mapper SQL
  - MyBatis annotation SQL
  - JPA repository/entity mappings
  - raw SQL files
  - Java SQL string literals
- Render a single self-contained offline HTML report.
- Ship as a skill (Codex / Claude Code / Cursor marketplace plugins + skill install) so agents run the CLI on demand.
- Support both Spring and non-Spring Java projects through `--profile auto`.
- Keep `codex-find` as a compatibility command while using `usage-trace` as the
  primary project name.

## Repository

```bash
git clone https://github.com/ddsyw/usage-trace.git
cd usage-trace
```

## Requirements

- Python 3.10+
- `pip`
- `rg` / ripgrep is recommended for faster search. If it is unavailable, the
  tool falls back to a Python search implementation.

Install dependencies in editable mode:

```bash
python3 -m pip install -e ".[dev]"
```

## Quick Start

Run against the included Spring fixture:

```bash
usage-trace \
  --keyword storeNo \
  --root tests/fixtures/java-spring
```

Open the report:

```bash
open .usage-trace/storeNo-report.html
```

You can also run the source entrypoint directly:

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring
```

## Analyze a Real Java Project

From this repository:

```bash
usage-trace \
  --keyword orderId \
  --root /path/to/your/java-project \
  --profile auto \
  --depth 4
```

Then open:

```bash
open .usage-trace/orderId-report.html
```

Use the actual project root, usually the directory containing `pom.xml`,
`build.gradle`, or `src/main/java`.

## CLI Options

```bash
usage-trace --keyword <identifier> --root <project> [options]
```

- `--keyword`: required keyword or field name, for example `orderId`.
- `--root`: required target project root.
- `--profile`: language profile. Default is `auto`; available Java profiles are
  `java-spring` and `java-generic`.
- `--depth`: call-chain depth. Default is `4`; the code applies a hard cap.
- `--max-nodes`: maximum graph nodes rendered in the report. Default is `300`.
- `--variants`: comma-separated extra keyword variants to search.
- `--out`: optional output HTML path. Default is `.usage-trace/<keyword>-report.html`
  in the current directory.

Compatibility command:

```bash
codex-find --keyword orderId --root /path/to/your/java-project
```

## How it runs (CLI first)

Analysis is done by the local **CLI**. You do **not** need an agent or skill
to generate reports.

```bash
python3 -m pip install -e .
usage-trace --keyword orderId --root /path/to/your/java-project --profile auto
open .usage-trace/orderId-report.html
```

| Piece | Role | Required? |
|-------|------|-----------|
| `usage-trace` CLI | Traces code and writes offline HTML | **Yes** |
| Skill (`SKILL.md`) | Tells Codex/Claude/Cursor when/how to run the CLI | Optional |
| Marketplace plugin | Distributes the skill via Codex / Claude Code / Cursor marketplaces | Optional |

Full ops guide (install, skill, FAQ): **[docs/skill-install.md](docs/skill-install.md)**.

## Skill (optional, Claude / Codex / Cursor)

Package as a **skill**, not a Claude Code subagent. Definition:

```text
skills/usage-trace/SKILL.md
```

CLI must still be installed first. Then:

```bash
bash scripts/install.sh                         # CLI + skill symlink (recommended)
bash scripts/install-skill.sh user              # Claude + agents + Cursor skill dirs
bash scripts/install-skill.sh project /path/to/java-project
bash scripts/install-skill.sh codex-user        # ~/.codex/skills only
```

Then ask the assistant:

```text
使用 usage-trace 分析当前项目的 orderId，生成 .usage-trace/orderId-report.html，并总结使用位置、调用链和涉及数据库表。
```

It should run:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4
```

## Marketplace Plugins (optional)

This repository ships multi-platform plugin metadata (skill only; CLI still required):

```text
.codex-plugin/plugin.json
.claude-plugin/marketplace.json + plugin.json
.cursor-plugin/marketplace.json + plugin.json
.agents/plugins/marketplace.json
plugins/usage-trace/.codex-plugin/
plugins/usage-trace/.claude-plugin/
plugins/usage-trace/.cursor-plugin/
skills/usage-trace/SKILL.md
```

**Codex**

```bash
codex plugin marketplace add ddsyw/usage-trace --ref main
codex plugin add usage-trace@usage-trace
```

Or open `/plugins` in Codex and install from the `usage-trace` marketplace.

**Claude Code**

```text
/plugin marketplace add ddsyw/usage-trace
/plugin install usage-trace@usage-trace
```

**Cursor**

```bash
bash scripts/install-skill.sh cursor-user
# local plugin dev: copy plugins/usage-trace -> ~/.cursor/plugins/local/usage-trace
```

After installation, start a new agent thread and ask:

```text
Use usage-trace to analyze orderId in the current Java project and generate .usage-trace/orderId-report.html.
```

## Report Contents

The generated HTML report includes:

- a summary of matched usage counts and table counts
- an interactive layered call-chain dashboard with a default main-path view,
  left-side layer tabs, group frames, search, pan, zoom, and click-to-focus
  neighborhood highlighting
- Understand-Anything-style graph metadata: node type, complexity, tags,
  weighted edges, architecture layers, guided tour steps, and cross-layer
  relationship aggregation
- a collapsed network overview
- usage-site table with file, line, layer, occurrence type, and snippet
- database table details with operation, source unit, source file, statement id,
  and SQL snippet
- MyBatis XML / SQL source statements, including unlinked statements for diagnostics
- notes about truncation and inferred edges

The report is self-contained and does not require external assets.

## Support Matrix

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
- Non-Java languages:
  - not supported for full call-chain tracing yet

## Debug Pipeline

The single `usage-trace` command orchestrates these phases:

1. `src/discover.py`: discover keyword usage sites
2. `src/trace.py`: build the call graph
3. `src/tables.py`: resolve database tables
4. `src/graph.py`: prune and layout graph nodes
5. `src/render.py`: render the offline HTML report

These scripts remain available for debugging individual phases.

## Development

Run the full verification suite:

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m compileall -q src tests
git diff --check
```

Run a focused smoke test:

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Project Layout

```text
.agents/plugins/marketplace.json   Codex repo marketplace
.codex-plugin/plugin.json          Root Codex plugin manifest
.claude-plugin/                    Claude Code plugin + marketplace
.cursor-plugin/                    Cursor plugin + marketplace
docs/skill-install.md              Skill installation and usage guide
plugins/usage-trace/               Thin multi-platform plugin wrapper
profiles/                          Java analysis profiles
scripts/install-skill.sh           Skill installer (user / project / codex-user)
skills/usage-trace/SKILL.md        Skill definition (synced into plugin)
src/                               CLI and analysis phases
templates/report.html.tmpl         Offline report template
tests/                             Unit, integration, and fixture tests
```

## Limitations

- The call graph is static and heuristic; reflection, runtime proxies, dynamic
  SQL generation, and complex dependency injection may require manual review.
- Non-Java projects are not supported for full tracing yet.
- Very large projects may need a lower `--max-nodes` value or narrower keyword
  variants to keep reports readable.

- Python (SQLAlchemy / generic):
  - keyword usage + call-chain tracing (tree-sitter-python)
  - `__tablename__` / `Table()` and SQL string table hints
- C# (EF Core / generic):
  - keyword usage + call-chain tracing (tree-sitter-c-sharp)
  - `[Table]` / `ToTable` / `DbSet` and SQL string table hints
