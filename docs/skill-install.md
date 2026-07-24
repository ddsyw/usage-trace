# usage-trace 操作说明（Cursor skill）

`usage-trace` 以 **Cursor skill + 本地 CLI** 形式提供。

用户侧只做两件事：

1. 把 `skills/usage-trace/SKILL.md` 装到 Cursor 的 skill 目录
2. 在目标项目里直接说需求，例如：`分析当前项目的 orderId`

Cursor 会 **自动匹配并加载 skill**，必要时自动安装本地 CLI，然后生成离线 HTML 报告。

| 组件 | 作用 |
|------|------|
| **Skill** (`SKILL.md`) | 匹配用户意图并指导助手如何分析 |
| **CLI** (`usage-trace`) | 本地分析引擎；skill 首次运行时若缺失会 `pip install` 安装 |

> 不需要插件包装或市场清单。Cursor 只要能读到 skill 文件即可。

---

## 1. 安装 skill（唯一推荐用户路径）

### 一条命令（推荐）

在本仓库根目录：

```bash
bash scripts/install.sh
```

### 手动安装

**macOS / Linux / Git Bash**：

```bash
mkdir -p ~/.cursor/skills/usage-trace
cp skills/usage-trace/SKILL.md ~/.cursor/skills/usage-trace/SKILL.md
```

或软链：

```bash
ln -sfn "$(pwd)/skills/usage-trace" ~/.cursor/skills/usage-trace
```

**Windows PowerShell**：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\skills\usage-trace" | Out-Null
Copy-Item -Force ".\skills\usage-trace\SKILL.md" "$env:USERPROFILE\.cursor\skills\usage-trace\SKILL.md"
```

确认：

```text
~/.cursor/skills/usage-trace/SKILL.md
```

然后 **重启 Cursor 或新开 Agent 会话**。  
装好后在**业务项目**里提问（不必在 usage-trace 仓库内）。

CLI 若缺失，skill 会提示安装：

```bash
python3 -m pip install -U "git+https://github.com/ddsyw/usage-trace.git"
```

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

---

## 3. 报告内容

单次运行生成 **一个离线 HTML**（无外链），通常包括：

- 关键字命中位置（含命名变体）
- 调用链图（层 → 类 → 方法）
- 涉及数据库表与 SQL 片段
- 交互式分层 dashboard

---

## 4. 维护者说明（非终端用户）

```bash
bash scripts/install.sh                 # Cursor skill 目录 + editable CLI
bash scripts/install.sh skill cursor-user
bash scripts/install.sh hooks           # 可选 pre-commit
```

相关路径：

```text
skills/usage-trace/SKILL.md    Skill 定义（唯一权威副本）
scripts/install-skill.sh       安装到 ~/.cursor/skills
src/                           分析引擎
```
