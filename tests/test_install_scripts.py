import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "scripts" / "install.sh"
INSTALL_SKILL = ROOT / "scripts" / "install-skill.sh"
SYNC = ROOT / "scripts" / "sync-plugin-copies.sh"
PRE_COMMIT = ROOT / "scripts" / "hooks" / "pre-commit"
INSTALL_HOOKS = ROOT / "scripts" / "hooks" / "install-hooks.sh"
LEGACY_AGENT_INSTALLER = ROOT / "scripts" / "install-claude-agent.sh"
LEGACY_AGENT_DOC = ROOT / "docs" / "claude-code-agent.md"


def _resolve_bash() -> str:
    """Prefer Git Bash on Windows; system32 bash is often the WSL launcher."""
    candidates = []
    which = shutil.which("bash")
    if which:
        candidates.append(which)
    program_files = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        r"D:\Program Files",
    ]
    for root in program_files:
        if not root:
            continue
        candidates.append(str(Path(root) / "Git" / "bin" / "bash.exe"))
        candidates.append(str(Path(root) / "Git" / "usr" / "bin" / "bash.exe"))
    seen = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        path = Path(cand)
        if not path.is_file():
            continue
        # Skip WSL launcher which fails outside a configured distro.
        if path.name.lower() == "bash.exe" and "system32" in str(path).lower():
            continue
        try:
            probe = subprocess.run(
                [str(path), "-c", "echo ok"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0 and "ok" in (probe.stdout or ""):
            return str(path)
    raise RuntimeError("No usable bash found for install script tests")


def _bash() -> str:
    return _resolve_bash()


def test_unified_install_script_exists():
    text = INSTALL_SH.read_text(encoding="utf-8")
    for needle in ["cli", "skill", "hooks", "sync", "install-skill.sh"]:
        assert needle in text, f"install.sh missing: {needle}"
    assert "install_skill user" in text or 'install_skill "$@"' in text


def test_skill_installer_supports_symlink_copy_and_cli():
    text = INSTALL_SKILL.read_text(encoding="utf-8")
    for needle in [
        "--symlink",
        "--copy",
        "--skip-cli",
        "ln -sfn",
        "USAGE_TRACE_SKILL_INSTALL",
        "pip install -e",
        "install_cli",
    ]:
        assert needle in text, f"install-skill.sh missing: {needle}"


def test_sync_and_hook_scripts_exist():
    assert SYNC.is_file()
    assert PRE_COMMIT.is_file()
    assert INSTALL_HOOKS.is_file()
    assert "sync-plugin-copies" in PRE_COMMIT.read_text(encoding="utf-8")


def test_legacy_agent_paths_removed():
    assert not LEGACY_AGENT_INSTALLER.exists()
    assert not LEGACY_AGENT_DOC.exists()


def test_install_skill_symlink_and_copy_modes():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
        }
        subprocess.run(
            [_bash(), str(INSTALL_SKILL), "--skip-cli", "--symlink", "claude-user"],
            check=True,
            env=env,
            cwd=ROOT,
        )
        dest = home / ".claude" / "skills" / "usage-trace"
        assert dest.is_symlink() or (dest / "SKILL.md").is_file()
        assert (dest / "SKILL.md").is_file()

        subprocess.run(
            [_bash(), str(INSTALL_SKILL), "--skip-cli", "--copy", "cursor-user"],
            check=True,
            env=env,
            cwd=ROOT,
        )
        copy_dest = home / ".cursor" / "skills" / "usage-trace" / "SKILL.md"
        assert copy_dest.is_file()
        assert not (home / ".cursor" / "skills" / "usage-trace").is_symlink()


def test_sync_plugin_copies_is_idempotent():
    subprocess.run([_bash(), str(SYNC)], check=True, cwd=ROOT)
    src = (ROOT / "skills" / "usage-trace" / "SKILL.md").read_text(encoding="utf-8")
    dst = (ROOT / "plugins" / "usage-trace" / "skills" / "usage-trace" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert src == dst