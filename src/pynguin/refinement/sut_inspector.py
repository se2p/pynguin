#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""SUT inspector: extracts docstrings and signatures via importlib."""

import importlib
import inspect
import signal
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    if hasattr(signal, "SIGALRM"):
        old_handler = signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # On Windows, we can't use SIGALRM, so just proceed without timeout
        # Alternative: use threading.Timer or multiprocessing, but adds complexity
        yield


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

        for part in parts:
            try:
                current = getattr(current, part)
            except AttributeError:  # noqa: PERF203
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
                parent_class = obj.__self__.__class__
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
                    parent_class = getattr(module, class_name, None)
                    if parent_class and inspect.isclass(parent_class):
                        return inspect.getdoc(parent_class)

            return None
        except Exception:  # noqa: BLE001
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
