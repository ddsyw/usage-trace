"""Single-command orchestration for usage-trace reports."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

def _prefer_local_modules() -> None:
    module_dir = str(Path(__file__).resolve().parent)
    if sys.path[0:1] == [module_dir]:
        return
    try:
        sys.path.remove(module_dir)
    except ValueError:
        pass
    sys.path.insert(0, module_dir)


_prefer_local_modules()

from common import load_profile, new_graph  # noqa: E402
from discover import discover  # noqa: E402
from graph import prune_and_layout  # noqa: E402
from render import render  # noqa: E402
from tables import resolve_tables  # noqa: E402
from trace import HARD_DEPTH_CAP, trace  # noqa: E402


def _profile_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "profiles"


def _template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


def _layer_order(profile: dict) -> list[str]:
    order = [layer["name"] for layer in profile.get("layers", [])]
    return order + [name for name in ("Table", "Other") if name not in order]


def detect_profile_name(root: Path | str) -> str:
    root = Path(root)
    java_markers = ("pom.xml", "build.gradle", "settings.gradle")
    if any((root / marker).exists() for marker in java_markers) or any(root.rglob("*.java")):
        for java in root.rglob("*.java"):
            try:
                text = java.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "org.springframework" in text or "@RestController" in text or "@Service" in text:
                return "java-spring"
        return "java-generic"

    py_markers = ("pyproject.toml", "setup.py", "requirements.txt", "Pipfile")
    if any((root / marker).exists() for marker in py_markers) or any(root.rglob("*.py")):
        for py in list(root.rglob("*.py"))[:80]:
            try:
                text = py.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            low = text.lower()
            if "sqlalchemy" in low or "flask_sqlalchemy" in low:
                return "python-sqlalchemy"
        return "python-generic"

    cs_markers = list(root.glob("*.csproj")) + list(root.glob("*.sln"))
    if cs_markers or any(root.rglob("*.cs")):
        for cs in list(root.rglob("*.cs"))[:80]:
            try:
                text = cs.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "Microsoft.EntityFrameworkCore" in text or "DbContext" in text or "[Table(" in text:
                return "csharp-ef"
        return "csharp-generic"

    return "java-generic"


def run(keyword: str, root: Path | str, profile_name: str = "auto",
        depth: int = 4, max_nodes: int = 300, out: Path | str | None = None,
        variants: list[str] | None = None) -> dict:
    root = Path(root)
    profile_name = detect_profile_name(root) if profile_name == "auto" else profile_name
    profile = load_profile(profile_name, _profile_dir())
    profile.setdefault("profile", profile_name)

    from index import ProjectIndex
    index = ProjectIndex.load_or_build(root, profile)

    usages = discover(keyword, profile, variants, index)
    if usages:
        graph = trace(usages, index, profile, depth)
    else:
        graph = new_graph({"depth": min(depth, HARD_DEPTH_CAP)})
    graph["meta"]["profile"] = profile_name
    graph = resolve_tables(graph, index, profile)
    graph = prune_and_layout(graph, max_nodes, _layer_order(profile))

    output = Path(out) if out is not None else Path(".usage-trace") / f"{keyword}-report.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "project": root.name,
        "language": profile_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output.write_text(render(graph, keyword, meta, _template_path()), encoding="utf-8")
    return graph


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Trace a keyword and render an offline HTML report.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", default="auto")
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--max-nodes", type=int, default=300)
    ap.add_argument("--variants", default="", help="comma-separated extra variants")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    run(args.keyword, args.root, args.profile, args.depth, args.max_nodes, args.out, variants)


if __name__ == "__main__":
    main()
