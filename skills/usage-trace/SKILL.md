---
name: usage-trace
description: Trace Java/Spring or plain Java keyword usage, call chains, and DB tables with the local usage-trace CLI and produce an offline HTML report.
---

# usage-trace

Use this skill when the user asks to find where a Java field, identifier, or keyword is used, how it flows through a project, or which database tables are involved. Typical keywords include `orderId`, `storeNo`, `userId`, and similar business fields.

## What It Does

`usage-trace` analyzes a Java project and writes a single offline HTML report containing:

- matched usage sites
- caller/callee chain
- involved database tables
- SQL snippets when resolvable
- layered SVG diagrams

Supported project types:

- Java/Spring projects
- plain Java projects

Full non-Java call-chain tracing is not supported yet.

## Inputs

- `keyword`: required field or identifier, for example `orderId`
- `root`: target project root; default to the current working directory when the user says "current project"
- `output`: report path; default to `/tmp/<keyword>-usage-trace-report.html`
- `depth`: optional call-chain depth; default `4`
- `profile`: default `auto`

## Preferred Command

If the `usage-trace` command is available on `PATH`, run:

```bash
usage-trace --keyword "<keyword>" --root "<target>" --profile auto --depth 4 --out "<output>"
```

Example:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4 --out /tmp/orderId-report.html
```

If the CLI is not installed, run from the plugin or repository root:

```bash
python3 src/usage_trace.py --keyword "<keyword>" --root "<target>" --profile auto --depth 4 --out "<output>"
```

If Python reports a missing dependency, install the package in editable mode from the plugin or repository root:

```bash
python3 -m pip install -e .
```

## Workflow

1. Identify the keyword and target project root from the user's request.
2. Choose an output path, usually `/tmp/<keyword>-report.html`.
3. Run `usage-trace --keyword ... --root ... --profile auto --depth 4 --out ...`.
4. Confirm the HTML report exists.
5. Summarize the key findings:
   - major usage sites
   - call-chain path
   - touched database tables
   - any inferred or ambiguous edges
6. Tell the user the report path.

## User-Facing Example

When the user asks:

```text
帮我查找 orderId 字段项目中的使用情况
```

Run:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4 --out /tmp/orderId-report.html
```

Then summarize the report and mention:

```text
报告路径：/tmp/orderId-report.html
```

## References

- English README: `README.md`
- Chinese README: `README-CN.md`
- Claude Code agent guide: `docs/claude-code-agent.md`
