from pathlib import Path

from common import load_profile, new_graph
from discover import discover
from index import ProjectIndex
from trace import trace
from tables import resolve_tables
from graph import prune_and_layout
from render import render

TMPL = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


def test_full_pipeline_on_fixture(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    profile.setdefault("profile", "java-spring")
    index = ProjectIndex.load_or_build(fixture_root, profile)
    usages = discover("storeNo", profile, index=index)
    assert usages, "expected usage sites in fixture"

    g = trace(usages, index, profile, depth=4)
    g = resolve_tables(g, index, profile)
    g = prune_and_layout(g, max_nodes=300,
                         layer_order=["Controller", "Service", "Repository", "Table"])

    html = render(g, "storeNo",
                  {"project": "fixture", "language": "java-spring",
                   "generated_at": "2026-07-03T12:00:00"}, TMPL)

    assert "<svg" in html
    assert "storeNo" in html
    assert "t_order" in html
    for unit in ["OrderController.queryByStoreNo",
                 "OrderService.findByStoreNo",
                 "OrderMapper.selectByStoreNo"]:
        assert unit in html
    assert "http://" not in html and "https://" not in html  # offline single file


def test_zero_hit_still_renders(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    profile.setdefault("profile", "java-spring")
    index = ProjectIndex.load_or_build(fixture_root, profile)
    usages = discover("___no_such_keyword___", profile, index=index)
    assert usages == []
    g = new_graph({"depth": 4})
    prune_and_layout(g, 300, ["Controller", "Service", "Repository", "Table"])
    html = render(g, "___no_such_keyword___",
                  {"project": "fixture", "language": "java-spring",
                   "generated_at": "2026-07-03T12:00:00"}, TMPL)
    assert "<svg" in html and "无涉及表" in html
