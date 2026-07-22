# usage-trace 操作说明

`usage-trace` 是 **本地 Python CLI**，可选配 **Skill** 供编码助手调用。

| 组件 | 作用 | 是否必须 |
|------|------|----------|
| **CLI** (`usage-trace`) | 分析 Java 代码并生成离线 HTML 报告 | **必须** |
| **Skill** (`SKILL.md`) | 告诉 Codex / Claude / Cursor 何时、如何调用 CLI | 可选 |
| **Codex plugin** | 通过 marketplace 分发 skill | 可选 |

**不再提供** Claude Code subagent（`.claude/agents/`）。旧脚本 `install-claude-agent.sh` 会转发到 skill 安装。

---

## 1. 安装并运行 CLI（推荐日常用法）

```bash
git clone https://github.com/ddsyw/usage-trace.git
cd usage-trace
python3 -m pip install -e .
```

验证：

```bash
usage-trace --keyword storeNo --root tests/fixtures/java-spring
open .usage-trace/storeNo-report.html   # macOS
```

分析真实 Java 项目：

```bash
usage-trace \
  --keyword orderId \
  --root /path/to/your/java-project \
  --profile auto \
  --depth 4
```

报告默认写到当前目录的 `.usage-trace/<keyword>-report.html`。

### 常用参数

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--keyword` | 是 | — | 字段/标识符，如 `orderId`、`storeNo` |
| `--root` | 是 | — | 目标项目根（含 `pom.xml` / `build.gradle` / `src/main/java`） |
| `--profile` | 否 | `auto` | `java-spring` 或 `java-generic` |
| `--depth` | 否 | `4` | 调用链深度（CLI 有上限） |
| `--max-nodes` | 否 | `300` | 报告图节点上限 |
| `--variants` | 否 | — | 额外关键字变体，逗号分隔 |
| `--out` | 否 | `.usage-trace/<keyword>-report.html` | 输出 HTML 路径 |

兼容旧命令名：`codex-find`（与 `usage-trace` 同一入口）。

不通过 pip 安装时，也可在仓库内直接：

```bash
python3 src/usage_trace.py --keyword storeNo --root tests/fixtures/java-spring
```

---

## 2. 安装 Skill（仅在需要助手自动调用时）

Skill **不会**自己分析代码；它只指导助手去执行 `usage-trace`。因此 **CLI 仍须装好**，且助手所用 shell 的 `PATH` 上能找到 `usage-trace`。

### 用户级（推荐）

```bash
bash /path/to/usage-trace/scripts/install-skill.sh user
```

写入：

```text
~/.claude/skills/usage-trace/SKILL.md
~/.agents/skills/usage-trace/SKILL.md
~/.cursor/skills/usage-trace/SKILL.md   # 若目录存在惯例则一并安装
```

（实际路径以 `install-skill.sh` 输出为准。）

### 仅 Codex

```bash
bash /path/to/usage-trace/scripts/install-skill.sh codex-user
```

写入 `~/.codex/skills/usage-trace/SKILL.md`（或 `$CODEX_HOME/skills/...`）。

### 仅 Claude / Cursor

```bash
bash /path/to/usage-trace/scripts/install-skill.sh claude-user
bash /path/to/usage-trace/scripts/install-skill.sh cursor-user
```

### 项目级（只给某个 Java 仓库）

```bash
bash /path/to/usage-trace/scripts/install-skill.sh project /path/to/your/java-project
```

写入该仓库下的 `.claude/skills/`、`.agents/skills/` 等。

### 助手侧示例提问

```text
查找 orderId 字段项目使用情况，生成 .usage-trace/orderId-report.html 并总结调用链和表
```

助手应执行：

```bash
usage-trace --keyword orderId --root . --profile auto --depth 4
```

---

## 3. Codex Plugin 路径

本仓库也是 Codex plugin marketplace 入口。Skill 定义在 `skills/usage-trace/SKILL.md`。

```bash
codex plugin marketplace add ddsyw/usage-trace --ref main
codex plugin add usage-trace@usage-trace
```

或在 Codex 中打开 `/plugins`，从 `usage-trace` marketplace 安装。

装好后建议新开会话。**CLI 仍需单独 `pip install -e .`**；plugin 只带 skill 说明，不替代分析二进制。

---

## 4. 报告内容

单次运行生成 **一个离线 HTML**（无外链），通常包括：

- 关键字命中位置（含命名变体）
- 调用链图（层 → 类 → 方法）
- 涉及数据库表与 SQL 片段（MyBatis / JPA / 原始 SQL / Java 字符串 SQL）
- 交互面板（搜索、主题、节点详情）

---

## 5. 常见问题

**Q: 只装 skill，不装 CLI 可以吗？**  
A: 不可以。助手只会按 skill 去调 `usage-trace`；命令不存在时会失败。

**Q: 还要不要装 Claude agent？**  
A: 不要。已改为 skill；`install-claude-agent.sh` 仅作兼容转发。

**Q: 助手找不到 `usage-trace`？**  
A: 在助手使用的同一环境执行 `python3 -m pip install -e /path/to/usage-trace`，确认 `which usage-trace` 有输出。

**Q: `--root` 指哪里？**  
A: Java 项目根目录，一般含 `pom.xml`、`build.gradle` 或 `src/main/java`。

**Q: 非 Java 项目？**  
A: 当前仅支持 Java（`java-spring` / `java-generic`）。多语言在路线图 P4。

---

## 6. 相关路径

```text
skills/usage-trace/SKILL.md              Skill 定义（权威副本）
plugins/usage-trace/skills/.../SKILL.md  plugin 内同步副本
scripts/install-skill.sh                 Skill 安装脚本
scripts/install-claude-agent.sh          已废弃，转发到 install-skill.sh
.codex-plugin/plugin.json                Codex plugin manifest
.agents/plugins/marketplace.json         仓库 marketplace
```
