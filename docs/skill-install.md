# usage-trace 操作说明

`usage-trace` 以 **插件 + Skill** 形式提供给编码助手（Codex / Claude Code / Cursor）。

用户侧只做两件事：

1. 在助手里 **安装 usage-trace 插件**
2. 在目标项目里直接说需求，例如：`分析当前项目的 orderId`

助手会 **自动匹配并加载 skill**，必要时自动安装本地 CLI，然后生成离线 HTML 报告。

| 组件 | 作用 |
|------|------|
| **Marketplace plugin** | 在 Codex / Claude Code / Cursor 中安装 skill |
| **Skill** (`SKILL.md`) | 匹配用户意图并指导助手如何分析 |
| **CLI** (`usage-trace`) | 本地分析引擎；skill 首次运行时若缺失会 `pip install` 安装 |

---

## 1. 安装插件（唯一推荐用户路径）

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

把本仓库的 thin plugin 装到 Cursor 本地插件目录（当前推荐方式）。

**Windows PowerShell**（在 usage-trace 仓库根目录执行）：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\plugins\local\usage-trace" | Out-Null
Copy-Item -Recurse -Force ".\plugins\usage-trace\*" "$env:USERPROFILE\.cursor\plugins\local\usage-trace\"
```

**macOS / Linux / Git Bash**：

```bash
mkdir -p ~/.cursor/plugins/local/usage-trace
cp -R plugins/usage-trace/. ~/.cursor/plugins/local/usage-trace/
```

确认目录中至少包含：

```text
~/.cursor/plugins/local/usage-trace/.cursor-plugin/plugin.json
~/.cursor/plugins/local/usage-trace/skills/usage-trace/SKILL.md
```

然后 **重启 Cursor 或新开 Agent 会话**。  
也可按 Cursor 官方流程把本仓库 marketplace 提交到 Cursor Marketplace。

装好后在**业务项目**里提问（不必在 usage-trace 仓库内）。

---

## 2. 自动触发

在目标项目根目录直接说：

```text
分析当前项目的 orderId
```

也可用：

```text
查找 storeNo 字段项目使用情况，生成报告并总结调用链和表
Trace userId usage, call chain, and related tables
```

助手应自动：

1. 加载 `usage-trace` skill（无需用户点名 skill）
2. 确保 `usage-trace` CLI 可用；缺失时执行：
   ```bash
   python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
   ```
3. 运行：
   ```bash
   usage-trace --keyword orderId --root . --profile auto --depth 4
   ```
4. 打开/总结 `.usage-trace/orderId-report.html`

### 常用 CLI 参数（助手会调用）

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--keyword` | 是 | — | 字段/标识符，如 `orderId` |
| `--root` | 是 | — | 目标项目根；“当前项目”时用 `.` |
| `--profile` | 否 | `auto` | `java-spring` / `java-generic` / `python-sqlalchemy` / `python-generic` / `csharp-ef` / `csharp-generic` |
| `--depth` | 否 | `4` | 调用链深度 |
| `--max-nodes` | 否 | `300` | 报告图节点上限 |
| `--variants` | 否 | — | 额外关键字变体，逗号分隔 |
| `--out` | 否 | `.usage-trace/<keyword>-report.html` | 输出 HTML 路径 |

兼容旧命令名：`codex-find`。

---

## 3. 报告内容

单次运行生成 **一个离线 HTML**（无外链），通常包括：

- 关键字命中位置（含命名变体）
- 调用链图（层 → 类 → 方法）
- 涉及数据库表与 SQL 片段
- 交互面板（搜索、主题、节点详情）

---

## 4. 常见问题

**Q: 一定要先跑仓库里的 install 脚本吗？**  
A: **不需要。** 用户路径是插件安装 + 自然语言提问。CLI 由 skill 在首次分析时按需 `pip install`。

**Q: 助手没有自动用 skill？**  
A: 确认插件已安装并新开了会话；提问尽量包含字段名 + 分析意图（分析 / 查找使用情况 / 调用链 / 涉及表）。Cursor 用户请确认 `~/.cursor/plugins/local/usage-trace/skills/usage-trace/SKILL.md` 存在。

**Q: 助手报找不到 `usage-trace`？**  
A: 让助手按 skill 执行  
`python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"`，  
然后重试；确认使用同一 shell 环境。

**Q: 支持哪些语言？**  
A: Java、Python、C#（见上表 profile）。`--profile auto` 自动选择。

---

## 5. 维护者说明（非终端用户）

仓库开发者可用：

```bash
bash scripts/install.sh              # 本地开发：skill 目录 + editable CLI
bash scripts/install.sh sync         # 同步 thin plugin 内 SKILL.md
bash scripts/install.sh hooks        # 可选 pre-commit 同步
```

相关路径：

```text
skills/usage-trace/SKILL.md              Skill 定义（权威副本）
plugins/usage-trace/skills/.../SKILL.md  plugin 内同步副本
.codex-plugin/plugin.json                Codex plugin manifest
.claude-plugin/                          Claude Code plugin + marketplace
.cursor-plugin/                          Cursor plugin + marketplace
.agents/plugins/marketplace.json         Codex 仓库 marketplace
plugins/usage-trace/                     多平台 thin plugin 包装
scripts/                                 维护者安装/同步脚本
```