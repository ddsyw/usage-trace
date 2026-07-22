import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "scripts" / "install.sh"
INSTALL_SKILL = ROOT / "scripts" / "install-skill.sh"
SYNC = ROOT / "scripts" / "sync-plugin-copies.sh"
PRE_COMMIT = ROOT / "scripts" / "hooks" / "pre-commit"
INSTALL_HOOKS = ROOT / "scripts" / "hooks" / "install-hooks.sh"


def test_unified_install_script_exists():
    text = INSTALL_SH.read_text(encoding="utf-8")
    for needle in ["cli", "skill", "hooks", "sync", "install-skill.sh"]:
        assert needle in text, f"install.sh missing: {needle}"


def test_skill_installer_supports_symlink_and_copy():
    text = INSTALL_SKILL.read_text(encoding="utf-8")
    for needle in ["--symlink", "--copy", "ln -sfn", "USAGE_TRACE_SKILL_INSTALL"]:
        assert needle in text, f"install-skill.sh missing: {needle}"


def test_sync_and_hook_scripts_exist():
    assert SYNC.is_file()
    assert PRE_COMMIT.is_file()
    assert INSTALL_HOOKS.is_file()
    assert "sync-plugin-copies" in PRE_COMMIT.read_text(encoding="utf-8")


def test_install_skill_symlink_and_copy_modes():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
        }
        subprocess.run(
            ["bash", str(INSTALL_SKILL), "--symlink", "claude-user"],
            check=True,
            env=env,
            cwd=ROOT,
        )
        dest = home / ".claude" / "skills" / "usage-trace"
        assert dest.is_symlink()
        assert (dest / "SKILL.md").is_file()

        subprocess.run(
            ["bash", str(INSTALL_SKILL), "--copy", "cursor-user"],
            check=True,
            env=env,
            cwd=ROOT,
        )
        copy_dest = home / ".cursor" / "skills" / "usage-trace" / "SKILL.md"
        assert copy_dest.is_file()
        assert not (home / ".cursor" / "skills" / "usage-trace").is_symlink()


def test_sync_plugin_copies_is_idempotent():
    subprocess.run(["bash", str(SYNC)], check=True, cwd=ROOT)
    src = (ROOT / "skills" / "usage-trace" / "SKILL.md").read_text(encoding="utf-8")
    dst = (ROOT / "plugins" / "usage-trace" / "skills" / "usage-trace" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert src == dst
