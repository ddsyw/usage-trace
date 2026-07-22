#!/usr/bin/env bash
# Keep marketplace thin-plugin skill copy in sync with the authoritative skill.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
src="$repo_root/skills/usage-trace/SKILL.md"
dst="$repo_root/plugins/usage-trace/skills/usage-trace/SKILL.md"

if [[ ! -f "$src" ]]; then
  echo "source skill missing: $src" >&2
  exit 1
fi

mkdir -p "$(dirname "$dst")"
if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
  echo "skill copies already in sync"
  exit 0
fi

cp "$src" "$dst"
echo "updated $dst"
