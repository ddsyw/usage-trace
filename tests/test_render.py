from pathlib import Path

from common import new_graph, add_node, add_edge
from graph import prune_and_layout
from render import render, render_svg, render_panorama_svg

TMPL = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


def _fixture_graph():
    g = new_graph({})
    a = add_node(g, {"kind": "unit", "label": "OrderController.queryByStoreNo", "layer": "Controller"})
    b = add_node(g, {"kind": "unit", "label": "OrderService.findByStoreNo", "layer": "Service"})
    c = add_node(g, {"kind": "unit", "label": "OrderMapper.selectByStoreNo", "layer": "Repository"})
    d = add_node(g, {"kind": "table", "label": "t_order", "layer": "Table", "table": "t_order", "op": "select"})
    add_edge(g, a, b)
    add_edge(g, b, c)
    add_edge(g, c, d, "references")
    prune_and_layout(g, 300, ["Controller", "Service", "Repository", "Table"])
    return g


def test_svg_contains_nodes_and_edge():
    svg = render_svg(_fixture_graph())
    assert "OrderController.queryByStoreNo" in svg
    assert "t_order" in svg
    assert "<path" in svg  # an edge


def test_render_single_file_html():
    html = render(_fixture_graph(), "storeNo",
                  {"project": "demo", "language": "java-spring"}, TMPL)
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>usage-trace" in html
    assert "storeNo" in html and "t_order" in html
    assert "http://" not in html and "https://" not in html  # offline single file
    assert "<svg" in html


def test_panorama_present_and_renderable():
    g = _fixture_graph()
    svg = render_panorama_svg(g)
    assert "<circle" in svg and "t_order" in svg
    html = render(g, "storeNo", {"project": "demo", "language": "java-spring"}, TMPL)
    assert "<details" in html and "网络全景" in html


def test_template_file_exists():
    assert TMPL.exists()
