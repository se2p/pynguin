#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""SUT inspector: extracts docstrings and signatures via importlib."""

import ast
import importlib
import inspect
import logging
import signal
import sys
from collections import Counter
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class SUTInspectionResult:
    """Container for SUT inspection results.

    Attributes:
        docstring: The docstring of the method/function/class being tested
        signature: The call signature (e.g., "(self, fmt='%Y-%m-%d', key='timestamp')")
        parent_docstring: If the object is a method, the parent class docstring
        module_name: The resolved module name
        object_path: The path to the object within the module
        success: Whether the inspection succeeded
        error_message: If failed, the error message
    """

    docstring: str | None = None
    signature: str | None = None
    parent_docstring: str | None = None
    module_name: str | None = None
    object_path: str | None = None
    success: bool = False
    error_message: str | None = None


class InspectionTimeoutError(Exception):
    """Raised when an import operation times out."""


@contextmanager
def time_limit(seconds: int):
    """Context manager to enforce a time limit on code execution.

    Note: This uses SIGALRM which is not available on Windows.
    On Windows, this will silently disable timeout protection.

    Args:
        seconds: Maximum time allowed for execution
    """

    def signal_handler(_signum, _frame):
        raise InspectionTimeoutError("Import operation timed out")

    # Check if signal.SIGALRM is available (not on Windows)
    alarm_fn = getattr(signal, "alarm", None)
    if hasattr(signal, "SIGALRM") and alarm_fn is not None:
        old_handler = signal.signal(signal.SIGALRM, signal_handler)
        alarm_fn(seconds)
        try:
            yield
        finally:
            alarm_fn(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # On Windows, we can't use SIGALRM, so just proceed without timeout
        # Alternative: use threading.Timer or multiprocessing, but adds complexity
        yield


def _collect_referenced_names(source: str, object_path: str | None) -> list[str]:  # noqa: C901
    referenced_names: list[str] = []
    try:
        tree = ast.parse(source)
        # Find the AST node of the target SUT object
        target_node = None
        if object_path:
            parts = object_path.split(".")
            # Simple search for class or function def matching path parts
            current_node: ast.AST = tree
            for part in parts:
                found = False
                for child in ast.iter_child_nodes(current_node):
                    if (
                        isinstance(
                            child,
                            (
                                ast.FunctionDef,
                                ast.AsyncFunctionDef,
                                ast.ClassDef,
                            ),
                        )
                        and child.name == part
                    ):
                        current_node = child
                        found = True
                        break
                if not found:
                    break
            else:
                target_node = current_node
        if target_node is None:
            target_node = tree

        class NameCollector(ast.NodeVisitor):
            def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
                referenced_names.append(node.id)
                self.generic_visit(node)

            def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
                if isinstance(node.value, ast.Name):
                    referenced_names.append(f"{node.value.id}.{node.attr}")
                    referenced_names.append(node.value.id)
                self.generic_visit(node)

        NameCollector().visit(target_node)
    except Exception:  # noqa: BLE001, S110
        pass
    return referenced_names


class SUTInspector:
    """Safely inspects Python modules and objects to extract documentation and signatures.

    Usage:
        inspector = SUTInspector(project_root="/path/to/project")
        result = inspector.inspect_method("structlog.processors", "TimeStamper")

        if result.success:
            print(f"Docstring: {result.docstring}")
            print(f"Signature: {result.signature}")
        else:
            print(f"Inspection failed: {result.error_message}")
    """

    def __init__(self, project_root: str | None = None, import_timeout: int = 5):
        """Initialize the inspector.

        Args:
            project_root: Root directory of the project (added to sys.path for local imports)
            import_timeout: Maximum seconds to wait for an import (default: 5)
        """
        self.project_root = project_root
        self.import_timeout = import_timeout
        self._original_syspath = None

        if project_root and Path(project_root).exists() and project_root not in sys.path:
            sys.path.insert(0, project_root)

    def _safe_import(self, module_name: str) -> Any | None:
        """Safely import a module with timeout and exception handling.

        Args:
            module_name: Fully qualified module name (e.g., "structlog.processors")

        Returns:
            The imported module object, or None if import failed
        """
        try:
            # Attempt import with timeout protection
            with time_limit(self.import_timeout):
                return importlib.import_module(module_name)
        except InspectionTimeoutError:
            return None
        except ImportError:
            return None
        except Exception:  # noqa: BLE001
            # Importing a SUT module runs its top-level code, which may raise
            # arbitrary exceptions; degrade gracefully instead of crashing.
            return None

    def _traverse_object_path(self, module: Any, object_path: str) -> Any | None:
        """Traverse an object path using recursive getattr.

        Args:
            module: The starting module/object
            object_path: Dot-separated path (e.g., "processors.TimeStamper")

        Returns:
            The final object, or None if any step fails
        """
        if not object_path:
            return module

        parts = object_path.split(".")
        current = module
        missing = object()

        for part in parts:
            current = getattr(current, part, missing)
            if current is missing:
                return None

        return current

    def _extract_signature(self, obj: Any) -> str | None:
        """Extract the call signature of a function, method, or class.

        Args:
            obj: The object to inspect

        Returns:
            String representation of the signature, or None if extraction fails
        """
        try:
            sig = inspect.signature(obj)
            return str(sig)
        except (ValueError, TypeError):
            # Some built-in functions don't have inspectable signatures
            return None

    def _extract_docstring(self, obj: Any) -> str | None:
        """Extract the docstring of an object.

        Args:
            obj: The object to inspect

        Returns:
            The docstring, or None if not available
        """
        try:
            doc = inspect.getdoc(obj)
            return doc or None
        except Exception:  # noqa: BLE001
            # ``getdoc`` may touch a custom ``__doc__`` descriptor on the SUT
            # object that raises arbitrarily; treat any failure as "no docstring".
            return None

    def _extract_parent_context(self, obj: Any) -> str | None:
        """If the object is a method, extract the parent class docstring for context.

        Args:
            obj: The object to inspect

        Returns:
            Parent class docstring, or None if not applicable
        """
        try:
            # Check if it's a method (has __self__ or is defined in a class)
            if inspect.ismethod(obj):
                parent_class: type[object] | None = obj.__self__.__class__
                return inspect.getdoc(parent_class)

            # For unbound methods or classes, check __qualname__
            if (
                hasattr(obj, "__qualname__")
                and "." in obj.__qualname__
                and hasattr(obj, "__module__")
            ):
                module = sys.modules.get(obj.__module__)
                if module:
                    class_name = obj.__qualname__.rsplit(".", 1)[0]
                    parent_candidate = getattr(module, class_name, None)
                    if parent_candidate and inspect.isclass(parent_candidate):
                        parent_class = parent_candidate
                        return inspect.getdoc(parent_class)

            return None
        except Exception:  # noqa: BLE001
            # Reflection over arbitrary SUT objects may raise anything; the
            # parent-class context is best-effort, so fall back to None.
            return None

    def inspect_method(
        self, module_name: str, object_path: str | None = None
    ) -> SUTInspectionResult:
        """Safely inspect a method/function/class to extract documentation and signature.

        Args:
            module_name: Fully qualified module name (e.g., "structlog.processors")
            object_path: Path to the object within the module (e.g., "TimeStamper")
                        If None, inspects the module itself

        Returns:
            SUTInspectionResult containing the inspection results
        """
        result = SUTInspectionResult(module_name=module_name, object_path=object_path)

        # Step 1: Safe import
        module = self._safe_import(module_name)
        if module is None:
            result.error_message = f"Failed to import module '{module_name}'"
            return result

        # Step 2: Traverse to the target object
        if object_path:
            target_obj = self._traverse_object_path(module, object_path)
            if target_obj is None:
                result.error_message = f"Object '{object_path}' not found in module '{module_name}'"
                return result
        else:
            target_obj = module

        # Step 3: Extract documentation and signature
        result.docstring = self._extract_docstring(target_obj)
        result.signature = self._extract_signature(target_obj)
        result.parent_docstring = self._extract_parent_context(target_obj)

        # Mark as successful if we got at least something
        result.success = result.docstring is not None or result.signature is not None

        if not result.success:
            result.error_message = "No documentation or signature available"

        return result

    def format_context_string(self, result: SUTInspectionResult) -> str:
        """Format the inspection result into a human-readable context string for LLM prompts.

        Args:
            result: The inspection result to format

        Returns:
            Formatted string suitable for LLM context
        """
        if not result.success:
            return "Documentation unavailable."

        lines = []

        # Add focal method identification
        if result.module_name and result.object_path:
            lines.append(f"Focal Method: {result.module_name}.{result.object_path}")
        elif result.module_name:
            lines.append(f"Focal Module: {result.module_name}")

        # Add signature
        if result.signature:
            lines.append(f"Signature: {result.signature}")

        # Add docstring
        if result.docstring:
            lines.append(f"\nDocstring:\n{result.docstring}")

        # Add parent class context
        if result.parent_docstring:
            lines.append(f"\nParent Class Documentation:\n{result.parent_docstring}")

        return "\n".join(lines) if lines else "Documentation unavailable."

    def inspect_dependencies(  # noqa: C901, PLR0914, PLR0915
        self, module_name: str, object_path: str | None = None, max_deps: int = 10
    ) -> str:
        """Safely extract signatures and docstrings of dependencies referenced by SUT.

        Args:
            module_name: Fully qualified module name (e.g., "structlog.processors")
            object_path: Path to SUT object within the module. If None, inspects the module.
            max_deps: Maximum dependencies to return in the string.

        Returns:
            A formatted string describing the dependencies and their signatures.
        """
        module = self._safe_import(module_name)
        if module is None:
            return ""

        # Step 1: Find the target SUT object
        target_obj = module
        if object_path:
            target_obj = self._traverse_object_path(module, object_path)
            if target_obj is None:
                target_obj = module

        # Step 2: Attempt to retrieve module source and AST
        source = None
        with suppress(Exception):
            source = inspect.getsource(module)

        if not source:
            file_path = getattr(module, "__file__", None)
            if file_path and Path(file_path).exists():
                with suppress(Exception):
                    source = Path(file_path).read_text(encoding="utf-8")

        referenced_names = _collect_referenced_names(source, object_path) if source else []

        # Step 3: Resolve name objects in globals
        resolved_deps = {}

        # If AST parsing yielded no names, fallback to module dir()
        candidates = referenced_names or dir(module)
        frequencies = Counter(candidates)

        def is_valid_dep(obj: Any) -> bool:
            if obj is None:
                return False
            if hasattr(obj, "__module__") and obj.__module__ == "builtins":
                return False
            # ``obj in {...}`` would raise TypeError for unhashable module-level
            # values (e.g. a dict/list constant), so guard on ``isinstance`` first.
            if isinstance(obj, type) and obj in {
                str,
                int,
                float,
                bool,
                list,
                dict,
                set,
                tuple,
                bytes,
            }:
                return False
            # Check if it's class or callable function
            return inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj)

        for name, freq in frequencies.most_common():
            obj = None
            if "." in name:
                # E.g. math.sqrt
                parts = name.split(".")
                base_obj = module.__dict__.get(parts[0])
                if base_obj:
                    obj = getattr(base_obj, parts[1], None)
            else:
                obj = module.__dict__.get(name)

            if is_valid_dep(obj):
                # Avoid duplicate entries for the same object
                obj_id = id(obj)
                if obj_id not in resolved_deps:
                    resolved_deps[obj_id] = (name, obj, freq)

        # Sort by frequency descending
        sorted_deps = sorted(resolved_deps.values(), key=lambda x: x[2], reverse=True)  # noqa: FURB118

        if len(sorted_deps) > max_deps:
            truncated = sorted_deps[max_deps:]
            truncated_names = [item[0] for item in truncated]
            _logger.warning("Truncated SUT dependencies: %s", ", ".join(truncated_names))
            sorted_deps = sorted_deps[:max_deps]

        # Step 4: Format dependency details
        formatted_parts = []
        for name, obj, _ in sorted_deps:
            # Skip if it is the target SUT object itself
            if obj is target_obj:
                continue

            assert obj is not None

            try:
                if inspect.isclass(obj):
                    # For class, extract init signature
                    try:
                        sig = inspect.signature(obj.__init__)
                    except Exception:  # noqa: BLE001
                        sig = inspect.signature(obj)
                else:
                    sig = inspect.signature(obj)
                sig_str = str(sig)
            except Exception:  # noqa: BLE001
                sig_str = "(...)"

            try:
                doc = inspect.getdoc(obj)
                doc_str = doc.split("\n")[0] if doc else "No description available."
            except Exception:  # noqa: BLE001
                doc_str = "No description available."

            kind = "Class" if inspect.isclass(obj) else "Function"
            formatted_parts.append(
                f"### {kind}: {name}\nSignature: {name}{sig_str}\nDescription: {doc_str}"
            )

        return "\n\n".join(formatted_parts)

    def inspect_usage_examples(  # noqa: C901
        self,
        module_name: str,
        object_path: str | None = None,
        max_examples: int = 3,
    ) -> str:
        """Scan the project for call sites of the target SUT object and return examples.

        Args:
            module_name: Fully qualified SUT module name.
            object_path: SUT object path.
            max_examples: Maximum examples to return.

        Returns:
            A formatted string with code examples.
        """
        if not self.project_root:
            return ""

        target_name = (
            object_path.rsplit(".", 1)[-1] if object_path else module_name.rsplit(".", 1)[-1]
        )
        if not target_name:
            return ""

        examples: list[str] = []
        root_path = Path(self.project_root)

        # Scan python files
        py_files = list(root_path.glob("**/*.py"))
        # Prioritize non-test files, sort to be deterministic
        py_files = sorted([f for f in py_files if "test" not in f.name.lower()]) + sorted([
            f for f in py_files if "test" in f.name.lower()
        ])

        for file_path in py_files:
            if len(examples) >= max_examples:
                break
            try:
                content = file_path.read_text(encoding="utf-8")
                if target_name not in content:
                    continue

                tree = ast.parse(content)

                class UsageVisitor(ast.NodeVisitor):
                    def __init__(self, target: str):
                        self.target = target
                        self.found_examples: list[str] = []
                        self.current_function: ast.FunctionDef | ast.AsyncFunctionDef | None = None

                    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
                        old_func = self.current_function
                        self.current_function = node
                        self.generic_visit(node)
                        self.current_function = old_func

                    def visit_AsyncFunctionDef(  # noqa: N802
                        self, node: ast.AsyncFunctionDef
                    ) -> None:
                        old_func = self.current_function
                        self.current_function = node
                        self.generic_visit(node)
                        self.current_function = old_func

                    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
                        try:
                            func_str = ast.unparse(node.func)
                        except Exception:  # noqa: BLE001
                            func_str = ""
                        if self.target in func_str:
                            if self.current_function:
                                try:
                                    code = ast.unparse(self.current_function)
                                except Exception:  # noqa: BLE001
                                    code = ""
                            else:
                                try:
                                    code = ast.unparse(node)
                                except Exception:  # noqa: BLE001
                                    code = ""
                            if code and code not in self.found_examples:
                                self.found_examples.append(code)
                        self.generic_visit(node)

                visitor = UsageVisitor(target_name)
                visitor.visit(tree)

                for code in visitor.found_examples:
                    # Skip giant functions
                    if len(code.splitlines()) > 25:
                        continue
                    if code not in examples:
                        examples.append(code)
                        if len(examples) >= max_examples:
                            break
            except Exception:  # noqa: BLE001, S110
                pass

        if not examples:
            return ""

        formatted = []
        for i, code in enumerate(examples, 1):
            formatted.append(f"### Example {i}\n```python\n{code}\n```")
        return "\n\n".join(formatted)
