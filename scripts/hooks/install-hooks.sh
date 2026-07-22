#!/usr/bin/env bash
# Install optional repo git hooks for usage-trace maintainers.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
hook_src="$script_dir/pre-commit"
hook_dst="$repo_root/.git/hooks/pre-commit"

if [[ ! -d "$repo_root/.git" ]]; then
  echo "not a git checkout: $repo_root" >&2
  exit 1
fi

if [[ ! -f "$hook_src" ]]; then
  echo "hook source missing: $hook_src" >&2
  exit 1
fi

mkdir -p "$(dirname "$hook_dst")"
if [[ -e "$hook_dst" || -L "$hook_dst" ]]; then
  if [[ -L "$hook_dst" ]]; then
    target="$(readlink "$hook_dst" || true)"
    if [[ "$target" == "$hook_src" ]]; then
      echo "pre-commit hook already installed -> $hook_src"
      exit 0
    fi
  fi
  backup="$hook_dst.usage-trace.bak"
  mv "$hook_dst" "$backup"
  echo "existing pre-commit backed up to $backup"
fi

ln -sfn "$hook_src" "$hook_dst"
echo "installed pre-commit hook -> $hook_src"
echo "it syncs plugins/usage-trace/skills/usage-trace/SKILL.md from skills/"
