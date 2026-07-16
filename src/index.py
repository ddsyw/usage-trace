"""ProjectIndex: parse-once symbol/call index with on-disk incremental cache."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from common import classify_layer
from parsing import FileSymbols, parser_for

INDEX_VERSION = 1
_SOURCE_EXTS = (".java",)  # P1; P4 adds .cs/.py via LANGUAGES


class ProjectIndex:
    def __init__(self) -> None:
        self.root_hash: str = ""
        self.files: dict[str, dict] = {}            # path -> {mtime, size, hash}
        self.methods: dict[str, object] = {}        # qual -> MethodSymbol
        self.methods_by_name: dict[str, list[str]] = {}
        self.methods_by_file: dict[str, list[object]] = {}
        self.fields: dict[str, dict[str, str]] = {} # cls -> {field: type}
        self.inheritance: dict[str, list[str]] = {}
        self.calls_by_caller: dict[str, list[object]] = {}
        self.calls_by_callee: dict[str, list[object]] = {}
        self.layers: dict[str, str] = {}
        self._symbols_cache: dict[str, FileSymbols] = {}

    def build(self, root: Path, profile: dict) -> "ProjectIndex":
        root = Path(root)
        self.root_hash = _root_hash(root, profile.get("profile", ""))
        layers = profile.get("layers", [])
        exclude = set(profile.get("exclude", {}).get("dirs", []))
        for path in _walk_sources(root, exclude):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            factory = parser_for(str(path))
            if factory is None:
                continue
            fs = factory.parse(text, str(path))
            self._integrate(str(path), fs)
            self.layers[str(path)] = classify_layer(str(path), layers, text)
            st = path.stat()
            self.files[str(path)] = {
                "mtime": int(st.st_mtime), "size": st.st_size,
                "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            self._symbols_cache[str(path)] = fs
        return self

    def _integrate(self, path: str, fs: FileSymbols) -> None:
        for m in fs.methods:
            self.methods[m.qual] = m
            self.methods_by_name.setdefault(m.name, []).append(m.qual)
            self.methods_by_file.setdefault(path, []).append(m)
        for f in fs.fields:
            self.fields.setdefault(f.cls, {})[f.name] = f.type
        for cls, supers in fs.inheritance.items():
            self.inheritance.setdefault(cls, [])
            for s in supers:
                if s not in self.inheritance[cls]:
                    self.inheritance[cls].append(s)
        for c in fs.calls:
            self.calls_by_caller.setdefault(c.caller_qual, []).append(c)
            self.calls_by_callee.setdefault(c.callee_name, []).append(c)

    def enclosing_method(self, file: str, line: int):
        best = None
        best_span = None
        for m in self.methods_by_file.get(file, []):
            if m.start_line <= line <= m.end_line:
                span = m.end_line - m.start_line
                if best is None or span < best_span:
                    best, best_span = m, span
        return best

    def symbol_types(self, qual: str) -> dict[str, str]:
        m = self.methods.get(qual)
        if not m:
            return {}
        types: dict[str, str] = {"this": m.cls} if m.cls else {}
        types.update(self.fields.get(m.cls, {}))
        types.update(m.params)
        return types

    def resolve_callee_targets(self, caller_qual: str, callee_name: str, receiver: str | None) -> list[str]:
        candidates = self.methods_by_name.get(callee_name, [])
        if not candidates:
            return []
        if receiver:
            rtype = self.symbol_types(caller_qual).get(receiver)
            return [q for q in candidates if _class_of(q) == rtype] if rtype else []
        caller = self.methods.get(caller_qual)
        caller_cls = caller.cls if caller else None
        return [q for q in candidates if _class_of(q) == caller_cls]

    @classmethod
    def load_or_build(cls, root: Path, profile: dict, cache_dir: Path | None = None) -> "ProjectIndex":
        root = Path(root)
        cache_dir = Path(cache_dir) if cache_dir else root / ".usage-trace" / "index"
        idx = cls()
        idx.root_hash = _root_hash(root, profile.get("profile", ""))
        cached_manifest = _read_json(cache_dir / "manifest.json")
        idx._build_from(root, profile, cached_manifest, cache_dir)
        try:
            idx._save(cache_dir)
        except OSError:
            pass  # read-only root: keep in-memory, no persistence
        return idx

    def _build_from(self, root: Path, profile: dict, cached_manifest: dict | None,
                    cache_dir: Path) -> "ProjectIndex":
        layers = profile.get("layers", [])
        exclude = set(profile.get("exclude", {}).get("dirs", []))
        cached_files: dict[str, dict] = {}
        if cached_manifest and cached_manifest.get("root_hash") == self.root_hash \
                and cached_manifest.get("version") == INDEX_VERSION:
            cached_files = cached_manifest.get("files", {})

        for path in _walk_sources(root, exclude):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            factory = parser_for(str(path))
            if factory is None:
                continue
            st = path.stat()
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            self.files[str(path)] = {
                "mtime": int(st.st_mtime), "size": st.st_size, "hash": digest,
            }

            fs = None
            cached = cached_files.get(str(path))
            if cached and cached.get("hash") == digest:
                blob = _read_json(cache_dir / "symbols" / f"{digest}.json")
                if blob:
                    fs = FileSymbols.from_dict(blob)
            if fs is None:
                fs = factory.parse(text, str(path))
            self._integrate(str(path), fs)
            self.layers[str(path)] = classify_layer(str(path), layers, text)
            self._symbols_cache[str(path)] = fs
        return self

    def _save(self, cache_dir: Path) -> None:
        sym_dir = cache_dir / "symbols"
        sym_dir.mkdir(parents=True, exist_ok=True)
        for path, fs in self._symbols_cache.items():
            digest = self.files[path]["hash"]
            target = sym_dir / f"{digest}.json"
            if not target.exists():
                target.write_text(json.dumps(fs.to_dict(), ensure_ascii=False), encoding="utf-8")
        manifest = {"root_hash": self.root_hash, "version": INDEX_VERSION, "files": self.files}
        (cache_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _class_of(qual: str) -> str:
    return qual.rsplit(".", 1)[0] if "." in qual else qual


def _root_hash(root: Path, profile_name: str) -> str:
    try:
        loc = str(root.resolve())
    except OSError:
        loc = str(root)
    return hashlib.sha1(f"{loc}|{profile_name}".encode("utf-8")).hexdigest()[:16]


def _walk_sources(root: Path, exclude: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fn in filenames:
            if Path(fn).suffix in _SOURCE_EXTS:
                yield Path(dirpath) / fn


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
