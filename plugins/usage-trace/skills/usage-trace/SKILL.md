---
name: usage-trace
description: Trace Java/Spring or plain Java keyword usage, call chains, and DB tables with the local usage-trace CLI and produce an offline HTML report. Use when the user asks to find a field's usage, trace a call chain, or identify involved DB tables. Supports Chinese queries like 查找字段使用情况, 追踪调用链, 字段流向分析, 查找字段项目使用情况.
---

# usage-trace

Use this skill when the user asks to find where a Java field, identifier, or keyword is used, how it flows through a project, or which database tables are involved. Typical keywords include `orderId`, `storeNo`, `userId`, and similar business fields.

## What It Does

`usage-trace` analyzes a Java project and writes a single offline HTML report containing:

- matched usage sites
- caller/callee chain
- involved database tables
- MyBatis XML / SQL source statements, including unlinked statements for diagnostics
- SQL snippets when resolvable
- an interactive searchable graph dashboard with a default main-path view,
  left-side layer tabs, group frames, click-to-focus neighborhood highlighting,
  table details, node details, pan, and zoom
- Understand-Anything-style graph rules: node type, complexity, tags,
  weighted edges, architecture layers, guided tour steps, and cross-layer aggregation

Supported project types:

- Java/Spring projects
- plain Java projects

Full non-Java call-chain tracing is not supported yet.

## Inputs

- `keyword`: required field or identifier, for example `orderId`
- `root`: target project root; default to the current working directory when the user says "current project"
- `output`: report path; default to `.usage-trace/<keyword>-report.html` in the current directory
- `depth`: optional call-chain depth; default `4`
- `profile`: default `auto`

## Preferred Command

If the `usage-trace` command is available on `PATH`, run:

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

If Python reports a missing dependency, install the package in editable mode from the plugin or repository root:

```bash
python3 -m pip install -e .
```

## Workflow

1. Identify the keyword and target project root from the user's request.
2. Use the default output path `.usage-trace/<keyword>-report.html` unless the user explicitly asks for another path.
3. Run `usage-trace --keyword ... --root ... --profile auto --depth 4`.
4. Confirm the HTML report exists.
5. Summarize the key findings:
   - major usage sites
   - call-chain path
   - touched database tables
   - MyBatis XML / SQL source statements
   - any inferred or ambiguous edges
6. Tell the user the report path.

## User-Facing Example

When the user asks:

```text
帮我查找 orderId 字段项目中的使用情况
```

Run:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4
```

Then summarize the report and mention:

```text
报告路径：.usage-trace/orderId-report.html
```

## References

- English README: `README.md`
- Chinese README: `README-CN.md`
- Claude Code agent guide: `docs/claude-code-agent.md`
