"""
Cortex Engineering — Python AST Graph Extractor.

Parses Python source files using Python's built-in ast module to extract
classes, functions, methods, imports, inheritance, calls, and test relationships.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from app.core.logging import get_logger
from app.graph.stable_key import make_file_key, make_symbol_key
from app.graph.types import ExtractedEdge, ExtractedNode, ExtractionResult
from app.models.graph import EdgeType, NodeType

logger = get_logger("python_extractor")


class PythonGraphExtractor:
    """Extracts code graph entities and relationships from Python source code."""

    def extract(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        content_hash: Optional[str] = None,
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
        imported_symbols: dict[str, str] = {}  # imported_name -> full_module_or_key

        # First pass: collect definitions and imports
        for stmt in tree.body:
            # Imports: import x, import x as y
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    target_name = alias.name
                    asname = alias.asname or alias.name
                    imported_symbols[asname] = target_name
                    # Edge from file to imported module
                    result.edges.append(
                        ExtractedEdge(
                            source_key=file_key,
                            target_key=f"repo:{repository_id}:file:{target_name.replace('.', '/')}.py",
                            edge_type=EdgeType.IMPORTS,
                            properties={"imported_name": target_name, "alias": asname},
                            confidence=0.8,
                            evidence_kind="static",
                            source_uri=relative_path,
                            content_hash=content_hash,
                        )
                    )

            # ImportFrom: from x import y
            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                for alias in stmt.names:
                    full_name = f"{mod}.{alias.name}" if mod else alias.name
                    asname = alias.asname or alias.name
                    imported_symbols[asname] = full_name
                    result.edges.append(
                        ExtractedEdge(
                            source_key=file_key,
                            target_key=f"repo:{repository_id}:file:{mod.replace('.', '/')}.py",
                            edge_type=EdgeType.IMPORTS,
                            properties={"imported_symbol": alias.name, "from_module": mod},
                            confidence=0.8,
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
                        target_base_key = classes_in_file.get(
                            base_name,
                            make_symbol_key(repository_id, relative_path, base_name, "class")
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
                caller_key = functions_in_file.get(node.name)
                if not caller_key:
                    continue

                is_test_caller = node.name.startswith("test_")

                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        callee_name = None
                        if isinstance(inner.func, ast.Name):
                            callee_name = inner.func.id
                        elif isinstance(inner.func, ast.Attribute):
                            callee_name = inner.func.attr

                        if not callee_name or callee_name == node.name:
                            continue

                        # If callee is known in file or imported
                        target_key = functions_in_file.get(callee_name)
                        if not target_key:
                            # Construct a speculative symbol key for call
                            target_key = make_symbol_key(
                                repository_id, relative_path, callee_name, "function"
                            )

                        edge_type = EdgeType.TESTS if is_test_caller else EdgeType.CALLS

                        result.edges.append(
                            ExtractedEdge(
                                source_key=caller_key,
                                target_key=target_key,
                                edge_type=edge_type,
                                properties={"call_line": inner.lineno},
                                confidence=0.85 if callee_name in functions_in_file else 0.6,
                                evidence_kind="static",
                                source_uri=relative_path,
                            )
                        )

        return result
