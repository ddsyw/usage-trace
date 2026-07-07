"""Single-command orchestration for codex-find reports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from common import load_profile, new_graph
from discover import discover
from graph import prune_and_layout
from render import render
from tables import resolve_tables
from trace import HARD_DEPTH_CAP, trace


def _profile_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "profiles"


def _template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


def _layer_order(profile: dict) -> list[str]:
    order = [layer["name"] for layer in profile.get("layers", [])]
    return order + [name for name in ("Table", "Unknown") if name not in order]


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
    return "java-generic"


def run(keyword: str, root: Path | str, profile_name: str = "auto",
        depth: int = 4, max_nodes: int = 300, out: Path | str | None = None,
        variants: list[str] | None = None) -> dict:
    root = Path(root)
    profile_name = detect_profile_name(root) if profile_name == "auto" else profile_name
    profile = load_profile(profile_name, _profile_dir())
    usages = discover(keyword, root, profile, variants)
    if usages:
        graph = trace(usages, root, profile, depth)
    else:
        graph = new_graph({"depth": min(depth, HARD_DEPTH_CAP)})
    graph["meta"]["profile"] = profile_name
    graph = resolve_tables(graph, root, profile)
    graph = prune_and_layout(graph, max_nodes, _layer_order(profile))

    output = Path(out) if out is not None else Path("output") / f"{keyword}-report.html"
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
