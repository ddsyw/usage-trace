# usage-trace

<details open>
<summary><strong>English</strong></summary>

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

</details>

---

<details>
<summary><strong>中文</strong></summary>

## 中文版

`usage-trace` 是一个本地代码分析 CLI，同时提供 Claude Code subagent 配置。它用于在 Java 项目中追踪某个字段或标识符的完整使用路径。输入 `orderId`、`storeNo` 这类关键字后，工具会生成一个离线 HTML 报告，展示使用位置、调用链和相关数据库表。

这个项目适合日常代码排查场景：当你想知道“这个字段在哪里被使用、经过了哪些方法、最终访问了哪些表”时，可以直接用它生成分析报告。

### 功能

- 在 Java 项目中搜索关键字使用位置，并支持自动生成常见变体。
- 围绕命中的方法构建调用链图。
- 识别 Controller、Service、Repository、Entity、SQL、Table 等层级。
- 支持解析以下数据库访问来源：
  - MyBatis XML mapper SQL
  - MyBatis 注解 SQL
  - JPA repository/entity 映射
  - 原始 SQL 文件
  - Java 字符串 SQL
- 生成单文件离线 HTML 报告，不依赖外部资源。
- 支持通过 Claude Code subagent 调用。
- 支持 Spring 项目和非 Spring 普通 Java 项目，默认使用 `--profile auto` 自动识别。
- 保留 `codex-find` 兼容命令，主项目名和主命令为 `usage-trace`。

### 仓库地址

```bash
git clone https://github.com/ddsyw/usage-trace.git
cd usage-trace
```

### 环境要求

- Python 3.10+
- `pip`
- 推荐安装 `rg` / ripgrep 以获得更快搜索速度；如果没有安装，会自动回退到 Python 搜索实现。

安装依赖和本地 CLI：

```bash
python3 -m pip install -e ".[dev]"
```

### 快速开始

使用项目内置 Spring 示例运行：

```bash
usage-trace \
  --keyword storeNo \
  --root tests/fixtures/java-spring \
  --out output/storeNo-report.html
```

打开报告：

```bash
open output/storeNo-report.html
```

也可以直接运行源码入口：

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring \
  --out output/storeNo-report.html
```

### 分析真实 Java 项目

在 `usage-trace` 仓库中执行：

```bash
usage-trace \
  --keyword orderId \
  --root /path/to/your/java-project \
  --profile auto \
  --depth 4 \
  --out /tmp/orderId-report.html
```

打开报告：

```bash
open /tmp/orderId-report.html
```

`--root` 应该指向真实 Java 项目根目录，通常是包含 `pom.xml`、`build.gradle` 或 `src/main/java` 的目录。

### CLI 参数

```bash
usage-trace --keyword <identifier> --root <project> [options]
```

- `--keyword`：必填，字段名或标识符，例如 `orderId`。
- `--root`：必填，目标项目根目录。
- `--profile`：语言 profile。默认是 `auto`；当前 Java profile 包括 `java-spring` 和 `java-generic`。
- `--depth`：调用链深度，默认 `4`，代码中有硬限制。
- `--max-nodes`：报告中最多渲染的图节点数量，默认 `300`。
- `--variants`：额外关键字变体，使用逗号分隔。
- `--out`：输出 HTML 路径，默认 `output/<keyword>-report.html`。

兼容旧命令：

```bash
codex-find --keyword orderId --root /path/to/your/java-project --out /tmp/orderId-report.html
```

### Claude Code Agent 用法

Claude Code subagent 定义文件位于：

```text
.claude/agents/usage-trace.md
```

先安装 CLI：

```bash
python3 -m pip install -e .
```

安装到某个 Java 项目：

```bash
bash scripts/install-claude-agent.sh project /path/to/your/java-project
```

或安装到当前用户级 Claude Code agents：

```bash
bash scripts/install-claude-agent.sh user
```

然后在 Java 项目根目录打开 Claude Code，输入：

```text
使用 usage-trace 分析当前项目的 orderId，生成 /tmp/orderId-report.html，并总结使用位置、调用链和涉及数据库表。
```

agent 应执行：

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4 --out /tmp/orderId-report.html
```

### 报告内容

生成的 HTML 报告包含：

- 命中使用位置数量和涉及表数量概览
- 分层调用链 SVG 图
- 折叠版网络全景图
- 使用位置明细，包括文件、行号、层级、命中类型和代码片段
- 数据库表明细，包括操作类型、来源单元和 SQL 片段
- 截断说明和推断边说明

报告是单个离线 HTML 文件，不需要联网或额外静态资源。

### 支持范围

- Java/Spring：
  - 关键字使用追踪
  - Controller、Service、Repository、Entity 层识别
  - MyBatis XML 和注解 SQL
  - JPA repository/entity 表映射
  - 原始 SQL 文件和 Java SQL 字符串
- 普通 Java：
  - 关键字使用追踪
  - 调用链图
  - 基于包路径的层级识别
  - 原始 SQL 文件和 Java SQL 字符串
- 非 Java 语言：
  - 暂不支持完整调用链追踪

### 调试流水线

单条 `usage-trace` 命令内部会编排以下阶段：

1. `src/discover.py`：发现关键字使用位置
2. `src/trace.py`：构建调用链图
3. `src/tables.py`：解析数据库表
4. `src/graph.py`：裁剪和布局图节点
5. `src/render.py`：生成离线 HTML 报告

这些脚本也可以单独运行，便于调试某个阶段。

### 开发验证

运行完整验证：

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m compileall -q src tests
git diff --check
```

运行一个快速 smoke test：

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring \
  --out /tmp/storeNo-report.html
```

### 项目结构

```text
.claude/agents/usage-trace.md      Claude Code subagent 定义
docs/claude-code-agent.md          Claude Code 安装和使用说明
profiles/                          Java 分析 profile
scripts/install-claude-agent.sh    Claude Code agent 安装脚本
src/                               CLI 和分析阶段代码
templates/report.html.tmpl         离线报告模板
tests/                             单元测试、集成测试和示例项目
```

### 限制

- 调用链是静态启发式分析；反射、运行时代理、动态 SQL 和复杂依赖注入可能需要人工复核。
- 暂不支持非 Java 项目的完整调用链追踪。
- 对于非常大的项目，可以降低 `--max-nodes` 或收窄关键字变体，让报告更易读。

</details>
