"""tree-sitter-backed source extraction. P1 ships Java; LANGUAGES is the P4 extension point."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Language, Parser


@dataclass
class MethodSymbol:
    name: str
    qual: str
    file: str
    start_line: int   # 1-indexed
    end_line: int     # 1-indexed, inclusive
    params: dict[str, str]  # param name -> type
    cls: str


@dataclass
class FieldSymbol:
    cls: str
    name: str
    type: str


@dataclass
class CallSite:
    caller_qual: str
    callee_name: str
    receiver: str | None  # receiver var name when `<expr>.name(`, else None
    file: str
    line: int


@dataclass
class FileSymbols:
    methods: list[MethodSymbol] = field(default_factory=list)
    fields: list[FieldSymbol] = field(default_factory=list)
    inheritance: dict[str, list[str]] = field(default_factory=dict)
    calls: list[CallSite] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "methods": [m.__dict__ for m in self.methods],
            "fields": [f.__dict__ for f in self.fields],
            "inheritance": {k: list(v) for k, v in self.inheritance.items()},
            "calls": [c.__dict__ for c in self.calls],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileSymbols":
        return cls(
            methods=[MethodSymbol(**m) for m in d.get("methods", [])],
            fields=[FieldSymbol(**f) for f in d.get("fields", [])],
            inheritance={k: list(v) for k, v in d.get("inheritance", {}).items()},
            calls=[CallSite(**c) for c in d.get("calls", [])],
        )


class LanguageParser:
    extension: str = ""

    def parse(self, source: str, file: str) -> FileSymbols:
        raise NotImplementedError


def parser_for(path: str) -> LanguageParser | None:
    cls = LANGUAGES.get(Path(path).suffix)
    return cls() if cls else None


class JavaParser(LanguageParser):
    extension = ".java"
    _parser: Parser | None = None

    @classmethod
    def _ts_parser(cls) -> Parser:
        if cls._parser is None:
            import tree_sitter_java
            lang = Language(tree_sitter_java.language())
            try:
                cls._parser = Parser(lang)
            except TypeError:  # older calling convention
                p = Parser()
                p.set_language(lang)
                cls._parser = p
        return cls._parser

    def parse(self, source: str, file: str) -> FileSymbols:
        src = source.encode("utf-8")
        tree = self._ts_parser().parse(src)
        sym = FileSymbols()
        self._visit(tree.root_node, src, file, [], sym)
        return sym

    def _visit(self, node, src, file, class_stack, sym: FileSymbols) -> None:
        t = node.type
        if t in ("class_declaration", "interface_declaration", "enum_declaration",
                 "record_declaration", "annotation_type_declaration"):
            name_node = node.child_by_field_name("name")
            cls = _text(src, name_node) if name_node else (class_stack[-1] if class_stack else "")
            if cls:
                sym.inheritance.setdefault(cls, [])
                sym.inheritance[cls].extend(_supertypes(node, src))
                class_stack.append(cls)
            for c in node.children:
                self._visit(c, src, file, class_stack, sym)
            if cls:
                class_stack.pop()
            return
        if t in ("method_declaration", "constructor_declaration"):
            cls = class_stack[-1] if class_stack else ""
            name_node = node.child_by_field_name("name")
            name = _text(src, name_node) if name_node else "<init>"
            qual = f"{cls}.{name}" if cls else name
            sym.methods.append(MethodSymbol(
                name=name, qual=qual, file=file,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                params=_params(node, src), cls=cls))
            _collect_calls(node, src, file, qual, sym)
            return
        if t == "field_declaration":
            cls = class_stack[-1] if class_stack else ""
            type_node = node.child_by_field_name("type")
            ftype = _text(src, type_node) if type_node else ""
            for decl in _iter_declarators(node):
                vname = decl.child_by_field_name("name")
                if vname:
                    sym.fields.append(FieldSymbol(cls, _text(src, vname), ftype))
            for c in node.children:
                self._visit(c, src, file, class_stack, sym)
            return
        for c in node.children:
            self._visit(c, src, file, class_stack, sym)


def _text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace") if node else ""


# Node types that represent a (named) type we want to record as a supertype.
# Capturing the whole node text preserves generics, e.g. `List<String>`.
_TYPE_NODE_KINDS = ("type_identifier", "scoped_type_identifier", "generic_type")


def _collect_type_names(node, src, out: list[str]) -> None:
    # Recursively gather type-like nodes within a `superclass` / `super_interfaces`
    # subtree. tree-sitter-java 0.23 wraps the extends name in a `superclass` node
    # (which also includes the `extends` keyword) and the implements list in
    # `super_interfaces` -> `type_list` -> `type_identifier`*; a flat
    # `child_by_field_name` walk misses them, so recurse and stop at type nodes
    # (don't descend into a generic_type's inner type_identifier to avoid dupes).
    for c in node.children:
        if c.type in _TYPE_NODE_KINDS:
            out.append(_text(src, c))
        else:
            _collect_type_names(c, src, out)


def _supertypes(class_node, src) -> list[str]:
    """Collect extends/implements types for class *and* interface declarations.

    tree-sitter-java exposes:
      - class: named fields ``superclass`` / ``interfaces`` (→ super_interfaces)
      - interface: child node ``extends_interfaces`` (not a named field)
    """
    supers: list[str] = []
    seen: set[int] = set()

    def add_from(node) -> None:
        if node is None or id(node) in seen:
            return
        seen.add(id(node))
        _collect_type_names(node, src, supers)

    add_from(class_node.child_by_field_name("superclass"))
    add_from(class_node.child_by_field_name("interfaces"))
    for c in class_node.children:
        if c.type in ("extends_interfaces", "super_interfaces", "superclass"):
            add_from(c)
    return supers


def _params(method_node, src) -> dict[str, str]:
    out: dict[str, str] = {}
    pl = method_node.child_by_field_name("parameters")
    if not pl:
        return out
    for c in pl.children:
        if c.type == "formal_parameter":
            tnode = c.child_by_field_name("type")
            nnode = c.child_by_field_name("name")
            if tnode and nnode:
                out[_text(src, nnode)] = _text(src, tnode)
    return out


def _iter_declarators(field_node):
    # Robust to grammar layout: field_declaration -> variable_declarator_list -> variable_declarator
    for c in field_node.children:
        if c.type == "variable_declarator":
            yield c
        for gc in c.children:
            if gc.type == "variable_declarator":
                yield gc


def _receiver_name(obj_node, src) -> str | None:
    """Normalize call receivers for resolution.

    - orderMapper.select -> orderMapper
    - this.orderMapper.select / field_access -> field name
    - this.run / super.run -> this / super
    - chained svc.repo().query -> None (unknown intermediate type)
    """
    if obj_node is None:
        return None
    t = obj_node.type
    if t == "identifier":
        return _text(src, obj_node)
    if t in ("this", "super"):
        return t
    if t == "field_access":
        field = obj_node.child_by_field_name("field")
        if field is not None:
            return _text(src, field)
        # last identifier in the access chain
        for c in reversed(list(obj_node.children)):
            if c.type == "identifier":
                return _text(src, c)
        return None
    return None


def _collect_calls(method_node, src, file, caller_qual, sym: FileSymbols) -> None:
    stack = list(method_node.children)
    while stack:
        n = stack.pop()
        if n.type == "method_invocation":
            name_node = n.child_by_field_name("name")
            obj_node = n.child_by_field_name("object")
            callee = _text(src, name_node)
            receiver = _receiver_name(obj_node, src)
            if callee:
                sym.calls.append(CallSite(caller_qual, callee, receiver, file, n.start_point[0] + 1))
        stack.extend(n.children)




def _make_ts_parser(lang_mod) -> Parser:
    lang = Language(lang_mod.language())
    try:
        return Parser(lang)
    except TypeError:  # older calling convention
        p = Parser()
        p.set_language(lang)
        return p


class PythonParser(LanguageParser):
    """tree-sitter-python extraction for P4."""

    extension = ".py"
    _parser: Parser | None = None

    @classmethod
    def _ts_parser(cls) -> Parser:
        if cls._parser is None:
            import tree_sitter_python
            cls._parser = _make_ts_parser(tree_sitter_python)
        return cls._parser

    def parse(self, source: str, file: str) -> FileSymbols:
        src = source.encode("utf-8")
        tree = self._ts_parser().parse(src)
        sym = FileSymbols()
        self._visit(tree.root_node, src, file, [], sym)
        return sym

    def _visit(self, node, src, file, class_stack, sym: FileSymbols) -> None:
        t = node.type
        if t == "class_definition":
            name_node = node.child_by_field_name("name")
            cls = _text(src, name_node) if name_node else (class_stack[-1] if class_stack else "")
            if cls:
                sym.inheritance.setdefault(cls, [])
                for c in node.children:
                    if c.type == "argument_list":
                        for arg in c.children:
                            if arg.type in ("identifier", "attribute"):
                                base = _text(src, arg).split(".")[-1]
                                if base and base not in sym.inheritance[cls]:
                                    sym.inheritance[cls].append(base)
                class_stack.append(cls)
            for c in node.children:
                self._visit(c, src, file, class_stack, sym)
            if cls:
                class_stack.pop()
            return
        if t == "function_definition":
            cls = class_stack[-1] if class_stack else ""
            name_node = node.child_by_field_name("name")
            name = _text(src, name_node) if name_node else "<lambda>"
            qual = f"{cls}.{name}" if cls else name
            params: dict[str, str] = {}
            params_node = node.child_by_field_name("parameters")
            if params_node is not None:
                for c in params_node.children:
                    if c.type == "identifier":
                        pname = _text(src, c)
                        if pname and pname != "self":
                            params[pname] = ""
                    elif c.type == "typed_parameter":
                        idn = next((x for x in c.children if x.type == "identifier"), None)
                        typ = c.child_by_field_name("type")
                        if idn is not None:
                            pname = _text(src, idn)
                            if pname and pname != "self":
                                params[pname] = _text(src, typ) if typ is not None else ""
                    elif c.type == "default_parameter":
                        idn = c.child_by_field_name("name")
                        if idn is not None:
                            pname = _text(src, idn)
                            if pname and pname != "self":
                                params[pname] = ""
            sym.methods.append(MethodSymbol(
                name=name, qual=qual, file=file,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                params=params, cls=cls,
            ))
            self._collect_calls(node, src, file, qual, sym)
            return
        if t == "assignment" and class_stack:
            # simple class attributes: self.x is not here; `repo = ...` rare.
            left = node.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                name = _text(src, left)
                if name and not name.startswith("_"):
                    sym.fields.append(FieldSymbol(cls=class_stack[-1], name=name, type=""))
        for c in node.children:
            self._visit(c, src, file, class_stack, sym)

    def _collect_calls(self, method_node, src, file, caller_qual, sym: FileSymbols) -> None:
        stack = list(method_node.children)
        while stack:
            n = stack.pop()
            if n.type == "call":
                fn = n.child_by_field_name("function")
                callee, receiver = _py_callee_receiver(fn, src)
                if callee:
                    sym.calls.append(CallSite(caller_qual, callee, receiver, file, n.start_point[0] + 1))
            stack.extend(n.children)


def _py_callee_receiver(fn_node, src) -> tuple[str | None, str | None]:
    if fn_node is None:
        return None, None
    if fn_node.type == "identifier":
        return _text(src, fn_node), None
    if fn_node.type == "attribute":
        attr = fn_node.child_by_field_name("attribute")
        obj = fn_node.child_by_field_name("object")
        callee = _text(src, attr) if attr is not None else None
        receiver = None
        if obj is not None:
            if obj.type == "identifier":
                receiver = _text(src, obj)
            elif obj.type == "attribute":
                # self.repo.select -> receiver repo (innermost attribute name before call)
                inner_attr = obj.child_by_field_name("attribute")
                if inner_attr is not None:
                    receiver = _text(src, inner_attr)
                else:
                    receiver = _text(src, obj).split(".")[-1]
            elif obj.type == "call":
                receiver = None
        return callee, receiver
    return None, None


class CSharpParser(LanguageParser):
    """tree-sitter-c-sharp extraction for P4."""

    extension = ".cs"
    _parser: Parser | None = None

    @classmethod
    def _ts_parser(cls) -> Parser:
        if cls._parser is None:
            import tree_sitter_c_sharp
            cls._parser = _make_ts_parser(tree_sitter_c_sharp)
        return cls._parser

    def parse(self, source: str, file: str) -> FileSymbols:
        src = source.encode("utf-8")
        tree = self._ts_parser().parse(src)
        sym = FileSymbols()
        self._visit(tree.root_node, src, file, [], sym)
        return sym

    def _visit(self, node, src, file, class_stack, sym: FileSymbols) -> None:
        t = node.type
        if t in ("class_declaration", "interface_declaration", "struct_declaration", "record_declaration"):
            name_node = node.child_by_field_name("name")
            cls = _text(src, name_node) if name_node else (class_stack[-1] if class_stack else "")
            if cls:
                sym.inheritance.setdefault(cls, [])
                bases = node.child_by_field_name("bases")
                if bases is not None:
                    for c in bases.children:
                        if c.type in ("identifier", "qualified_name", "generic_name"):
                            base = _text(src, c).split("<", 1)[0].split(".")[-1]
                            if base and base not in sym.inheritance[cls]:
                                sym.inheritance[cls].append(base)
                class_stack.append(cls)
            for c in node.children:
                self._visit(c, src, file, class_stack, sym)
            if cls:
                class_stack.pop()
            return
        if t == "method_declaration":
            cls = class_stack[-1] if class_stack else ""
            name_node = node.child_by_field_name("name")
            name = _text(src, name_node) if name_node else "<method>"
            qual = f"{cls}.{name}" if cls else name
            params: dict[str, str] = {}
            params_node = node.child_by_field_name("parameters")
            if params_node is not None:
                for c in params_node.children:
                    if c.type == "parameter":
                        pname_n = c.child_by_field_name("name")
                        ptype_n = c.child_by_field_name("type")
                        if pname_n is None:
                            ids = [x for x in c.children if x.type == "identifier"]
                            pname_n = ids[-1] if ids else None
                        if pname_n is not None:
                            pname = _text(src, pname_n)
                            ptype = _text(src, ptype_n) if ptype_n is not None else ""
                            if not ptype:
                                # first identifier is often the type
                                ids = [x for x in c.children if x.type in ("identifier", "predefined_type", "generic_name", "nullable_type")]
                                if len(ids) >= 2:
                                    ptype = _text(src, ids[0])
                            params[pname] = ptype
            sym.methods.append(MethodSymbol(
                name=name, qual=qual, file=file,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                params=params, cls=cls,
            ))
            self._collect_calls(node, src, file, qual, sym)
            return
        if t == "field_declaration" and class_stack:
            decl = next((c for c in node.children if c.type == "variable_declaration"), None)
            if decl is not None:
                type_n = next((c for c in decl.children if c.type in (
                    "identifier", "predefined_type", "generic_name", "nullable_type", "qualified_name"
                )), None)
                ftype = _text(src, type_n) if type_n is not None else ""
                for c in decl.children:
                    if c.type == "variable_declarator":
                        idn = c.child_by_field_name("name")
                        if idn is None:
                            idn = next((x for x in c.children if x.type == "identifier"), None)
                        if idn is not None:
                            sym.fields.append(FieldSymbol(cls=class_stack[-1], name=_text(src, idn), type=ftype))
        for c in node.children:
            self._visit(c, src, file, class_stack, sym)

    def _collect_calls(self, method_node, src, file, caller_qual, sym: FileSymbols) -> None:
        stack = list(method_node.children)
        while stack:
            n = stack.pop()
            if n.type == "invocation_expression":
                fn = n.child_by_field_name("function")
                callee, receiver = _cs_callee_receiver(fn, src)
                if callee:
                    sym.calls.append(CallSite(caller_qual, callee, receiver, file, n.start_point[0] + 1))
            stack.extend(n.children)


def _cs_callee_receiver(fn_node, src) -> tuple[str | None, str | None]:
    if fn_node is None:
        return None, None
    if fn_node.type == "identifier":
        return _text(src, fn_node), None
    if fn_node.type == "member_access_expression":
        name_n = fn_node.child_by_field_name("name")
        expr_n = fn_node.child_by_field_name("expression")
        callee = _text(src, name_n) if name_n is not None else _text(src, fn_node).split(".")[-1]
        receiver = None
        if expr_n is not None:
            if expr_n.type == "identifier":
                receiver = _text(src, expr_n)
            elif expr_n.type == "member_access_expression":
                inner = expr_n.child_by_field_name("name")
                receiver = _text(src, inner) if inner is not None else _text(src, expr_n).split(".")[-1]
            elif expr_n.type == "invocation_expression":
                receiver = None
        return callee, receiver
    return None, None


LANGUAGES: dict[str, type[LanguageParser]] = {
    ".java": JavaParser,
    ".py": PythonParser,
    ".cs": CSharpParser,
}
