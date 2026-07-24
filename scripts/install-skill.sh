#!/usr/bin/env bash
# Install usage-trace skill for Cursor (+ optional agents skill path Cursor also reads).
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-skill.sh [--symlink|--copy] [--skip-cli] user              # Cursor user skill dirs (Recommended)
  install-skill.sh [--symlink|--copy] [--skip-cli] project [dir]     # project-level .cursor/skills
  install-skill.sh [--symlink|--copy] [--skip-cli] cursor-user       # only ~/.cursor/skills
  install-skill.sh [--symlink|--copy] [--skip-cli] agents-user       # only ~/.agents/skills (Cursor also loads this)
  install-skill.sh [--symlink|--copy] [--skip-cli] all               # alias of user

Installs skills/usage-trace for Cursor and (by default) the local usage-trace CLI.

Link mode:
  --symlink   ln -sfn repo skills/usage-trace into each dest (default)
  --copy      copy SKILL.md into each dest
  USAGE_TRACE_SKILL_INSTALL=symlink|copy overrides the default

CLI:
  By default also runs: python3 -m pip install -e <repo>
  --skip-cli  install skill only (no pip)

Skill load paths (Cursor):
  ~/.cursor/skills/  or  <project>/.cursor/skills/
  also reads ~/.agents/skills/ and .agents/skills/

Examples:
  install-skill.sh user
  install-skill.sh --copy user
  install-skill.sh project .
  install-skill.sh cursor-user
USAGE
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_src="$repo_root/skills/usage-trace"
skill_md="$skill_src/SKILL.md"

if [[ ! -f "$skill_md" ]]; then
  echo "skill missing: $skill_md" >&2
  exit 1
fi

mode="${USAGE_TRACE_SKILL_INSTALL:-symlink}"
skip_cli=0
targets=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --symlink) mode=symlink; shift ;;
    --copy) mode=copy; shift ;;
    --skip-cli) skip_cli=1; shift ;;
    -h|--help|help) usage; exit 0 ;;
    --) shift; break ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      targets+=("$1")
      shift
      ;;
  esac
done

if [[ ${#targets[@]} -eq 0 ]]; then
  targets=(user)
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

install_one() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  if [[ "$mode" == "copy" ]]; then
    mkdir -p "$dest"
    # replace any previous symlink/dir cleanly
    if [[ -L "$dest" ]]; then
      rm -f "$dest"
      mkdir -p "$dest"
    fi
    cp -f "$skill_md" "$dest/SKILL.md"
    echo "  $dest/SKILL.md (copy)"
  else
    ln -sfn "$skill_src" "$dest"
    echo "  $dest -> $skill_src"
  fi
}

resolve_targets() {
  local t="$1"
  local project_dir="${2:-.}"
  case "$t" in
    all|user)
      printf '%s\n' \
        "$HOME/.cursor/skills/usage-trace" \
        "$HOME/.agents/skills/usage-trace"
      ;;
    cursor-user)
      printf '%s\n' "$HOME/.cursor/skills/usage-trace"
      ;;
    agents-user)
      printf '%s\n' "$HOME/.agents/skills/usage-trace"
      ;;
    project)
      # resolve project dir to absolute
      local abs
      abs="$(cd "$project_dir" && pwd)"
      printf '%s\n' \
        "$abs/.cursor/skills/usage-trace" \
        "$abs/.agents/skills/usage-trace"
      ;;
    *)
      echo "unknown target: $t" >&2
      usage >&2
      exit 2
      ;;
  esac
}

echo "Installed usage-trace skill ($mode):"
i=0
while [[ $i -lt ${#targets[@]} ]]; do
  t="${targets[$i]}"
  if [[ "$t" == "project" ]]; then
    next="${targets[$((i+1))]:-}"
    if [[ -n "$next" && "$next" != all && "$next" != user && "$next" != cursor-user && "$next" != agents-user && "$next" != project ]]; then
      project_dir="$next"
      i=$((i+2))
    else
      project_dir="."
      i=$((i+1))
    fi
    while IFS= read -r dest; do
      install_one "$dest"
    done < <(resolve_targets project "$project_dir")
  else
    while IFS= read -r dest; do
      install_one "$dest"
    done < <(resolve_targets "$t")
    i=$((i+1))
  fi
done

if [[ "$skip_cli" -eq 0 ]]; then
  install_cli
fi

cat <<'MSG'

Ask Cursor (examples):

  查找 orderId 字段项目使用情况
  Trace storeNo call chain and database tables in the current project

The agent should load this skill and run:

  usage-trace --keyword orderId --root . --profile auto --depth 4

Cursor loads skills from:
  ~/.cursor/skills/usage-trace/SKILL.md
  or <project>/.cursor/skills/usage-trace/SKILL.md
  (also ~/.agents/skills)
MSG
