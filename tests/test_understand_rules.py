from common import add_edge, add_node, new_graph
from graph import prune_and_layout


def test_understand_rules_enrich_graph_with_layers_tour_and_aggregations():
    g = new_graph({})
    controller = add_node(g, {
        "id": "OrderController.queryByStoreNo",
        "kind": "unit",
        "label": "OrderController.queryByStoreNo",
        "layer": "Controller",
        "usages": [{"snippet": "return orderService.findByStoreNo(storeNo);"}],
    })
    service = add_node(g, {
        "id": "OrderService.findByStoreNo",
        "kind": "unit",
        "label": "OrderService.findByStoreNo",
        "layer": "Service",
    })
    mapper = add_node(g, {
        "id": "OrderMapper.selectByStoreNo",
        "kind": "unit",
        "label": "OrderMapper.selectByStoreNo",
        "layer": "Repository",
    })
    table = add_node(g, {
        "id": "table:t_order",
        "kind": "table",
        "label": "t_order",
        "layer": "Table",
        "table": "t_order",
        "op": "select",
    })
    add_edge(g, controller, service, "call")
    add_edge(g, controller, service, "call")
    add_edge(g, service, mapper, "call", "inferred")
    add_edge(g, mapper, table, "references")
    add_edge(g, mapper, "missing-node", "call")

    prune_and_layout(g, 300, ["Controller", "Service", "Repository", "Table"])

    assert len(g["edges"]) == 3
    assert all(e["to"] != "missing-node" for e in g["edges"])
    first_edge = next(e for e in g["edges"] if e["from"] == controller and e["to"] == service)
    assert first_edge["type"] == "calls"
    assert first_edge["direction"] == "forward"
    assert first_edge["weight"] == 1.0

    by_id = {n["id"]: n for n in g["nodes"]}
    assert by_id[controller]["type"] == "function"
    assert by_id[controller]["complexity"] == "moderate"
    assert "controller" in by_id[controller]["tags"]
    assert by_id[table]["type"] == "table"
    assert by_id[table]["complexity"] == "simple"

    assert [layer["id"] for layer in g["layers"]] == [
        "layer:controller",
        "layer:service",
        "layer:repository",
        "layer:table",
    ]
    assert g["layers"][0]["nodeIds"] == [controller]
    assert g["layer_edges"][0] == {
        "sourceLayerId": "layer:controller",
        "targetLayerId": "layer:service",
        "count": 1,
        "edgeTypes": ["calls"],
    }
    assert g["main_paths"][0]["nodes"] == [controller, service, mapper, table]
    assert g["tour"][0]["title"] == "主路径"
    assert g["tour"][0]["nodeIds"] == [controller, service, mapper, table]
    assert g["meta"]["understand_rules"]["dropped_edges"] == 1
    assert g["meta"]["understand_rules"]["deduped_edges"] == 1
