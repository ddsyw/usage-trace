import json
import re
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
    d = add_node(g, {
        "kind": "table",
        "label": "t_order",
        "layer": "Table",
        "table": "t_order",
        "op": "select",
        "source_files": ["src/main/resources/mapper/OrderMapper.xml"],
        "sql_snippet": "SELECT * FROM t_order WHERE store_no = #{storeNo}",
    })
    g["db_statements"] = [{
        "source": "mybatis_xml",
        "file": "src/main/resources/mapper/OrderMapper.xml",
        "statement_id": "OrderMapper.selectByStoreNo",
        "op": "select",
        "tables": ["t_order"],
        "sql": "SELECT * FROM t_order WHERE store_no = #{storeNo}",
        "linked": True,
    }]
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


def test_svg_wraps_layers_in_group_frames():
    svg = render_svg(_fixture_graph())

    assert 'class="graph-group node-controller"' in svg
    assert 'class="graph-group node-service"' in svg
    assert 'class="graph-group node-repository"' in svg
    assert 'class="graph-group node-table"' in svg
    assert 'class="group-frame"' in svg
    assert 'data-layer="Controller"' in svg
    assert 'data-layer="Table"' in svg
    assert "Controller · 1" in svg
    assert "Table · 1" in svg
    assert svg.index('class="graph-group') < svg.index('class="graph-edge')


def test_render_single_file_html():
    html = render(_fixture_graph(), "storeNo",
                  {"project": "demo", "language": "java-spring"}, TMPL)
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>usage-trace" in html
    assert "storeNo" in html and "t_order" in html
    assert "XML / SQL 来源" in html
    assert "OrderMapper.xml" in html
    assert "http://" not in html and "https://" not in html  # offline single file
    assert "<svg" in html
    assert 'id="graph-data"' in html
    assert 'id="graph-search"' in html
    assert 'id="node-details"' in html
    assert 'data-node-id="' in html
    assert "fitGraph" in html


def test_render_includes_main_path_and_focus_controls():
    html = render(_fixture_graph(), "storeNo",
                  {"project": "demo", "language": "java-spring"}, TMPL)

    assert "主路径" in html
    assert 'class="path-lane"' in html
    assert 'id="view-main"' in html
    assert 'id="view-all"' in html
    assert "导览" in html
    assert "层间关系" in html
    assert "applyFocus" in html
    assert "applyMainPathView" in html

    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    payload = json.loads(m.group(1))
    assert payload["layers"][0]["id"] == "layer:controller"
    assert payload["layer_edges"][0]["edgeTypes"] == ["calls"]
    assert payload["tour"][0]["title"] == "主路径"
    assert len(payload["main_paths"]) == 1
    assert payload["main_paths"][0]["labels"] == [
        "OrderController.queryByStoreNo",
        "OrderService.findByStoreNo",
        "OrderMapper.selectByStoreNo",
        "t_order",
    ]


def test_render_includes_layer_tabs_for_full_graph_filtering():
    html = render(_fixture_graph(), "storeNo",
                  {"project": "demo", "language": "java-spring"}, TMPL)

    assert '<section class="panel-section layer-tabs-section">' in html
    assert 'class="layer-tabs"' in html
    assert 'class="layer-tab active"' in html
    assert 'data-layer="all"' in html
    assert 'data-layer="Controller"' in html
    assert 'data-layer="Service"' in html
    assert 'data-layer="Repository"' in html
    assert 'data-layer="Table"' in html
    assert "activeLayer" in html
    assert "selectLayerTab" in html
    assert "applyLayerTabs" in html
    assert html.index('<section class="panel-section layer-tabs-section">') < html.index(
        '<section class="graph-stage">'
    )


def test_render_includes_table_node_detail_panel_support():
    html = render(_fixture_graph(), "storeNo",
                  {"project": "demo", "language": "java-spring"}, TMPL)

    assert "renderTableDetails" in html
    assert "表详情" in html
    assert "访问操作" in html
    assert "Statement" in html
    assert "SQL 片段" in html


def test_render_shows_unlinked_xml_table_candidates():
    g = new_graph({})
    add_node(g, {"kind": "unit", "label": "OrderService.findByStoreNo", "layer": "Service"})
    g["db_statements"] = [{
        "source": "mybatis_xml",
        "file": "src/main/resources/mappers/OrderMapper.xml",
        "statement_id": "OrderMapper.selectByStoreNo",
        "op": "select",
        "tables": ["t_order"],
        "sql": "SELECT * FROM t_order WHERE store_no = #{storeNo}",
        "linked": False,
        "skip_reason": "not in traced call chain",
    }]
    prune_and_layout(g, 300, ["Controller", "Service", "Repository", "Table"])

    html = render(g, "storeNo", {"project": "demo", "language": "java-spring"}, TMPL)

    assert "候选表" in html
    assert "t_order" in html
    assert "未连接" in html
    assert "OrderMapper.xml" in html


def test_panorama_present_and_renderable():
    g = _fixture_graph()
    svg = render_panorama_svg(g)
    assert "<circle" in svg and "t_order" in svg
    html = render(g, "storeNo", {"project": "demo", "language": "java-spring"}, TMPL)
    assert "<details" in html and "网络全景" in html


def test_template_file_exists():
    assert TMPL.exists()
