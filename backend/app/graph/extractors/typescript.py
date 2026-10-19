"""
Cortex Engineering — TypeScript / JavaScript AST & Lexical Graph Extractor.

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


class TypeScriptGraphExtractor:
    """Extracts code graph entities and relationships from TypeScript/JavaScript source."""

    def extract(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        content_hash: Optional[str] = None,
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

        # Track symbols defined in this file
        defined_symbols: dict[str, str] = {}  # symbol_name -> stable_key

        # 1. Extract Imports
        self._extract_imports(
            repository_id, norm_path, content, file_key, content_hash, result
        )

        # 2. Extract Classes & Methods
        self._extract_classes(
            repository_id,
            norm_path,
            content,
            file_key,
            content_hash,
            get_line_number,
            defined_symbols,
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
            result,
        )

        return result

    def _resolve_relative_import(self, current_file: str, import_path: str) -> str:
        """Resolve a relative import (e.g., './foo', '../bar') to a repository file path."""
        if not (import_path.startswith("./") or import_path.startswith("../")):
            return import_path

        current_dir = os.path.dirname(current_file)
        joined = os.path.normpath(os.path.join(current_dir, import_path)).replace("\\", "/")
        return joined

    def _extract_imports(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        file_key: str,
        content_hash: Optional[str],
        result: ExtractionResult,
    ) -> None:
        """Extract import statements and build IMPORTS edges."""
        for m in RE_IMPORT.finditer(content):
            default_imp = m.group(1)
            named_imp1 = m.group(2)
            star_imp = m.group(3)
            named_imp2 = m.group(4)
            import_source = m.group(5)

            resolved_path = self._resolve_relative_import(relative_path, import_source)
            is_local = import_source.startswith("./") or import_source.startswith("../") or import_source.startswith("@/")

            target_key = (
                f"repo:{repository_id}:file:{resolved_path}"
                if is_local
                else f"repo:{repository_id}:symbol:{import_source}:external"
            )

            imported_names = []
            if default_imp:
                imported_names.append(default_imp)
            if star_imp:
                imported_names.append(star_imp)
            for named in (named_imp1, named_imp2):
                if named:
                    for item in named.split(","):
                        clean_item = item.strip().split(" as ")[0].strip()
                        if clean_item:
                            imported_names.append(clean_item)

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
        defined_symbols: dict[str, str],
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
                target_base_key = defined_symbols.get(
                    base_cls,
                    make_symbol_key(repository_id, relative_path, base_cls, "class"),
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
                        result.edges.append(
                            ExtractedEdge(
                                source_key=cls_key,
                                target_key=make_symbol_key(
                                    repository_id, relative_path, iface_clean, "interface"
                                ),
                                edge_type=EdgeType.IMPLEMENTS,
                                properties={"interface_name": iface_clean},
                                confidence=0.9,
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
        result: ExtractionResult,
    ) -> None:
        """Detect intra-file and inter-symbol function calls."""
        if not defined_symbols:
            return

        for m in RE_CALL.finditer(content):
            callee_name = m.group(1)
            if callee_name in defined_symbols:
                target_key = defined_symbols[callee_name]
                # Edge from file to callee
                file_key = make_file_key(repository_id, relative_path)
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=target_key,
                        edge_type=EdgeType.CALLS,
                        properties={"callee": callee_name},
                        confidence=0.8,
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
