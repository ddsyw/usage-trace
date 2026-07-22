#!/usr/bin/env bash
# Unified usage-trace installer (P3): CLI + multi-platform skill + optional git hooks.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install.sh                 # CLI (editable) + skill user dirs (symlink)  [Recommended]
  install.sh all             # same as default
  install.sh cli             # python3 -m pip install -e .
  install.sh skill [args...] # forward to install-skill.sh (default --symlink)
  install.sh hooks           # install optional repo pre-commit sync hook
  install.sh sync            # sync thin plugin skill copy from skills/

Examples:
  bash scripts/install.sh
  bash scripts/install.sh cli
  bash scripts/install.sh skill --copy user
  bash scripts/install.sh hooks
USAGE
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cmd="${1:-all}"
if [[ $# -gt 0 ]]; then
  shift
fi

install_cli() {
  echo "Installing CLI (editable) from $repo_root ..."
  python3 -m pip install -e "$repo_root"
  if command -v usage-trace >/dev/null 2>&1; then
    echo "  usage-trace -> $(command -v usage-trace)"
  else
    echo "  note: usage-trace not on PATH yet; open a new shell or check pip bin dir." >&2
  fi
}

install_skill() {
  bash "$script_dir/install-skill.sh" "$@"
}

install_hooks() {
  bash "$script_dir/hooks/install-hooks.sh"
}

sync_copies() {
  bash "$script_dir/sync-plugin-copies.sh"
}

case "$cmd" in
  all|"")
    install_cli
    install_skill user
    ;;
  cli)
    install_cli
    ;;
  skill)
    install_skill "$@"
    ;;
  hooks)
    install_hooks
    ;;
  sync)
    sync_copies
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
