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
import operator
import signal
import sys
from collections import Counter
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

# Builtin scalar/container types that are never useful as reported dependencies.
_BUILTIN_DEP_TYPES: frozenset[type] = frozenset({
    str,
    int,
    float,
    bool,
    list,
    dict,
    set,
    tuple,
    bytes,
})

# Maximum number of source lines a usage example may span before being skipped.
_MAX_USAGE_EXAMPLE_LINES = 25


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


def _find_ast_node_for_path(tree: ast.Module, object_path: str | None) -> ast.AST:
    """Locate the AST node for a dotted object path within a parsed module.

    Args:
        tree: The parsed module AST.
        object_path: Dot-separated path to the target definition (e.g.
            ``"MyClass.my_method"``). If ``None`` or not found, the module node
            is returned.

    Returns:
        The AST node of the matched definition, or the module ``tree`` itself
        when no definition matches the given path.
    """
    if not object_path:
        return tree

    definition_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    current_node: ast.AST = tree
    for part in object_path.split("."):
        match = next(
            (
                child
                for child in ast.iter_child_nodes(current_node)
                if isinstance(child, definition_types) and child.name == part
            ),
            None,
        )
        if match is None:
            return tree
        current_node = match
    return current_node


class _ReferenceNameCollector(ast.NodeVisitor):
    """Collects the names and dotted attribute references used within a node."""

    def __init__(self) -> None:
        self.referenced_names: list[str] = []

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        self.referenced_names.append(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if isinstance(node.value, ast.Name):
            self.referenced_names.append(f"{node.value.id}.{node.attr}")
            self.referenced_names.append(node.value.id)
        self.generic_visit(node)


def _collect_referenced_names(source: str, object_path: str | None) -> list[str]:
    """Collect the names referenced by the SUT definition in the given source.

    Args:
        source: The module source code.
        object_path: Dot-separated path to the SUT definition. If ``None`` the
            whole module is scanned.

    Returns:
        A list of referenced names (plain names and ``base.attr`` references).
        Returns an empty list if the source cannot be parsed.
    """
    try:
        tree = ast.parse(source)
    except Exception:  # noqa: BLE001
        # Malformed or unparsable SUT source: degrade gracefully.
        return []

    target_node = _find_ast_node_for_path(tree, object_path)
    collector = _ReferenceNameCollector()
    collector.visit(target_node)
    return collector.referenced_names


class _UsageVisitor(ast.NodeVisitor):
    """Collects source of functions (or bare calls) that reference a target name."""

    def __init__(self, target: str) -> None:
        self.target = target
        self.found_examples: list[str] = []
        self.current_function: ast.FunctionDef | ast.AsyncFunctionDef | None = None

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        old_func = self.current_function
        self.current_function = node
        self.generic_visit(node)
        self.current_function = old_func

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if self._call_targets_name(node):
            code = self._unparse(self.current_function or node)
            if code and code not in self.found_examples:
                self.found_examples.append(code)
        self.generic_visit(node)

    def _call_targets_name(self, node: ast.Call) -> bool:
        func_str = self._unparse(node.func)
        return self.target in func_str

    @staticmethod
    def _unparse(node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:  # noqa: BLE001
            # ``unparse`` can fail on exotic nodes; treat as "no source".
            return ""


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

    def _resolve_target_object(self, module: Any, object_path: str | None) -> Any:
        """Resolve the SUT object within a module, falling back to the module.

        Args:
            module: The imported module.
            object_path: Path to the object within the module, or ``None``.

        Returns:
            The resolved object, or the ``module`` itself when the path is empty
            or cannot be resolved.
        """
        if not object_path:
            return module
        target_obj = self._traverse_object_path(module, object_path)
        return target_obj if target_obj is not None else module

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

    def _read_module_source(self, module: Any) -> str | None:
        """Retrieve the source code of a module.

        Tries :func:`inspect.getsource` first and falls back to reading the
        module's ``__file__`` from disk.

        Args:
            module: The imported module.

        Returns:
            The module source, or ``None`` if it cannot be obtained.
        """
        with suppress(Exception):
            source = inspect.getsource(module)
            if source:
                return source

        file_path = getattr(module, "__file__", None)
        if file_path and Path(file_path).exists():
            with suppress(Exception):
                return Path(file_path).read_text(encoding="utf-8")

        return None

    @staticmethod
    def _is_valid_dependency(obj: Any) -> bool:
        """Check whether an object is a useful dependency to report.

        Args:
            obj: The candidate dependency object.

        Returns:
            ``True`` if ``obj`` is a non-builtin class, function, or method.
        """
        if obj is None:
            return False
        if getattr(obj, "__module__", None) == "builtins":
            return False
        # ``obj in {...}`` would raise TypeError for unhashable module-level
        # values (e.g. a dict/list constant), so guard on ``isinstance`` first.
        if isinstance(obj, type) and obj in _BUILTIN_DEP_TYPES:
            return False
        return inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj)

    @staticmethod
    def _resolve_named_object(module: Any, name: str) -> Any | None:
        """Resolve a (possibly dotted) name against a module's global namespace.

        Args:
            module: The module whose ``__dict__`` provides the lookup scope.
            name: A plain name (``helper``) or a single-dotted reference
                (``math.sqrt``).

        Returns:
            The resolved object, or ``None`` if it cannot be resolved.
        """
        if "." not in name:
            return module.__dict__.get(name)
        base_name, attr_name = name.split(".", 1)
        base_obj = module.__dict__.get(base_name)
        if base_obj is None:
            return None
        return getattr(base_obj, attr_name, None)

    def _resolve_dependencies(
        self, module: Any, referenced_names: list[str], max_deps: int
    ) -> list[tuple[str, Any, int]]:
        """Resolve referenced names to dependency objects, ranked by frequency.

        Args:
            module: The imported SUT module.
            referenced_names: Names referenced by the SUT (empty to fall back to
                the module's ``dir()``).
            max_deps: Maximum number of dependencies to keep; the rest are logged
                and dropped.

        Returns:
            A list of ``(name, object, frequency)`` tuples sorted by descending
            frequency and truncated to ``max_deps``.
        """
        candidates = referenced_names or dir(module)
        frequencies = Counter(candidates)

        resolved_deps: dict[int, tuple[str, Any, int]] = {}
        for name, freq in frequencies.most_common():
            obj = self._resolve_named_object(module, name)
            if self._is_valid_dependency(obj):
                # Avoid duplicate entries for the same object.
                resolved_deps.setdefault(id(obj), (name, obj, freq))

        sorted_deps = sorted(resolved_deps.values(), key=operator.itemgetter(2), reverse=True)

        if len(sorted_deps) > max_deps:
            truncated_names = [item[0] for item in sorted_deps[max_deps:]]
            _logger.warning("Truncated SUT dependencies: %s", ", ".join(truncated_names))
            sorted_deps = sorted_deps[:max_deps]

        return sorted_deps

    @staticmethod
    def _extract_dependency_signature(obj: Any) -> str:
        """Extract a signature string for a dependency, with graceful fallbacks.

        For classes the ``__init__`` signature is preferred over the class'
        own signature.

        Args:
            obj: The dependency object.

        Returns:
            The signature string, or ``"(...)"`` if none can be determined.
        """
        try:
            if inspect.isclass(obj):
                try:
                    return str(inspect.signature(obj.__init__))
                except Exception:  # noqa: BLE001
                    return str(inspect.signature(obj))
            return str(inspect.signature(obj))
        except Exception:  # noqa: BLE001
            return "(...)"

    @staticmethod
    def _extract_dependency_description(obj: Any) -> str:
        """Extract the first docstring line of a dependency as a short description.

        Args:
            obj: The dependency object.

        Returns:
            The first line of the docstring, or a default placeholder.
        """
        default = "No description available."
        try:
            doc = inspect.getdoc(obj)
        except Exception:  # noqa: BLE001
            return default
        return doc.split("\n")[0] if doc else default

    def _format_dependency(self, name: str, obj: Any) -> str:
        """Format a single dependency into a markdown-style description block.

        Args:
            name: The name under which the dependency is referenced.
            obj: The dependency object.

        Returns:
            A formatted block describing the dependency's kind, signature, and
            description.
        """
        sig_str = self._extract_dependency_signature(obj)
        doc_str = self._extract_dependency_description(obj)
        kind = "Class" if inspect.isclass(obj) else "Function"
        return f"### {kind}: {name}\nSignature: {name}{sig_str}\nDescription: {doc_str}"

    def inspect_dependencies(
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

        target_obj = self._resolve_target_object(module, object_path)

        source = self._read_module_source(module)
        referenced_names = _collect_referenced_names(source, object_path) if source else []

        sorted_deps = self._resolve_dependencies(module, referenced_names, max_deps)

        formatted_parts = [
            self._format_dependency(name, obj)
            for name, obj, _ in sorted_deps
            # Skip the target SUT object itself.
            if obj is not target_obj
        ]
        return "\n\n".join(formatted_parts)

    def _resolve_usage_target_name(self, module_name: str, object_path: str | None) -> str:
        """Determine the simple name to search for in project call sites.

        Args:
            module_name: The fully qualified SUT module name.
            object_path: The SUT object path, if any.

        Returns:
            The trailing name segment of the object path or module name.
        """
        source = object_path or module_name
        return source.rsplit(".", 1)[-1]

    @staticmethod
    def _ordered_python_files(root_path: Path) -> list[Path]:
        """List the project's Python files, non-test files first, deterministically.

        Args:
            root_path: The project root to scan.

        Returns:
            A sorted list of ``.py`` files with non-test files ordered before
            test files.
        """
        py_files = list(root_path.glob("**/*.py"))
        non_test = sorted(f for f in py_files if "test" not in f.name.lower())
        test = sorted(f for f in py_files if "test" in f.name.lower())
        return non_test + test

    def _extract_examples_from_file(self, file_path: Path, target_name: str) -> list[str]:
        """Extract usage-example snippets referencing ``target_name`` from a file.

        Args:
            file_path: The Python file to scan.
            target_name: The simple SUT name to look for in call sites.

        Returns:
            The list of example snippets found (functions or bare calls). Returns
            an empty list on any read/parse error or when the name is absent.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            if target_name not in content:
                return []
            tree = ast.parse(content)
        except Exception:  # noqa: BLE001
            # Unreadable or unparsable file: skip silently.
            return []

        visitor = _UsageVisitor(target_name)
        visitor.visit(tree)
        return [
            code
            for code in visitor.found_examples
            # Skip giant functions.
            if len(code.splitlines()) <= _MAX_USAGE_EXAMPLE_LINES
        ]

    @staticmethod
    def _format_usage_examples(examples: list[str]) -> str:
        """Format collected usage examples into a markdown-style string.

        Args:
            examples: The example code snippets.

        Returns:
            A formatted string, or an empty string if there are no examples.
        """
        if not examples:
            return ""
        formatted = [
            f"### Example {i}\n```python\n{code}\n```" for i, code in enumerate(examples, 1)
        ]
        return "\n\n".join(formatted)

    def inspect_usage_examples(
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

        target_name = self._resolve_usage_target_name(module_name, object_path)
        if not target_name:
            return ""

        examples: list[str] = []
        for file_path in self._ordered_python_files(Path(self.project_root)):
            for code in self._extract_examples_from_file(file_path, target_name):
                if code not in examples:
                    examples.append(code)
                    if len(examples) >= max_examples:
                        break
            if len(examples) >= max_examples:
                break

        return self._format_usage_examples(examples)
