from common import add_node, load_profile, new_graph
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


def test_resolves_multiple_mybatis_tables_and_operations(tmp_path, profiles_dir):
    mapper_dir = tmp_path / "src/main/resources/mapper"
    mapper_dir.mkdir(parents=True)
    (mapper_dir / "OrderMapper.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.example.mapper.OrderMapper">
  <select id="selectWithStore" resultType="object">
    SELECT * FROM t_order o JOIN t_store s ON s.id = o.store_id WHERE o.store_no = #{storeNo}
  </select>
  <update id="updateByStoreNo">
    UPDATE t_order SET status = #{status} WHERE store_no = #{storeNo}
  </update>
</mapper>
""",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    g = new_graph({})
    add_node(g, {
        "id": "OrderMapper.selectWithStore",
        "kind": "unit",
        "label": "OrderMapper.selectWithStore",
        "layer": "Repository",
    })
    add_node(g, {
        "id": "OrderMapper.updateByStoreNo",
        "kind": "unit",
        "label": "OrderMapper.updateByStoreNo",
        "layer": "Repository",
    })

    resolve_tables(g, tmp_path, profile)

    by_table = {n["table"]: n for n in g["nodes"] if n["kind"] == "table"}
    assert set(by_table) == {"t_order", "t_store"}
    assert by_table["t_order"]["ops"] == ["select", "update"]
    assert by_table["t_store"]["ops"] == ["select"]
    ref_edges = [e for e in g["edges"] if e["kind"] == "references"]
    assert len(ref_edges) == 3


def test_resolves_jpa_repository_entity_table(tmp_path, profiles_dir):
    java_dir = tmp_path / "src/main/java/com/example"
    (java_dir / "entity").mkdir(parents=True)
    (java_dir / "repository").mkdir(parents=True)
    (java_dir / "entity/OrderEntity.java").write_text(
        """package com.example.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "t_order")
public class OrderEntity {
}
""",
        encoding="utf-8",
    )
    repo = java_dir / "repository/OrderRepository.java"
    repo.write_text(
        """package com.example.repository;

import com.example.entity.OrderEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderRepository extends JpaRepository<OrderEntity, Long> {
    Object findByStoreNo(String storeNo);
}
""",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    g = new_graph({})
    add_node(g, {
        "id": "OrderRepository.findByStoreNo",
        "kind": "unit",
        "label": "OrderRepository.findByStoreNo",
        "layer": "Repository",
        "file": str(repo),
    })

    resolve_tables(g, tmp_path, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert len(table_nodes) == 1
    assert table_nodes[0]["table"] == "t_order"
    assert table_nodes[0]["ops"] == ["select"]
    assert any(e["from"] == "OrderRepository.findByStoreNo" for e in g["edges"])


def test_resolves_mybatis_annotation_sql(tmp_path, profiles_dir):
    mapper_dir = tmp_path / "src/main/java/com/example/mapper"
    mapper_dir.mkdir(parents=True)
    mapper = mapper_dir / "OrderMapper.java"
    mapper.write_text(
        """package com.example.mapper;

public interface OrderMapper {
    @org.apache.ibatis.annotations.Select("SELECT * FROM t_order WHERE store_no = #{storeNo}")
    Object selectByStoreNo(String storeNo);
}
""",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    g = new_graph({})
    add_node(g, {
        "id": "OrderMapper.selectByStoreNo",
        "kind": "unit",
        "label": "OrderMapper.selectByStoreNo",
        "layer": "Repository",
        "file": str(mapper),
    })

    resolve_tables(g, tmp_path, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert len(table_nodes) == 1
    assert table_nodes[0]["table"] == "t_order"
    assert table_nodes[0]["ops"] == ["select"]


def test_resolves_raw_sql_files_with_keyword_usage(tmp_path, profiles_dir):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "orders_by_store.sql").write_text(
        "SELECT * FROM t_order WHERE store_no = :storeNo;\n",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    g = new_graph({})
    add_node(g, {
        "id": "OrderService.findByStoreNo",
        "kind": "unit",
        "label": "OrderService.findByStoreNo",
        "layer": "Service",
        "usages": [{"snippet": "return runSql(\"storeNo\");"}],
    })

    resolve_tables(g, tmp_path, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert len(table_nodes) == 1
    assert table_nodes[0]["table"] == "t_order"
    assert table_nodes[0]["ops"] == ["select"]
    assert any(e["from"] == "OrderService.findByStoreNo" for e in g["edges"])


def test_resolves_raw_sql_files_from_unit_name_terms(tmp_path, profiles_dir):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "orders_by_store.sql").write_text(
        "SELECT * FROM t_order WHERE store_no = :storeNo;\n",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    g = new_graph({})
    add_node(g, {
        "id": "OrderService.findByStoreNo",
        "kind": "unit",
        "label": "OrderService.findByStoreNo",
        "layer": "Service",
    })

    resolve_tables(g, tmp_path, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert len(table_nodes) == 1
    assert table_nodes[0]["table"] == "t_order"


def test_raw_sql_does_not_match_only_on_generic_class_or_table_terms(tmp_path, profiles_dir):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "orders_by_store.sql").write_text(
        "SELECT * FROM t_order WHERE store_no = :storeNo;\n",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    g = new_graph({})
    add_node(g, {
        "id": "OrderService.findByCustomerId",
        "kind": "unit",
        "label": "OrderService.findByCustomerId",
        "layer": "Service",
    })

    resolve_tables(g, tmp_path, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert table_nodes == []
