---
name: usage-trace
description: Trace Java/Spring or plain Java keyword usage, call chains, and DB tables with the local usage-trace CLI and produce an offline HTML report. Use when the user asks to find a field's usage, trace a call chain, or identify involved DB tables. Supports Chinese queries like 查找字段使用情况, 追踪调用链, 字段流向分析, 查找字段项目使用情况.
---

# usage-trace

Skill for Java keyword usage analysis. Prefer this skill (not a subagent) whenever the user wants to find where a field/identifier is used, how it flows through the project, or which database tables it touches.

Typical keywords: `orderId`, `storeNo`, `userId`, and similar business fields.

## What It Does

Runs the local `usage-trace` CLI against a Java project and writes **one offline HTML report** with:

- matched usage sites (with naming variants)
- caller/callee call chain
- involved database tables (MyBatis XML/annotations, JPA, raw SQL, Java SQL strings)
- interactive graph dashboard (layer columns → class groups → methods)
- table / statement diagnostics and SQL snippets when resolvable

Supported:

- Java/Spring projects (`java-spring`)
- plain Java projects (`java-generic`)

Full non-Java call-chain tracing is not supported yet.

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `keyword` | yes | — | field / identifier, e.g. `orderId` |
| `root` | yes | current project when user says so | directory with `pom.xml` / `build.gradle` / `src/main/java` |
| `output` | no | `.usage-trace/<keyword>-report.html` | relative to cwd |
| `depth` | no | `4` | hard-capped in CLI |
| `profile` | no | `auto` | `java-spring` or `java-generic` |
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
   - main call-chain path (Controller → Service → Repository → Table when present)
   - touched database tables and statement sources
   - truncation notes or ambiguous edges, if any
6. Give the report path (and on macOS you may suggest `open <path>`).

## Graph Layout (report)

The HTML graph is organized as:

1. **Layer columns** — Controller / Service / Repository / Table / …
2. **Class groups inside each layer** — e.g. `AController`, `BController`, `CController`
3. **Methods under each class** — same class methods sit together

When summarizing, prefer this same hierarchy.

## User-Facing Example

User:

```text
帮我查找 orderId 字段项目中的使用情况
```

Run:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4
```

Reply with findings and:

```text
报告路径：.usage-trace/orderId-report.html
```

## Rules

- Always produce a report file when possible (zero hits still render a report).
- Report is a **single offline HTML** file — no external HTTP assets.
- Prefer the installed CLI; fall back to `python3 src/usage_trace.py` only from the usage-trace repo/plugin tree.
- Do not invent call edges; summarize only what the report/CLI produced.
- If a phase fails, say so and share whatever report was generated.

## Install This Skill

From the usage-trace repository:

```bash
# Claude Code / Codex-style user skill
bash scripts/install-skill.sh user

# project-local skill (into a Java project)
bash scripts/install-skill.sh project /path/to/java-project
```

Also available as a Codex plugin skill via `/plugins` (marketplace entry ships `skills/usage-trace/SKILL.md`).

## References

- English README: `README.md`
- Chinese README: `README-CN.md`
- Skill install guide: `docs/skill-install.md`
