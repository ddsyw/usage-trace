#!/usr/bin/env bash
# Deprecated: usage-trace ships as a skill, not a Claude Code subagent.
# This wrapper forwards to install-skill.sh.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "note: install-claude-agent.sh is deprecated; installing skill instead." >&2
exec bash "$script_dir/install-skill.sh" "$@"
