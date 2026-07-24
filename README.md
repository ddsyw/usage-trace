# usage-trace

[中文文档](README-CN.md)

`usage-trace` is a **Cursor skill** (+ local CLI) for tracing a field or identifier
through Java, Python, or C# codebases. After installing the skill in Cursor, ask
naturally:

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
- Cursor skill auto-matching for natural-language prompts.
- Support Java, Python, and C# through `--profile auto`.

## Install (Cursor skill)

Cursor loads skills from `~/.cursor/skills/<name>/SKILL.md` (or project-level
`.cursor/skills/`). You only need the skill file — **plugin packaging is not required**.

### One command (recommended)

From this repository root:

```bash
bash scripts/install.sh
```

This symlinks `skills/usage-trace` into `~/.cursor/skills/usage-trace` (and
`~/.agents/skills/usage-trace`, which Cursor also reads) and installs the local
CLI in editable mode.

Cursor-only skill dir:

```bash
bash scripts/install.sh skill cursor-user
```

Copy instead of symlink:

```bash
bash scripts/install.sh skill --copy cursor-user
```

### Manual install

**macOS / Linux / Git Bash**:

```bash
mkdir -p ~/.cursor/skills/usage-trace
cp skills/usage-trace/SKILL.md ~/.cursor/skills/usage-trace/SKILL.md
# optional: install CLI
python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
```

Or symlink the whole skill directory (keeps updates in sync with this repo):

```bash
ln -sfn "$(pwd)/skills/usage-trace" ~/.cursor/skills/usage-trace
```

**Windows PowerShell** (from this repository root):

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\skills\usage-trace" | Out-Null
Copy-Item -Force ".\skills\usage-trace\SKILL.md" "$env:USERPROFILE\.cursor\skills\usage-trace\SKILL.md"
```

Confirm:

```text
~/.cursor/skills/usage-trace/SKILL.md
```

Then restart Cursor or open a new Agent session.

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
  - keyword usage + call-chain graph
  - `__tablename__` / `Table(...)` style table resolution
  - query/select oriented table hints when present
- C# (EF Core / generic):
  - keyword usage + call-chain graph
  - `[Table]`, `ToTable`, `DbSet`, `FromSqlRaw` oriented table resolution

## Debug pipeline

1. `src/discover.py` finds keyword usage sites.
2. `src/trace.py` builds the call-chain graph.
3. `src/tables.py` resolves database tables.
4. `src/graph.py` prunes and layouts graph nodes.
5. `src/render.py` writes the offline HTML report.

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
bash scripts/install.sh
bash scripts/install.sh skill --copy cursor-user
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Project layout

```text
skills/usage-trace/SKILL.md     Cursor skill definition
src/                            CLI and analysis phases
profiles/                       analysis profiles (java-*, python-*, csharp-*)
templates/                      HTML report template
tests/                          unit tests, e2e tests, and fixture projects
scripts/                        maintainer install helpers
docs/                           guides (skill-install.md)
```

## Ops

End-user install and trigger guide: [docs/skill-install.md](docs/skill-install.md).
