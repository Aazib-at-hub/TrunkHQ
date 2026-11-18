"""
TrunkHQ — TypeScript / JavaScript AST & Lexical Graph Extractor.

Extracts files, components, functions, classes, interfaces, imports, and calls
from TypeScript and JavaScript source files (.ts, .tsx, .js, .jsx, .mjs, .cjs).
"""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Callable, Optional
from uuid import UUID

from app.core.logging import get_logger
from app.graph.stable_key import make_file_key, make_symbol_key, normalize_path
from app.graph.types import ExtractedEdge, ExtractedNode, ExtractionResult
from app.models.graph import EdgeType, NodeType

logger = get_logger("typescript_extractor")

# Regex patterns for TypeScript / JavaScript constructs
RE_IMPORT = re.compile(
    r"""import\s+(?:type\s+)?(?:([a-zA-Z0-9_$]+)|(?:\{([^}]+)\})|(?:\*\s+as\s+([a-zA-Z0-9_$]+)))(?:\s*,\s*(?:\{([^}]+)\}))?\s+from\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)

RE_REQUIRE = re.compile(
    r"""(?:const|let|var)\s+(?:([a-zA-Z0-9_$]+)|\{([^}]+)\})\s*=\s*require\(['"]([^'"]+)['"]\)""",
    re.MULTILINE,
)

RE_FUNCTION = re.compile(
    r"""(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*(?:<[^>]*>)?\s*\(""",
    re.MULTILINE,
)

RE_CONST_FN = re.compile(
    r"""(?:export\s+)?(?:const|let)\s+([a-zA-Z0-9_$]+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*(?::\s*[^=>]+)?\s*=>""",
    re.MULTILINE,
)

RE_CLASS = re.compile(
    r"""(?:export\s+)?(?:default\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$.]+))?(?:\s+implements\s+([a-zA-Z0-9_$,\s]+))?""",
    re.MULTILINE,
)

RE_INTERFACE = re.compile(
    r"""(?:export\s+)?interface\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$,\s]+))?""",
    re.MULTILINE,
)

RE_TYPE = re.compile(
    r"""(?:export\s+)?type\s+([a-zA-Z0-9_$]+)(?:<[^>]*>)?\s*=""",
    re.MULTILINE,
)

RE_TEST_CALL = re.compile(
    r"""\b(?:it|test|describe)\s*\(\s*['"`]([^'"`]+)['"`]""",
    re.MULTILINE,
)

RE_CALL = re.compile(
    r"""\b([a-zA-Z0-9_$]+)\s*\(""",
    re.MULTILINE,
)

RE_JSDOC = re.compile(
    r"""/\*\*\s*([\s\S]*?)\s*\*/""",
    re.MULTILINE,
)

RE_CLASS_METHOD = re.compile(
    r"""^\s*(?:(?:public|private|protected|static|readonly|override|abstract|async)\s+)*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*(?::\s*[^\{;\n]+)?\s*\{""",
    re.MULTILINE,
)

RE_NS_CALL = re.compile(
    r"""\b([a-zA-Z0-9_$]+)\.([a-zA-Z0-9_$]+)\s*\(""",
    re.MULTILINE,
)

_TS_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "new",
    "super", "constructor", "import", "export", "await", "throw", "delete",
}

_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_TS_INDEX_FILES = ("/index.ts", "/index.tsx", "/index.js", "/index.jsx")


class TypeScriptGraphExtractor:
    """Extracts code graph entities and relationships from TypeScript/JavaScript source."""

    def extract(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        content_hash: Optional[str] = None,
        repo_paths: Optional[set[str]] = None,
    ) -> ExtractionResult:
        """Parse TypeScript/JavaScript source and extract symbols and relationships."""
        result = ExtractionResult()
        norm_path = normalize_path(relative_path)
        file_key = make_file_key(repository_id, norm_path)
        filename = Path(norm_path).name
        ext = Path(norm_path).suffix.lower()
        is_test_file = (
            ".test." in norm_path
            or ".spec." in norm_path
            or "/__tests__/" in norm_path
            or norm_path.startswith("tests/")
        )

        lines = content.splitlines()

        def get_line_number(char_idx: int) -> int:
            return content.count("\n", 0, char_idx) + 1

        # File Node
        file_doc = None
        trimmed = content.lstrip()
        if trimmed.startswith("/**"):
            end_comment = content.find("*/")
            if end_comment != -1:
                file_doc = self._clean_jsdoc(content[content.find("/**") : end_comment + 2])

        result.nodes.append(
            ExtractedNode(
                node_type=NodeType.TEST if is_test_file else NodeType.FILE,
                stable_key=file_key,
                name=filename,
                qualified_name=norm_path,
                description=file_doc or f"TypeScript/JavaScript source file: {norm_path}",
                properties={
                    "language": "typescript" if ext in {".ts", ".tsx"} else "javascript",
                    "path": norm_path,
                    "is_react": ext in {".tsx", ".jsx"} or "react" in content.lower(),
                },
                source_kind="code",
                source_uri=norm_path,
                content_hash=content_hash,
            )
        )

        # Track symbols defined in this file and imported aliases
        defined_symbols: dict[str, str] = {}  # symbol_name -> stable_key
        import_aliases: dict[str, tuple[str, Optional[str]]] = {}  # local_name -> (target_file, orig_sym_or_None)

        # 1. Extract Imports
        self._extract_imports(
            repository_id,
            norm_path,
            content,
            file_key,
            content_hash,
            repo_paths,
            import_aliases,
            result,
        )

        # 2. Extract Classes & Methods
        self._extract_classes(
            repository_id,
            norm_path,
            content,
            file_key,
            content_hash,
            get_line_number,
            is_test_file,
            defined_symbols,
            import_aliases,
            result,
        )

        # 3. Extract Functions & React Components
        self._extract_functions(
            repository_id,
            norm_path,
            content,
            file_key,
            content_hash,
            get_line_number,
            is_test_file,
            defined_symbols,
            result,
        )

        # 4. Extract Interfaces & Types
        self._extract_types(
            repository_id,
            norm_path,
            content,
            file_key,
            content_hash,
            get_line_number,
            defined_symbols,
            result,
        )

        # 5. Extract Tests (if test file)
        if is_test_file:
            self._extract_tests(
                repository_id,
                norm_path,
                content,
                file_key,
                content_hash,
                get_line_number,
                result,
            )

        # 6. Extract Inter-Symbol Calls
        self._extract_calls(
            repository_id,
            norm_path,
            content,
            defined_symbols,
            import_aliases,
            result,
        )

        return result

    def _resolve_relative_import(
        self,
        current_file: str,
        import_path: str,
        repo_paths: Optional[set[str]] = None,
    ) -> str:
        """Resolve a relative or alias import (e.g., './foo', '@/bar') to a repository file path."""
        if import_path.startswith("@/"):
            rel_candidate = import_path[2:]
            candidates = [rel_candidate]
            if not Path(rel_candidate).suffix:
                candidates.extend(f"{rel_candidate}{ext}" for ext in _TS_EXTENSIONS)
                candidates.extend(f"{rel_candidate}{idx}" for idx in _TS_INDEX_FILES)
            if repo_paths:
                for cand in candidates:
                    norm_cand = normalize_path(cand)
                    if norm_cand in repo_paths:
                        return norm_cand
                    # Common frontend/src/ prefix
                    for prefix in ("frontend/", "src/", "frontend/src/"):
                        prefixed = normalize_path(f"{prefix}{cand}")
                        if prefixed in repo_paths:
                            return prefixed
            return normalize_path(candidates[1] if len(candidates) > 1 else rel_candidate)

        if not (import_path.startswith("./") or import_path.startswith("../")):
            return import_path

        current_dir = os.path.dirname(current_file)
        joined = normalize_path(os.path.normpath(os.path.join(current_dir, import_path)).replace("\\", "/"))

        if Path(joined).suffix:
            if repo_paths and joined in repo_paths:
                return joined
            return joined

        candidates = [joined]
        candidates.extend(f"{joined}{ext}" for ext in _TS_EXTENSIONS)
        candidates.extend(f"{joined}{idx}" for idx in _TS_INDEX_FILES)

        if repo_paths:
            for cand in candidates:
                if cand in repo_paths:
                    return cand

        return f"{joined}.ts"

    def _extract_imports(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        repo_paths: Optional[set[str]],
        import_aliases: dict[str, tuple[str, Optional[str]]],
        result: ExtractionResult,
    ) -> None:
        """Extract import/require statements, build alias map, and emit IMPORTS edges."""
        for m in RE_IMPORT.finditer(content):
            default_imp = m.group(1)
            named_imp1 = m.group(2)
            star_imp = m.group(3)
            named_imp2 = m.group(4)
            import_source = m.group(5)

            is_local = (
                import_source.startswith("./")
                or import_source.startswith("../")
                or import_source.startswith("@/")
            )
            resolved_path = (
                self._resolve_relative_import(relative_path, import_source, repo_paths)
                if is_local
                else import_source
            )

            target_key = (
                make_file_key(repository_id, resolved_path)
                if is_local
                else f"repo:{repository_id}:symbol:{import_source}:external"
            )

            imported_names = []
            if default_imp:
                imported_names.append(default_imp)
                if is_local:
                    import_aliases[default_imp] = (resolved_path, default_imp)
            if star_imp:
                imported_names.append(star_imp)
                if is_local:
                    import_aliases[star_imp] = (resolved_path, None)
            for named in (named_imp1, named_imp2):
                if named:
                    for item in named.split(","):
                        parts = [p.strip() for p in item.strip().split(" as ") if p.strip()]
                        if not parts:
                            continue
                        orig_name = parts[0].removeprefix("type ").strip()
                        local_name = parts[1] if len(parts) > 1 else orig_name
                        if orig_name:
                            imported_names.append(orig_name)
                            if is_local:
                                import_aliases[local_name] = (resolved_path, orig_name)

            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=target_key,
                    edge_type=EdgeType.IMPORTS,
                    properties={
                        "module": import_source,
                        "resolved_path": resolved_path if is_local else None,
                        "imported_names": imported_names[:10],
                        "is_external": not is_local,
                    },
                    confidence=0.95 if (is_local and repo_paths and resolved_path in repo_paths) else (0.9 if is_local else 0.7),
                    evidence_kind="static",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

        for m in RE_REQUIRE.finditer(content):
            default_imp = m.group(1)
            named_imp = m.group(2)
            import_source = m.group(3)
            is_local = import_source.startswith("./") or import_source.startswith("../")
            resolved_path = (
                self._resolve_relative_import(relative_path, import_source, repo_paths)
                if is_local
                else import_source
            )
            target_key = (
                make_file_key(repository_id, resolved_path)
                if is_local
                else f"repo:{repository_id}:symbol:{import_source}:external"
            )
            imported_names = []
            if default_imp:
                imported_names.append(default_imp)
                if is_local:
                    import_aliases[default_imp] = (resolved_path, None)
            if named_imp:
                for item in named_imp.split(","):
                    parts = [p.strip() for p in item.strip().split(":") if p.strip()]
                    if parts:
                        orig = parts[0]
                        local = parts[1] if len(parts) > 1 else orig
                        imported_names.append(orig)
                        if is_local:
                            import_aliases[local] = (resolved_path, orig)
            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=target_key,
                    edge_type=EdgeType.IMPORTS,
                    properties={
                        "module": import_source,
                        "resolved_path": resolved_path if is_local else None,
                        "imported_names": imported_names[:10],
                        "is_external": not is_local,
                    },
                    confidence=0.9 if is_local else 0.7,
                    evidence_kind="static",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

    def _extract_classes(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        get_line_number: Callable[[int], int],
        is_test_file: bool,
        defined_symbols: dict[str, str],
        import_aliases: dict[str, tuple[str, Optional[str]]],
        result: ExtractionResult,
    ) -> None:
        """Extract class definitions, inheritance, and methods."""
        for m in RE_CLASS.finditer(content):
            cls_name = m.group(1)
            base_cls = m.group(2)
            implements_clause = m.group(3)
            start_line = get_line_number(m.start())

            cls_key = make_symbol_key(repository_id, relative_path, cls_name, "class")
            defined_symbols[cls_name] = cls_key

            docstring = self._find_preceding_jsdoc(content, m.start())

            result.nodes.append(
                ExtractedNode(
                    node_type=NodeType.CLASS,
                    stable_key=cls_key,
                    name=cls_name,
                    qualified_name=f"{relative_path}::{cls_name}",
                    description=docstring,
                    properties={
                        "start_line": start_line,
                        "path": relative_path,
                    },
                    source_kind="code",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

            # File DEFINES class
            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=cls_key,
                    edge_type=EdgeType.DEFINES,
                    confidence=1.0,
                    evidence_kind="static",
                    source_uri=relative_path,
                )
            )

            # Inheritance
            if base_cls:
                target_base_key = defined_symbols.get(base_cls)
                if not target_base_key and base_cls in import_aliases:
                    imp_file, imp_sym = import_aliases[base_cls]
                    target_base_key = make_symbol_key(
                        repository_id, imp_file, imp_sym or base_cls, "class"
                    )
                if not target_base_key:
                    target_base_key = make_symbol_key(
                        repository_id, relative_path, base_cls, "class"
                    )
                result.edges.append(
                    ExtractedEdge(
                        source_key=cls_key,
                        target_key=target_base_key,
                        edge_type=EdgeType.INHERITS,
                        properties={"base_name": base_cls},
                        confidence=0.9,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )

            # Implements interfaces
            if implements_clause:
                for iface in implements_clause.split(","):
                    iface_clean = iface.strip()
                    if iface_clean:
                        target_iface_key = defined_symbols.get(iface_clean)
                        if not target_iface_key and iface_clean in import_aliases:
                            imp_file, imp_sym = import_aliases[iface_clean]
                            target_iface_key = make_symbol_key(
                                repository_id, imp_file, imp_sym or iface_clean, "interface"
                            )
                        if not target_iface_key:
                            target_iface_key = make_symbol_key(
                                repository_id, relative_path, iface_clean, "interface"
                            )
                        result.edges.append(
                            ExtractedEdge(
                                source_key=cls_key,
                                target_key=target_iface_key,
                                edge_type=EdgeType.IMPLEMENTS,
                                properties={"interface_name": iface_clean},
                                confidence=0.9,
                                evidence_kind="static",
                                source_uri=relative_path,
                            )
                        )

            # Extract methods inside brace-balanced class body
            body_start = content.find("{", m.end())
            if body_start != -1:
                depth = 0
                body_end = body_start
                for idx in range(body_start, len(content)):
                    ch = content[idx]
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            body_end = idx
                            break
                class_body = content[body_start + 1 : body_end]
                for mm in RE_CLASS_METHOD.finditer(class_body):
                    method_name = mm.group(1)
                    if method_name in _TS_KEYWORDS:
                        continue
                    method_qual = f"{cls_name}.{method_name}"
                    method_key = make_symbol_key(
                        repository_id, relative_path, method_qual, "method"
                    )
                    defined_symbols[method_name] = method_key
                    defined_symbols[method_qual] = method_key
                    method_line = get_line_number(body_start + 1 + mm.start())
                    is_test_m = is_test_file and method_name.startswith("test")
                    result.nodes.append(
                        ExtractedNode(
                            node_type=NodeType.TEST if is_test_m else NodeType.METHOD,
                            stable_key=method_key,
                            name=method_name,
                            qualified_name=f"{relative_path}::{method_qual}",
                            description=self._find_preceding_jsdoc(content, body_start + 1 + mm.start()),
                            properties={"start_line": method_line, "path": relative_path, "class": cls_name},
                            source_kind="code",
                            source_uri=relative_path,
                            content_hash=content_hash,
                        )
                    )
                    result.edges.append(
                        ExtractedEdge(
                            source_key=cls_key,
                            target_key=method_key,
                            edge_type=EdgeType.CONTAINS,
                            confidence=1.0,
                            evidence_kind="static",
                            source_uri=relative_path,
                        )
                    )

    def _extract_functions(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        get_line_number: Callable[[int], int],
        is_test_file: bool,
        defined_symbols: dict[str, str],
        result: ExtractionResult,
    ) -> None:
        """Extract named functions, React components, and exported arrow functions."""
        # Standard functions
        for m in RE_FUNCTION.finditer(content):
            fn_name = m.group(1)
            self._register_function(
                repository_id,
                relative_path,
                fn_name,
                m.start(),
                content,
                file_key,
                content_hash,
                get_line_number,
                is_test_file,
                defined_symbols,
                result,
            )

        # Exported / top-level arrow functions
        for m in RE_CONST_FN.finditer(content):
            fn_name = m.group(1)
            # Filter common non-function constants
            if fn_name in defined_symbols or fn_name in {"router", "app", "db"}:
                continue
            self._register_function(
                repository_id,
                relative_path,
                fn_name,
                m.start(),
                content,
                file_key,
                content_hash,
                get_line_number,
                is_test_file,
                defined_symbols,
                result,
            )

    def _register_function(
        self,
        repository_id: UUID,
        relative_path: str,
        fn_name: str,
        char_idx: int,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        get_line_number: Callable[[int], int],
        is_test_file: bool,
        defined_symbols: dict[str, str],
        result: ExtractionResult,
    ) -> None:
        """Helper to create and link function/component node."""
        if fn_name in defined_symbols:
            return

        is_component = fn_name[0].isupper() and not is_test_file
        node_type = NodeType.TEST if is_test_file else NodeType.FUNCTION
        fn_key = make_symbol_key(repository_id, relative_path, fn_name, "function")
        defined_symbols[fn_name] = fn_key
        start_line = get_line_number(char_idx)
        docstring = self._find_preceding_jsdoc(content, char_idx)

        result.nodes.append(
            ExtractedNode(
                node_type=node_type,
                stable_key=fn_key,
                name=fn_name,
                qualified_name=f"{relative_path}::{fn_name}",
                description=docstring,
                properties={
                    "start_line": start_line,
                    "is_component": is_component,
                    "path": relative_path,
                },
                source_kind="code",
                source_uri=relative_path,
                content_hash=content_hash,
            )
        )

        result.edges.append(
            ExtractedEdge(
                source_key=file_key,
                target_key=fn_key,
                edge_type=EdgeType.DEFINES,
                confidence=1.0,
                evidence_kind="static",
                source_uri=relative_path,
            )
        )

    def _extract_types(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        get_line_number: Callable[[int], int],
        defined_symbols: dict[str, str],
        result: ExtractionResult,
    ) -> None:
        """Extract TypeScript interfaces and type aliases."""
        for m in RE_INTERFACE.finditer(content):
            iface_name = m.group(1)
            extends_clause = m.group(2)
            start_line = get_line_number(m.start())
            iface_key = make_symbol_key(repository_id, relative_path, iface_name, "interface")
            defined_symbols[iface_name] = iface_key
            doc = self._find_preceding_jsdoc(content, m.start())

            result.nodes.append(
                ExtractedNode(
                    node_type=NodeType.SYMBOL,
                    stable_key=iface_key,
                    name=iface_name,
                    qualified_name=f"{relative_path}::{iface_name}",
                    description=doc,
                    properties={
                        "symbol_kind": "interface",
                        "start_line": start_line,
                        "path": relative_path,
                    },
                    source_kind="code",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=iface_key,
                    edge_type=EdgeType.DEFINES,
                    confidence=1.0,
                    evidence_kind="static",
                    source_uri=relative_path,
                )
            )

        for m in RE_TYPE.finditer(content):
            type_name = m.group(1)
            start_line = get_line_number(m.start())
            type_key = make_symbol_key(repository_id, relative_path, type_name, "type")
            defined_symbols[type_name] = type_key
            doc = self._find_preceding_jsdoc(content, m.start())

            result.nodes.append(
                ExtractedNode(
                    node_type=NodeType.SYMBOL,
                    stable_key=type_key,
                    name=type_name,
                    qualified_name=f"{relative_path}::{type_name}",
                    description=doc,
                    properties={
                        "symbol_kind": "type",
                        "start_line": start_line,
                        "path": relative_path,
                    },
                    source_kind="code",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=type_key,
                    edge_type=EdgeType.DEFINES,
                    confidence=1.0,
                    evidence_kind="static",
                    source_uri=relative_path,
                )
            )

    def _extract_tests(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        get_line_number: Callable[[int], int],
        result: ExtractionResult,
    ) -> None:
        """Extract test suites and test cases."""
        for m in RE_TEST_CALL.finditer(content):
            test_title = m.group(1).strip()
            start_line = get_line_number(m.start())
            test_key = make_symbol_key(repository_id, relative_path, test_title[:50], "test")

            result.nodes.append(
                ExtractedNode(
                    node_type=NodeType.TEST,
                    stable_key=test_key,
                    name=test_title[:60],
                    qualified_name=f"{relative_path}::{test_title}",
                    description=f"Automated test: {test_title}",
                    properties={"start_line": start_line, "path": relative_path},
                    source_kind="code",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=test_key,
                    edge_type=EdgeType.DEFINES,
                    confidence=1.0,
                    evidence_kind="static",
                    source_uri=relative_path,
                )
            )

    def _extract_calls(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        defined_symbols: dict[str, str],
        import_aliases: dict[str, tuple[str, Optional[str]]],
        result: ExtractionResult,
    ) -> None:
        """Detect intra-file and cross-file function calls."""
        if not defined_symbols and not import_aliases:
            return

        file_key = make_file_key(repository_id, relative_path)
        seen_targets: set[str] = set()

        # Namespace/module calls: ns.fn()
        for m in RE_NS_CALL.finditer(content):
            ns_name, fn_name = m.group(1), m.group(2)
            if ns_name in import_aliases:
                imp_file, imp_sym = import_aliases[ns_name]
                if imp_sym is None:
                    target_key = make_symbol_key(repository_id, imp_file, fn_name, "function")
                else:
                    target_key = make_symbol_key(repository_id, imp_file, f"{imp_sym}.{fn_name}", "method")
                if target_key not in seen_targets:
                    seen_targets.add(target_key)
                    result.edges.append(
                        ExtractedEdge(
                            source_key=file_key,
                            target_key=target_key,
                            edge_type=EdgeType.CALLS,
                            properties={"callee": f"{ns_name}.{fn_name}"},
                            confidence=0.8,
                            evidence_kind="static",
                            source_uri=relative_path,
                        )
                    )

        # Direct calls: fn()
        for m in RE_CALL.finditer(content):
            callee_name = m.group(1)
            if callee_name in _TS_KEYWORDS:
                continue
            target_key: Optional[str] = None
            confidence = 0.8
            if callee_name in defined_symbols:
                target_key = defined_symbols[callee_name]
            elif callee_name in import_aliases:
                imp_file, imp_sym = import_aliases[callee_name]
                target_key = make_symbol_key(
                    repository_id, imp_file, imp_sym or callee_name, "function"
                )
                confidence = 0.85

            if target_key and target_key not in seen_targets:
                seen_targets.add(target_key)
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=target_key,
                        edge_type=EdgeType.CALLS,
                        properties={"callee": callee_name},
                        confidence=confidence,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )

    def _clean_jsdoc(self, raw: str) -> Optional[str]:
        """Strip JSDoc comment markers /** and * from comment string."""
        content = raw.replace("/**", "").replace("*/", "")
        cleaned_lines = [re.sub(r"^\s*\*\s?", "", line).strip() for line in content.splitlines()]
        cleaned = "\n".join(l for l in cleaned_lines if l).strip()
        return cleaned[:300] if cleaned else None

    def _find_preceding_jsdoc(self, content: str, char_idx: int) -> Optional[str]:
        """Look backwards from a declaration to extract any JSDoc block."""
        window_start = max(0, char_idx - 500)
        prefix = content[window_start:char_idx]
        matches = list(RE_JSDOC.finditer(prefix))
        if not matches:
            return None
        last_match = matches[-1]
        # Ensure only whitespace/comments between JSDoc and declaration
        trailing = prefix[last_match.end() :]
        if any(line.strip() and not line.strip().startswith("//") for line in trailing.splitlines()):
            return None

        return self._clean_jsdoc(last_match.group(0))
