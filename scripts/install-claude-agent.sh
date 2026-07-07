#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  install-claude-agent.sh project [project_dir]
  install-claude-agent.sh user

Examples:
  install-claude-agent.sh project .
  install-claude-agent.sh user
EOF
}

mode="${1:-project}"
target="${2:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
agent_src="$repo_root/.claude/agents/usage-trace.md"

if [[ ! -f "$agent_src" ]]; then
  echo "Agent definition not found: $agent_src" >&2
  exit 1
fi

case "$mode" in
  project)
    project_dir="${target:-$PWD}"
    dest_dir="$project_dir/.claude/agents"
    ;;
  user)
    dest_dir="$HOME/.claude/agents"
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

mkdir -p "$dest_dir"
install -m 0644 "$agent_src" "$dest_dir/usage-trace.md"

cat <<EOF
Installed Claude Code agent:
  $dest_dir/usage-trace.md

Make sure the CLI is installed and visible to Claude Code:
  python3 -m pip install -e "$repo_root"

Example Claude Code request:
  Use usage-trace to analyze orderId in the current project. Generate /tmp/orderId-report.html.
EOF
