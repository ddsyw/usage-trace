from common import load_profile
from discover import discover
from trace import trace
from tables import resolve_tables


def test_resolves_t_order_from_mybatis(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", fixture_root, profile)
    g = trace(usages, fixture_root, profile, depth=4)
    g = resolve_tables(g, fixture_root, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert any(n["table"] == "t_order" for n in table_nodes)
    t = next(n for n in table_nodes if n["table"] == "t_order")
    assert t["op"] == "select"
    assert t["layer"] == "Table"
    assert "store_no" in t["sql_snippet"]
    assert any(e["kind"] == "references" and e["to"] == t["id"] for e in g["edges"])
