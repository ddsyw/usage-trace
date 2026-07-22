"""Shared utilities: profile loading, graph schema IO, grep wrapper (rg or pure Python)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - import guard
    yaml = None


# ---- Profile loading ----
def load_profile(name: str, profiles_dir: Path | None = None) -> dict:
    """Load a language profile YAML by name ('java-spring') or by path."""
    p = Path(name)
    if not p.is_absolute() and not p.exists() and profiles_dir is not None:
        for ext in (".yml", ".yaml"):
            cand = Path(profiles_dir) / f"{name}{ext}"
            if cand.exists():
                p = cand
                break
    if not p.exists():
        raise FileNotFoundError(f"profile not found: {name}")
    if yaml is None:
        raise RuntimeError("PyYAML is required to load profiles: pip install pyyaml")
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---- Graph schema IO ----
def new_graph(meta: dict | None = None) -> dict:
    return {"meta": meta or {}, "nodes": [], "edges": []}


def add_node(g: dict, node: dict) -> str:
    if not node.get("id"):
        node["id"] = f"n{len(g['nodes']) + 1}"
    g["nodes"].append(node)
    return node["id"]


def add_edge(g: dict, frm: str, to: str, kind: str = "call",
             confidence: str = "confirmed") -> dict:
    e = {"from": frm, "to": to, "kind": kind, "confidence": confidence}
    g["edges"].append(e)
    return e


def dump_graph(g: dict) -> str:
    return json.dumps(g, ensure_ascii=False, indent=2)


def load_graph(s: str | bytes) -> dict:
    if isinstance(s, bytes):
        s = s.decode("utf-8")
    return json.loads(s)


# ---- Layer classification ----
def _annotation_match(pattern: str, text: str) -> bool:
    annotations = {f"@{m.group(1)}" for m in re.finditer(r"@(?:[\w.]+\.)?(\w+)", text)}
    for part in re.split(r"\|", pattern):
        token = part.strip("() ")
        if token.startswith("@") and token in annotations:
            return True
    return False


def _path_hint_match(fpath: str, hint: str) -> bool:
    """Match path_hint against path *segments*, not the raw full path.

    Full-path search false-positives on project/module names such as
    ``common-entry-service`` matching ``service`` (hyphen is a regex word
    boundary). Segment fullmatch keeps ``.../service/Foo.java`` and
    ``.../dao/Bar.java`` while ignoring hyphenated parent folders.
    """
    if not hint:
        return False
    parts: list[str] = []
    for part in fpath.replace("\\", "/").split("/"):
        if not part:
            continue
        parts.append(part)
        if "." in part:
            parts.append(part.rsplit(".", 1)[0])
    try:
        rx = re.compile(rf"^(?:{hint})$", re.IGNORECASE)
    except re.error:
        rx = re.compile("^" + re.escape(hint) + "$", re.IGNORECASE)
    return any(rx.match(part) for part in parts)


def classify_layer(file: str, layers: list[dict], text: str | None = None) -> str:
    """Classify a source file by ordered layer path hints and optional content matches."""
    fpath = str(file).replace("\\", "/")
    text = text or ""
    for layer in layers:
        hint = layer.get("path_hint")
        match = layer.get("match")
        if hint and _path_hint_match(fpath, hint):
            return layer["name"]
        if match and (re.search(match, text) or _annotation_match(match, text)):
            return layer["name"]
    return "Other"



# ---- Grep wrapper ----
def has_ripgrep() -> bool:
    return shutil.which("rg") is not None


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(2048)
    except OSError:
        return True


def grep(pattern: str, root: Path, glob: str = "*",
         exclude_dirs: Iterable[str] = ()) -> list[dict]:
    """Search text files under root for regex `pattern`. Returns [{file, line, col, text}]."""
    root = Path(root)
    excludes = set(exclude_dirs)
    if has_ripgrep():
        try:
            return _grep_rg(pattern, root, excludes)
        except FileNotFoundError:
            pass
    return _grep_py(pattern, root, excludes)


def _grep_rg(pattern: str, root: Path, excludes: set[str]) -> list[dict]:
    cmd = ["rg", "--line-number", "--column", "--no-heading", "--color=never"]
    for d in excludes:
        cmd += ["--glob", f"!{d}/**"]
    cmd += [pattern, str(root)]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    results = []
    for line in out.stdout.splitlines():
        m = re.match(r"^(.*?):(\d+):(\d+):(.*)$", line)
        if m:
            results.append({"file": m.group(1), "line": int(m.group(2)),
                            "col": int(m.group(3)), "text": m.group(4)})
    return results


def _grep_py(pattern: str, root: Path, excludes: set[str]) -> list[dict]:
    rx = re.compile(pattern)
    results: list[dict] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in excludes for part in path.parts):
            continue
        if _is_binary(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    m = rx.search(line)
                    if m:
                        results.append({"file": str(path), "line": i,
                                        "col": m.start() + 1,
                                        "text": line.rstrip("\n")})
        except OSError:
            continue
    return results
