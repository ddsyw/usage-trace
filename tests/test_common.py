from pathlib import Path

from common import (
    load_profile, grep, new_graph, add_node, add_edge, dump_graph, load_graph,
)


def test_graph_roundtrip():
    g = new_graph({"keyword": "storeNo"})
    a = add_node(g, {"kind": "unit", "label": "A.foo", "layer": "Service"})
    b = add_node(g, {"kind": "unit", "label": "A.bar", "layer": "Service"})
    add_edge(g, a, b)
    s = dump_graph(g)
    g2 = load_graph(s)
    assert len(g2["nodes"]) == 2
    assert g2["edges"][0]["from"] == a and g2["edges"][0]["to"] == b
    assert g["nodes"][0]["id"] != g["nodes"][1]["id"]


def test_grep_finds_store_no(fixture_root):
    hits = grep(r"storeNo", fixture_root, "*", ("target", "node_modules"))
    files = {Path(h["file"]).name for h in hits}
    assert "OrderController.java" in files
    assert "OrderService.java" in files
    for h in hits:
        assert h["line"] >= 1 and h["col"] >= 1 and h["text"]


def test_grep_excludes_dirs(fixture_root):
    hits = grep(r"storeNo", fixture_root, "*", ("target",))
    assert not any("target" in h["file"] for h in hits)


def test_load_profile_not_found(profiles_dir):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_profile("does-not-exist", profiles_dir)
