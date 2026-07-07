# usage-trace

[中文文档](README-CN.md)

`usage-trace` is a local code-analysis CLI and Claude Code subagent for tracing a
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
- Support Claude Code through a project-level or user-level subagent.
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
  --root tests/fixtures/java-spring \
  --out output/storeNo-report.html
```

Open the report:

```bash
open output/storeNo-report.html
```

You can also run the source entrypoint directly:

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring \
  --out output/storeNo-report.html
```

## Analyze a Real Java Project

From this repository:

```bash
usage-trace \
  --keyword orderId \
  --root /path/to/your/java-project \
  --profile auto \
  --depth 4 \
  --out /tmp/orderId-report.html
```

Then open:

```bash
open /tmp/orderId-report.html
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
- `--out`: output HTML path. Default is `output/<keyword>-report.html`.

Compatibility command:

```bash
codex-find --keyword orderId --root /path/to/your/java-project --out /tmp/orderId-report.html
```

## Claude Code Agent

The Claude Code subagent definition lives at:

```text
.claude/agents/usage-trace.md
```

Install the CLI first:

```bash
python3 -m pip install -e .
```

Install the agent into a specific Java project:

```bash
bash scripts/install-claude-agent.sh project /path/to/your/java-project
```

Or install it for your Claude Code user:

```bash
bash scripts/install-claude-agent.sh user
```

Then open Claude Code from the Java project root and ask:

```text
使用 usage-trace 分析当前项目的 orderId，生成 /tmp/orderId-report.html，并总结使用位置、调用链和涉及数据库表。
```

The agent should run:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4 --out /tmp/orderId-report.html
```

## Report Contents

The generated HTML report includes:

- a summary of matched usage counts and table counts
- a layered call-chain SVG diagram
- a collapsed network overview
- usage-site table with file, line, layer, occurrence type, and snippet
- database table table with operation, source unit, and SQL snippet
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
  --root tests/fixtures/java-spring \
  --out /tmp/storeNo-report.html
```

## Project Layout

```text
.claude/agents/usage-trace.md      Claude Code subagent definition
docs/claude-code-agent.md          Claude Code installation and usage guide
profiles/                          Java analysis profiles
scripts/install-claude-agent.sh    Claude Code agent installer
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
