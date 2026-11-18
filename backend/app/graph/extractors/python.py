"""
TrunkHQ — Python AST Graph Extractor.

Parses Python source files using Python's built-in ast module to extract
classes, functions, methods, imports, inheritance, calls, and test relationships.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from app.core.logging import get_logger
from app.graph.stable_key import make_file_key, make_symbol_key, normalize_path
from app.graph.types import ExtractedEdge, ExtractedNode, ExtractionResult
from app.models.graph import EdgeType, NodeType

logger = get_logger("python_extractor")


def _resolve_python_module(
    current_file: str,
    module_name: Optional[str],
    level: int,
    repo_paths: Optional[set[str]],
) -> str:
    """Resolve a Python module/import (including relative levels) to a repo-relative .py path."""
    norm_current = normalize_path(current_file)
    if level > 0:
        parts = norm_current.split("/")[:-1]  # directory of current file
        up = max(0, level - 1)
        base_parts = parts[: len(parts) - up] if up <= len(parts) else []
        mod_parts = [p for p in (module_name or "").split(".") if p]
        rel_parts = base_parts + mod_parts
        base_rel = "/".join(rel_parts)
    else:
        base_rel = (module_name or "").replace(".", "/")

    if not base_rel:
        return norm_current

    candidates = [f"{base_rel}.py", f"{base_rel}/__init__.py"]
    if repo_paths:
        for cand in candidates:
            if cand in repo_paths:
                return cand
        # Handle repos nested under a root prefix like backend/
        for cand in candidates:
            suffix = f"/{cand}"
            for rp in repo_paths:
                if rp.endswith(suffix):
                    return rp
    return candidates[0]


class PythonGraphExtractor:
    """Extracts code graph entities and relationships from Python source code."""

    def extract(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        content_hash: Optional[str] = None,
        repo_paths: Optional[set[str]] = None,
    ) -> ExtractionResult:
        """Parse Python source and extract symbols and relationships."""
        result = ExtractionResult()

        try:
            tree = ast.parse(content, filename=relative_path)
        except SyntaxError as exc:
            logger.debug(
                "Skipping file due to syntax error",
                path=relative_path,
                line=exc.lineno,
                error=str(exc),
            )
            return result
        except Exception as exc:
            logger.warning(
                "Failed to parse Python AST",
                path=relative_path,
                error=str(exc),
            )
            return result

        file_key = make_file_key(repository_id, relative_path)
        filename = Path(relative_path).name
        module_path = relative_path.replace("/", ".").replace("\\", ".")
        if module_path.endswith(".py"):
            module_path = module_path[:-3]

        # File Node
        result.nodes.append(
            ExtractedNode(
                node_type=NodeType.FILE,
                stable_key=file_key,
                name=filename,
                qualified_name=relative_path,
                description=f"Source file: {relative_path}",
                properties={"language": "python", "path": relative_path},
                source_kind="code",
                source_uri=relative_path,
                content_hash=content_hash,
            )
        )

        # Context tracking
        classes_in_file: dict[str, str] = {}  # class_name -> stable_key
        functions_in_file: dict[str, str] = {}  # func_name -> stable_key
        func_node_keys: dict[int, str] = {}  # id(ast.FunctionDef) -> stable_key
        func_enclosing_class: dict[int, str] = {}  # id(ast.FunctionDef) -> class_name
        # alias_name -> (target_file_path, imported_symbol_or_None)
        import_aliases: dict[str, tuple[str, Optional[str]]] = {}

        # First pass: collect definitions and imports
        for stmt in tree.body:
            # Imports: import x, import x as y
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    target_name = alias.name
                    asname = alias.asname or alias.name.split(".")[0]
                    target_file = _resolve_python_module(relative_path, target_name, 0, repo_paths)
                    import_aliases[asname] = (target_file, None)
                    if alias.asname:
                        import_aliases[alias.asname] = (target_file, None)
                    # Edge from file to imported module
                    result.edges.append(
                        ExtractedEdge(
                            source_key=file_key,
                            target_key=make_file_key(repository_id, target_file),
                            edge_type=EdgeType.IMPORTS,
                            properties={"imported_name": target_name, "alias": asname, "resolved_file": target_file},
                            confidence=0.9 if (repo_paths and target_file in repo_paths) else 0.8,
                            evidence_kind="static",
                            source_uri=relative_path,
                            content_hash=content_hash,
                        )
                    )

            # ImportFrom: from x import y
            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                level = getattr(stmt, "level", 0) or 0
                base_target_file = _resolve_python_module(relative_path, mod, level, repo_paths)
                for alias in stmt.names:
                    asname = alias.asname or alias.name
                    target_file = base_target_file
                    imported_sym: Optional[str] = alias.name if alias.name != "*" else None

                    # Check if `from pkg import submod` refers to a module file in repo_paths
                    if alias.name != "*" and repo_paths:
                        submod = f"{mod}.{alias.name}" if mod else alias.name
                        sub_cand = _resolve_python_module(relative_path, submod, level, repo_paths)
                        if sub_cand in repo_paths:
                            target_file = sub_cand
                            imported_sym = None

                    if alias.name != "*":
                        import_aliases[asname] = (target_file, imported_sym)

                    result.edges.append(
                        ExtractedEdge(
                            source_key=file_key,
                            target_key=make_file_key(repository_id, target_file),
                            edge_type=EdgeType.IMPORTS,
                            properties={
                                "imported_symbol": alias.name,
                                "from_module": mod,
                                "alias": asname,
                                "resolved_file": target_file,
                            },
                            confidence=0.9 if (repo_paths and target_file in repo_paths) else 0.8,
                            evidence_kind="static",
                            source_uri=relative_path,
                            content_hash=content_hash,
                        )
                    )

            # Classes
            elif isinstance(stmt, ast.ClassDef):
                cls_key = make_symbol_key(repository_id, relative_path, stmt.name, "class")
                classes_in_file[stmt.name] = cls_key
                docstring = ast.get_docstring(stmt) or ""

                result.nodes.append(
                    ExtractedNode(
                        node_type=NodeType.CLASS,
                        stable_key=cls_key,
                        name=stmt.name,
                        qualified_name=f"{module_path}.{stmt.name}",
                        description=docstring[:300] if docstring else None,
                        properties={
                            "start_line": stmt.lineno,
                            "end_line": getattr(stmt, "end_lineno", stmt.lineno),
                            "path": relative_path,
                        },
                        source_kind="code",
                        source_uri=relative_path,
                        content_hash=content_hash,
                    )
                )

                # DEFINES edge from file to class
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
                for base in stmt.bases:
                    base_name = None
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr

                    if base_name:
                        # Target could be local or imported
                        target_base_key = classes_in_file.get(base_name)
                        if not target_base_key and base_name in import_aliases:
                            imp_file, imp_sym = import_aliases[base_name]
                            target_base_key = make_symbol_key(
                                repository_id, imp_file, imp_sym or base_name, "class"
                            )
                        if not target_base_key:
                            target_base_key = make_symbol_key(
                                repository_id, relative_path, base_name, "class"
                            )
                        result.edges.append(
                            ExtractedEdge(
                                source_key=cls_key,
                                target_key=target_base_key,
                                edge_type=EdgeType.INHERITS,
                                properties={"base_name": base_name},
                                confidence=0.9,
                                evidence_kind="static",
                                source_uri=relative_path,
                            )
                        )

                # Methods inside class
                for item in stmt.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_qual = f"{stmt.name}.{item.name}"
                        method_key = make_symbol_key(
                            repository_id, relative_path, method_qual, "method"
                        )
                        functions_in_file[item.name] = method_key
                        functions_in_file[method_qual] = method_key
                        func_node_keys[id(item)] = method_key
                        func_enclosing_class[id(item)] = stmt.name
                        m_doc = ast.get_docstring(item) or ""
                        is_test = item.name.startswith("test_") or stmt.name.startswith("Test")

                        result.nodes.append(
                            ExtractedNode(
                                node_type=NodeType.TEST if is_test else NodeType.METHOD,
                                stable_key=method_key,
                                name=item.name,
                                qualified_name=f"{module_path}.{method_qual}",
                                description=m_doc[:300] if m_doc else None,
                                properties={
                                    "start_line": item.lineno,
                                    "end_line": getattr(item, "end_lineno", item.lineno),
                                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                                    "is_test": is_test,
                                    "path": relative_path,
                                },
                                source_kind="code",
                                source_uri=relative_path,
                                content_hash=content_hash,
                            )
                        )

                        # CONTAINS edge from class to method
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

            # Top-level Functions
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_key = make_symbol_key(repository_id, relative_path, stmt.name, "function")
                functions_in_file[stmt.name] = func_key
                func_node_keys[id(stmt)] = func_key
                f_doc = ast.get_docstring(stmt) or ""
                is_test = stmt.name.startswith("test_")

                result.nodes.append(
                    ExtractedNode(
                        node_type=NodeType.TEST if is_test else NodeType.FUNCTION,
                        stable_key=func_key,
                        name=stmt.name,
                        qualified_name=f"{module_path}.{stmt.name}",
                        description=f_doc[:300] if f_doc else None,
                        properties={
                            "start_line": stmt.lineno,
                            "end_line": getattr(stmt, "end_lineno", stmt.lineno),
                            "is_async": isinstance(stmt, ast.AsyncFunctionDef),
                            "is_test": is_test,
                            "path": relative_path,
                        },
                        source_kind="code",
                        source_uri=relative_path,
                        content_hash=content_hash,
                    )
                )

                # DEFINES edge from file to function
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=func_key,
                        edge_type=EdgeType.DEFINES,
                        confidence=1.0,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )

        # Second pass: Extract CALLS and TESTS relationships
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller_key = func_node_keys.get(id(node)) or functions_in_file.get(node.name)
                if not caller_key:
                    continue

                is_test_caller = node.name.startswith("test_")
                enclosing_cls = func_enclosing_class.get(id(node))

                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        callee_name: Optional[str] = None
                        target_key: Optional[str] = None
                        confidence = 0.6

                        if isinstance(inner.func, ast.Name):
                            callee_name = inner.func.id
                            if callee_name in functions_in_file:
                                target_key = functions_in_file[callee_name]
                                confidence = 0.85
                            elif callee_name in classes_in_file:
                                target_key = classes_in_file[callee_name]
                                confidence = 0.85
                            elif callee_name in import_aliases:
                                imp_file, imp_sym = import_aliases[callee_name]
                                sym_name = imp_sym or callee_name
                                target_key = make_symbol_key(
                                    repository_id, imp_file, sym_name, "function"
                                )
                                confidence = 0.85
                        elif isinstance(inner.func, ast.Attribute):
                            callee_name = inner.func.attr
                            if isinstance(inner.func.value, ast.Name):
                                obj_name = inner.func.value.id
                                if obj_name == "self" and enclosing_cls:
                                    qual = f"{enclosing_cls}.{callee_name}"
                                    if qual in functions_in_file:
                                        target_key = functions_in_file[qual]
                                        confidence = 0.9
                                elif obj_name in import_aliases:
                                    imp_file, imp_sym = import_aliases[obj_name]
                                    if imp_sym is None:
                                        # Module import: e.g., utils.helper()
                                        target_key = make_symbol_key(
                                            repository_id, imp_file, callee_name, "function"
                                        )
                                        confidence = 0.85
                                    else:
                                        # Class/object import: e.g., Service.method()
                                        target_key = make_symbol_key(
                                            repository_id, imp_file, f"{imp_sym}.{callee_name}", "method"
                                        )
                                        confidence = 0.8

                        if not callee_name or callee_name == node.name:
                            continue

                        if not target_key:
                            target_key = functions_in_file.get(callee_name)
                            if target_key:
                                confidence = 0.85
                            else:
                                # Construct a speculative symbol key for call
                                target_key = make_symbol_key(
                                    repository_id, relative_path, callee_name, "function"
                                )
                                confidence = 0.5

                        edge_type = EdgeType.TESTS if is_test_caller else EdgeType.CALLS

                        result.edges.append(
                            ExtractedEdge(
                                source_key=caller_key,
                                target_key=target_key,
                                edge_type=edge_type,
                                properties={"call_line": inner.lineno, "callee": callee_name},
                                confidence=confidence,
                                evidence_kind="static",
                                source_uri=relative_path,
                            )
                        )

        return result
