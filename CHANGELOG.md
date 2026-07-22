# Changelog

## Unreleased

### Packaging & ops
- End-user path is **marketplace / local plugin install** (Codex, Claude Code, Cursor)
- Natural language like `分析当前项目的 orderId` auto-triggers the skill
- Missing CLI is installed by the skill via `pip install git+https://github.com/ddsyw/usage-trace.git`
- Maintainer `install-skill.sh` also installs the CLI by default (`--skip-cli` to opt out)
- Cursor install docs include Windows PowerShell and macOS/Linux steps
- Removed deprecated `scripts/install-claude-agent.sh` and `docs/claude-code-agent.md`

## 0.2.0 — 2026-07-22

### Highlights
- **P1** tree-sitter engine + incremental `ProjectIndex` (Java)
- **P2** Understand-Anything style offline HTML report (search, theme, persona, NodeInfo)
- **P3** multi-platform packaging: Codex / Claude Code / Cursor plugins, unified `scripts/install.sh`, skill symlink install, optional pre-commit sync hooks
- **P4** multi-language foundation: Python (SQLAlchemy) and C# (EF Core) parsers, profiles, table extraction

### Analysis
- Layer path classification uses path segments (avoids false Service hits on module names)
- Group methods by class in graph layout / report frames
- Improved discovery (camelCase boundaries, plurals)
- Table extraction: MyBatis / JPA / raw SQL / Java SQL strings; SQLAlchemy `__tablename__` + `query/select`; EF Core `[Table]` / `ToTable` / `DbSet` / `FromSqlRaw`
- Profile-scoped `source_exts` so monorepos only index the active language
- Auto profile detection scores by source counts for mixed repos

### Packaging & ops
- Skill-first (no Claude Code subagent)
- `scripts/install.sh` (`cli` / `skill` / `hooks` / `sync`)
- Marketplace manifests for Codex, Claude Code, Cursor
- Docs: `docs/skill-install.md`, dual-language README

### Breaking / notes
- Report output defaults under `.usage-trace/`
- Index cache version bumped with multi-language source sets
- Requires `tree-sitter`, `tree-sitter-java`, `tree-sitter-python`, `tree-sitter-c-sharp`

## 0.1.x — prior
- Initial Java/Spring CLI pipeline and Codex skill packaging

