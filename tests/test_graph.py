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
    add_edge(g, a, b)
    add_edge(g, b, c)
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


def test_truncation_preserves_table_reference_nodes():
    g = new_graph({})
    seed = add_node(g, {
        "id": "Controller.entry",
        "kind": "unit",
        "label": "Controller.entry",
        "layer": "Controller",
        "usages": [{"file": "Controller.java", "line": 1}],
    })
    for i in range(20):
        extra = add_node(g, {
            "id": f"Service.extra{i}",
            "kind": "unit",
            "label": f"Service.extra{i}",
            "layer": "Service",
        })
        add_edge(g, seed, extra)
    repo = add_node(g, {
        "id": "StoreMapper.selectByStoreNo",
        "kind": "unit",
        "label": "StoreMapper.selectByStoreNo",
        "layer": "Repository",
    })
    table = add_node(g, {
        "id": "table:store",
        "kind": "table",
        "label": "store",
        "layer": "Table",
        "table": "store",
    })
    add_edge(g, seed, repo)
    add_edge(g, repo, table, "references")

    prune_and_layout(g, max_nodes=5)

    ids = {n["id"] for n in g["nodes"]}
    assert "StoreMapper.selectByStoreNo" in ids
    assert "table:store" in ids
    assert any(e["from"] == repo and e["to"] == table for e in g["edges"])


def test_no_truncation_under_cap():
    g = _big_graph(50)
    prune_and_layout(g, max_nodes=300)
    assert g["meta"].get("truncated") is None
    assert len(g["nodes"]) == 50
