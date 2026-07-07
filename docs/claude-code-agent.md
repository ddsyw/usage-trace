# Claude Code Agent Setup

`usage-trace` is a Python CLI plus a Claude Code subagent definition. The CLI does the analysis; the Claude Code agent tells Claude when and how to run it.

## 1. Install the CLI

From this repository:

```bash
cd /path/to/usage-trace
python3 -m pip install -e .
```

Verify:

```bash
usage-trace --keyword storeNo --root tests/fixtures/java-spring --out /tmp/storeNo-report.html
```

## 2. Install the Claude Code agent

Project-level install, recommended when only one Java project should use this agent:

```bash
cd /path/to/your/java-project
bash /path/to/usage-trace/scripts/install-claude-agent.sh project .
```

This creates:

```text
/path/to/your/java-project/.claude/agents/usage-trace.md
```

User-level install, useful when all Claude Code projects should see the agent:

```bash
bash /path/to/usage-trace/scripts/install-claude-agent.sh user
```

This creates:

```text
~/.claude/agents/usage-trace.md
```

## 3. Use it in Claude Code

Open Claude Code from the Java project root, then ask:

```text
Use usage-trace to analyze orderId in the current project. Generate /tmp/orderId-report.html, then summarize the usage sites, call chain, and database tables.
```

The agent should run:

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4 --out /tmp/orderId-report.html
```

Open the result on macOS:

```bash
open /tmp/orderId-report.html
```

## Notes

- Project roots should contain the real Java project, for example a directory with `pom.xml`, `build.gradle`, or `src/main/java`.
- `--profile auto` chooses `java-spring` for Spring projects and `java-generic` for plain Java projects.
- Non-Java projects are not supported for full call-chain tracing yet.
- If Claude Code cannot find `usage-trace`, run `python3 -m pip install -e /path/to/usage-trace` again in the same shell environment used by Claude Code.
