#!/usr/bin/env bash
# Install usage-trace skill for Codex / Claude Code / Cursor.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-skill.sh user              # all user-level skill dirs (Recommended)
  install-skill.sh project [dir]     # all project-level skill dirs
  install-skill.sh codex-user        # only ~/.codex/skills (or $CODEX_HOME)
  install-skill.sh claude-user       # only ~/.claude/skills
  install-skill.sh cursor-user       # only ~/.cursor/skills
  install-skill.sh all               # alias of user

Installs skills/usage-trace/SKILL.md for coding agents.
Not a Claude Code subagent.

Skill load paths (Agent Skills standard):
  Claude Code  ~/.claude/skills/  or  <project>/.claude/skills/
  Cursor       ~/.cursor/skills/  or  <project>/.cursor/skills/
               also reads ~/.agents/skills/ and .agents/skills/
  Codex        ~/.codex/skills/   or  plugin marketplace
               also reads ~/.agents/skills/

Examples:
  install-skill.sh user
  install-skill.sh project .
  install-skill.sh codex-user
USAGE
}

mode="${1:-user}"
target="${2:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_src="$repo_root/skills/usage-trace/SKILL.md"

if [[ ! -f "$skill_src" ]]; then
  echo "Skill definition not found: $skill_src" >&2
  exit 1
fi

install_one() {
  local dir="$1"
  mkdir -p "$dir"
  install -m 0644 "$skill_src" "$dir/SKILL.md"
  echo "  $dir/SKILL.md"
}

dests=()

case "$mode" in
  user|all)
    dests+=(
      "${HOME}/.claude/skills/usage-trace"
      "${HOME}/.cursor/skills/usage-trace"
      "${HOME}/.agents/skills/usage-trace"
      "${CODEX_HOME:-$HOME/.codex}/skills/usage-trace"
    )
    ;;
  project)
    project_dir="${target:-$PWD}"
    project_dir="$(cd "$project_dir" && pwd)"
    dests+=(
      "$project_dir/.claude/skills/usage-trace"
      "$project_dir/.cursor/skills/usage-trace"
      "$project_dir/.agents/skills/usage-trace"
    )
    ;;
  codex-user)
    dests+=("${CODEX_HOME:-$HOME/.codex}/skills/usage-trace")
    ;;
  claude-user)
    dests+=("${HOME}/.claude/skills/usage-trace")
    ;;
  cursor-user)
    dests+=("${HOME}/.cursor/skills/usage-trace")
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

echo "Installed usage-trace skill:"
for d in "${dests[@]}"; do
  install_one "$d"
done

cat <<EOF

CLI (required in the same shell the agent uses):

  python3 -m pip install -e "$repo_root"
  # verify: usage-trace --help

Then ask (examples):

  查找 orderId 字段项目使用情况
  Trace storeNo call chain and database tables in the current project

The agent should load this skill and run:

  usage-trace --keyword orderId --root . --profile auto --depth 4

Platform notes:
  - Claude Code: ~/.claude/skills or <project>/.claude/skills
  - Cursor:      ~/.cursor/skills or <project>/.cursor/skills
                 (also loads .agents/skills and Claude/Codex skill dirs)
  - Codex:       plugin marketplace, or ~/.codex/skills / install-skill.sh codex-user
