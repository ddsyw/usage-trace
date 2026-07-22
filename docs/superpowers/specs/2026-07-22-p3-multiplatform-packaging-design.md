# P3 设计：三端打包（Codex / Claude Code / Cursor）

**日期：** 2026-07-22  
**状态：** ✅ 已交付  
**所属路线图：** usage-trace 四阶段升级（P1 引擎 ✅ → P2 UA 风格报告 ✅ → P3 三端打包 ✅ → **P4 多语言** ✅ ✅）

## 目标

把 `usage-trace` skill 以统一方式分发到三个编码助手生态，并提供一键安装：

| 平台 | Manifest / Marketplace | 安装方式 |
|------|------------------------|----------|
| Codex | `.codex-plugin/` + `.agents/plugins/marketplace.json` | `/plugins` 或 `codex plugin ...` |
| Claude Code | `.claude-plugin/` | `/plugin marketplace add` + `/plugin install` |
| Cursor | `.cursor-plugin/` | skill 安装 / local plugin / 官方 Marketplace 提交流程 |

## 交付物

1. **多平台 plugin 元数据**
   - 根目录：`.codex-plugin/`、`.claude-plugin/`、`.cursor-plugin/`
   - thin wrapper：`plugins/usage-trace/.{codex,claude,cursor}-plugin/`
   - 权威 skill：`skills/usage-trace/SKILL.md`（与 thin 副本同步）
2. **统一安装入口** `scripts/install.sh`
   - `all`：`pip install -e .` + skill 用户级安装
   - `cli` / `skill` / `hooks` / `sync` 子命令
3. **Skill 安装默认 symlink**（`scripts/install-skill.sh --symlink`）
   - `--copy` 可选；`USAGE_TRACE_SKILL_INSTALL` 可覆盖
4. **可选 maintainer hook**
   - `scripts/hooks/pre-commit` + `scripts/hooks/install-hooks.sh`
   - `scripts/sync-plugin-copies.sh` 同步 thin plugin skill 副本

## 非目标

- 不把 CLI 打进 marketplace 二进制（plugin 只分发 skill）
- 不恢复 Claude Code subagent（`.claude/agents/`）
- 不做 P4 多语言解析

## 验收

- 六份 plugin.json `name/version/description` 对齐，含中文触发词
- `bash scripts/install-skill.sh --symlink claude-user` 生成有效 symlink
- `python3 -m pytest` 含 packaging / install script 测试全绿
- 文档：`docs/skill-install.md`、README 双语文档包含三端安装说明
