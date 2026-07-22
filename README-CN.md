# usage-trace 中文版

[English README](README.md)

`usage-trace` 以编码助手 **插件 + Skill** 形式提供。在 Codex / Claude Code / Cursor
安装插件后，直接在目标项目里说：

```text
分析当前项目的 orderId
```

助手会 **自动匹配 skill**，必要时安装本地 CLI，并生成离线 HTML 报告（使用位置、调用链、相关表）。

## 功能

- 搜索关键字使用位置，并支持自动生成常见命名变体。
- 围绕命中方法构建调用链图。
- 识别 Controller、Service、Repository、Entity、SQL、Table 等层级。
- 解析多种数据库访问来源（MyBatis、JPA、SQLAlchemy、EF Core、原始 SQL、字符串 SQL 等）。
- 生成单文件离线 HTML 报告，不依赖外部资源。
- 通过 Codex / Claude Code / Cursor 插件市场安装；自然语言自动触发 skill。
- 通过 `--profile auto` 支持 Java、Python、C#。
- 兼容旧命令名 `codex-find`。

## 安装（仅插件）

### Codex

```bash
codex plugin marketplace add ddsyw/usage-trace --ref main
codex plugin add usage-trace@usage-trace
```

或在 Codex 中打开 `/plugins`，从 `usage-trace` marketplace 安装。

### Claude Code

```text
/plugin marketplace add ddsyw/usage-trace
/plugin install usage-trace@usage-trace
```

### Cursor

本地安装 thin plugin（当前推荐）：

**Windows PowerShell**（在本仓库根目录执行）：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\plugins\local\usage-trace" | Out-Null
Copy-Item -Recurse -Force ".\plugins\usage-trace\*" "$env:USERPROFILE\.cursor\plugins\local\usage-trace\"
```

**macOS / Linux / Git Bash**：

```bash
mkdir -p ~/.cursor/plugins/local/usage-trace
cp -R plugins/usage-trace/. ~/.cursor/plugins/local/usage-trace/
```

确认存在：

```text
~/.cursor/plugins/local/usage-trace/.cursor-plugin/plugin.json
~/.cursor/plugins/local/usage-trace/skills/usage-trace/SKILL.md
```

也可按 Cursor 文档提交到官方 Marketplace。

## 使用（自动触发 Skill）

在目标项目里用自然语言提问，**不必点名 skill**：

```text
分析当前项目的 orderId
```

```text
查找 storeNo 字段项目使用情况，生成报告并总结调用链和表
```

```text
Trace userId usage, call chain, and related tables
```

助手应自动：

1. 加载 `usage-trace` skill  
2. 若缺少 CLI，则执行：
   ```bash
   python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
   ```
3. 运行：
   ```bash
   usage-trace --keyword orderId --root . --profile auto --depth 4
   ```
4. 总结 `.usage-trace/orderId-report.html`

## 助手调用的 CLI 参数

```bash
usage-trace --keyword <identifier> --root <project> [options]
```

- `--keyword`：必填，字段名或标识符，例如 `orderId`。
- `--root`：必填，目标项目根目录；“当前项目”时用 `.`。
- `--profile`：语言 profile，默认 `auto`；可选 `java-spring`、`java-generic`、
  `python-sqlalchemy`、`python-generic`、`csharp-ef`、`csharp-generic`。
- `--depth`：调用链深度，默认 `4`。
- `--max-nodes`：报告中最多渲染的图节点数量，默认 `300`。
- `--variants`：额外关键字变体，逗号分隔。
- `--out`：可选输出 HTML 路径，默认 `.usage-trace/<keyword>-report.html`。

兼容旧命令：

```bash
codex-find --keyword orderId --root /path/to/your/project
```

## 报告内容

生成的 HTML 报告包含：

- 命中使用位置数量和涉及表数量概览
- 分层调用链 dashboard（主路径、层级 tab、搜索、聚焦上下游等）
- Understand-Anything 风格图元数据
- 使用位置明细与数据库表明细
- MyBatis XML / SQL 诊断（若有）
- 截断说明和推断边说明

报告是单个离线 HTML 文件，不需要联网或额外静态资源。

## 支持范围

- Java/Spring：关键字、分层、MyBatis、JPA、原始/字符串 SQL
- 普通 Java：关键字、调用链、包路径分层、MyBatis XML、原始/字符串 SQL
- Python（SQLAlchemy / generic）：关键字与调用链、`__tablename__` / `Table()` 等
- C#（EF Core / generic）：关键字与调用链、`[Table]` / `ToTable` / `DbSet` 等

## 调试流水线

1. `src/discover.py`：发现关键字使用位置  
2. `src/trace.py`：构建调用链图  
3. `src/tables.py`：解析数据库表  
4. `src/graph.py`：裁剪和布局图节点  
5. `src/render.py`：生成离线 HTML 报告  

## 开发验证

```bash
git clone https://github.com/ddsyw/usage-trace.git
cd usage-trace
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m ruff check .
python3 -m compileall -q src tests
```

Smoke test：

```bash
python3 src/usage_trace.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring
```

维护者脚本（终端用户不需要）：

```bash
bash scripts/install.sh
bash scripts/install.sh sync
```

## 变更日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 项目结构

```text
.agents/plugins/marketplace.json   Codex repo marketplace
.codex-plugin/plugin.json          根目录 Codex plugin manifest
.claude-plugin/                    Claude Code plugin + marketplace
.cursor-plugin/                    Cursor plugin + marketplace
docs/skill-install.md              插件安装与使用说明
plugins/usage-trace/               多平台 thin plugin
profiles/                          分析 profile
scripts/                           维护者脚本
skills/usage-trace/SKILL.md        Skill 定义
src/                               CLI 与分析阶段
templates/report.html.tmpl         离线报告模板
tests/                             测试与示例项目
```

## 限制

- 调用链是静态启发式分析；反射、运行时代理、动态 SQL 和复杂依赖注入可能需要人工复核。
- 超大项目可降低 `--max-nodes` 或收窄关键字变体，让报告更易读。