from common import new_graph, add_node, add_edge
from graph import prune_and_layout


def _big_graph(n):
    g = new_graph({})
    prev = None
    for i in range(n):
        nid = add_node(g, {"kind": "unit", "label": f"u{i}", "layer": "Service"})
        if prev:
            add_edge(g, prev, nid)
        prev = nid
    return g


def test_layout_assigns_col_and_row():
    g = new_graph({})
    a = add_node(g, {"kind": "unit", "label": "A", "layer": "Controller"})
    b = add_node(g, {"kind": "unit", "label": "B", "layer": "Service"})
    c = add_node(g, {"kind": "table", "label": "t", "layer": "Table"})
    add_edge(g, a, b); add_edge(g, b, c)
    prune_and_layout(g, max_nodes=300,
                     layer_order=["Controller", "Service", "Repository", "Table"])
    by_id = {n["id"]: n for n in g["nodes"]}
    assert by_id[a]["col"] == 0 and by_id[a]["row"] == 0
    assert by_id[b]["col"] == 1
    assert by_id[c]["col"] == 3   # Table column


def test_truncation_when_over_cap():
    g = _big_graph(400)
    prune_and_layout(g, max_nodes=300)
    assert len(g["nodes"]) <= 300
    assert g["meta"]["truncated"] is not None
    assert g["meta"]["truncated"]["pruned_count"] >= 100


def test_no_truncation_under_cap():
    g = _big_graph(50)
    prune_and_layout(g, max_nodes=300)
    assert g["meta"].get("truncated") is None
    assert len(g["nodes"]) == 50
