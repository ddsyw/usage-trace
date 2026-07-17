from parsing import JavaParser, FileSymbols


JAVA_BASIC = """\
package com.example.service;

public class OrderService {
    private final OrderMapper orderMapper;

    public OrderService(OrderMapper orderMapper) {
        this.orderMapper = orderMapper;
    }

    public Object findByStoreNo(String storeNo) {
        return orderMapper.selectByStoreNo(storeNo);
    }
}
"""


def test_parse_methods_fields_calls():
    sym = JavaParser().parse(JAVA_BASIC, "OrderService.java")
    assert isinstance(sym, FileSymbols)
    quals = {m.qual for m in sym.methods}
    assert "OrderService.findByStoreNo" in quals
    assert "OrderService.OrderService" in quals  # constructor

    fields = {(f.cls, f.name, f.type) for f in sym.fields}
    assert ("OrderService", "orderMapper", "OrderMapper") in fields

    calls = {(c.callee_name, c.receiver) for c in sym.calls}
    assert ("selectByStoreNo", "orderMapper") in calls


def test_parse_method_span_ignores_braces_in_strings_and_block_comments():
    # The #6 regression: a "}" inside a string literal and a block comment must
    # NOT skew the method end line. A naive brace counter ends the method early.
    src = """
public class EdgeCaseService {
    public void tricky(String storeNo) {
        String s = "}{ not a real brace ";
        /* } another fake brace } */
        doWork(storeNo);
    }

    public void after() {
        other();
    }
}
"""
    sym = JavaParser().parse(src, "EdgeCaseService.java")
    by_name = {m.name: m for m in sym.methods}
    # `tricky` body is lines 3-7 (1-indexed). end_line must reach the real closing brace.
    assert by_name["tricky"].start_line == 3
    assert by_name["tricky"].end_line == 7
    # `after` is still parsed -> proves the string/comment braces didn't terminate tricky early
    assert "after" in by_name
    assert any(c.callee_name == "doWork" for c in sym.calls)


def test_parse_inheritance():
    src = "public class Foo extends Bar implements Baz, Qux { void x() {} }"
    sym = JavaParser().parse(src, "Foo.java")
    assert "Bar" in sym.inheritance.get("Foo", [])
    assert "Baz" in sym.inheritance["Foo"]
    assert "Qux" in sym.inheritance["Foo"]


def test_filesymbols_roundtrip():
    sym = JavaParser().parse(JAVA_BASIC, "OrderService.java")
    d = sym.to_dict()
    sym2 = FileSymbols.from_dict(d)
    assert {m.qual for m in sym.methods} == {m.qual for m in sym2.methods}
    assert {f.name for f in sym.fields} == {f.name for f in sym2.fields}
