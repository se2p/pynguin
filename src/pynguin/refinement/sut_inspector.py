"""
Safe System Under Test (SUT) Introspection

This module provides tools to safely extract documentation and signatures from
Python modules and objects without crashing the pipeline due to import side effects.

Key Safety Features:
- Timeout protection for imports that hang
- Exception handling for modules with side effects
- Graceful degradation when inspection fails
- Sandbox-like isolation (limited by Python's capabilities)
"""

import importlib
import inspect
import sys
import signal
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from contextlib import contextmanager


@dataclass
class SUTInspectionResult:
    """
    Container for SUT inspection results.
    
    Attributes:
        docstring: The docstring of the method/function/class being tested
        signature: The call signature (e.g., "(self, fmt='%Y-%m-%d', key='timestamp')")
        parent_docstring: If the object is a method, the parent class docstring
        module_name: The resolved module name
        object_path: The path to the object within the module
        success: Whether the inspection succeeded
        error_message: If failed, the error message
    """
    docstring: Optional[str] = None
    signature: Optional[str] = None
    parent_docstring: Optional[str] = None
    module_name: Optional[str] = None
    object_path: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None


class TimeoutError(Exception):
    """Raised when an import operation times out"""
    pass


@contextmanager
def time_limit(seconds: int):
    """
    Context manager to enforce a time limit on code execution.
    
    Note: This uses SIGALRM which is not available on Windows.
    On Windows, this will silently disable timeout protection.
    
    Args:
        seconds: Maximum time allowed for execution
    """
    def signal_handler(signum, frame):
        raise TimeoutError("Import operation timed out")
    
    # Check if signal.SIGALRM is available (not on Windows)
    if hasattr(signal, 'SIGALRM'):
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
    """
    Safely inspects Python modules and objects to extract documentation and signatures.
    
    Usage:
        inspector = SUTInspector(project_root="/path/to/project")
        result = inspector.inspect_method("structlog.processors", "TimeStamper")
        
        if result.success:
            print(f"Docstring: {result.docstring}")
            print(f"Signature: {result.signature}")
        else:
            print(f"Inspection failed: {result.error_message}")
    """
    
    def __init__(self, project_root: Optional[str] = None, import_timeout: int = 5):
        """
        Initialize the inspector.
        
        Args:
            project_root: Root directory of the project (added to sys.path for local imports)
            import_timeout: Maximum seconds to wait for an import (default: 5)
        """
        self.project_root = project_root
        self.import_timeout = import_timeout
        self._original_syspath = None
        
        if project_root and os.path.exists(project_root):
            # Ensure project root is in sys.path for local module imports
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
    
    def _safe_import(self, module_name: str) -> Optional[Any]:
        """
        Safely import a module with timeout and exception handling.
        
        Args:
            module_name: Fully qualified module name (e.g., "structlog.processors")
        
        Returns:
            The imported module object, or None if import failed
        """
        try:
            # Attempt import with timeout protection
            with time_limit(self.import_timeout):
                module = importlib.import_module(module_name)
                return module
        except TimeoutError:
            print(f"Warning: Import of '{module_name}' timed out after {self.import_timeout}s")
            return None
        except ImportError as e:
            print(f"Warning: Could not import '{module_name}': {e}")
            return None
        except Exception as e:
            print(f"Warning: Unexpected error importing '{module_name}': {type(e).__name__}: {e}")
            return None
    
    def _traverse_object_path(self, module: Any, object_path: str) -> Optional[Any]:
        """
        Traverse an object path using recursive getattr.
        
        Args:
            module: The starting module/object
            object_path: Dot-separated path (e.g., "processors.TimeStamper")
        
        Returns:
            The final object, or None if any step fails
        """
        if not object_path:
            return module
        
        parts = object_path.split('.')
        current = module
        
        for part in parts:
            try:
                current = getattr(current, part)
            except AttributeError:
                print(f"Warning: '{part}' not found in {current}")
                return None
        
        return current
    
    def _extract_signature(self, obj: Any) -> Optional[str]:
        """
        Extract the call signature of a function, method, or class.
        
        Args:
            obj: The object to inspect
        
        Returns:
            String representation of the signature, or None if extraction fails
        """
        try:
            sig = inspect.signature(obj)
            return str(sig)
        except (ValueError, TypeError) as e:
            # Some built-in functions don't have inspectable signatures
            print(f"Warning: Could not extract signature: {e}")
            return None
    
    def _extract_docstring(self, obj: Any) -> Optional[str]:
        """
        Extract the docstring of an object.
        
        Args:
            obj: The object to inspect
        
        Returns:
            The docstring, or None if not available
        """
        try:
            doc = inspect.getdoc(obj)
            return doc if doc else None
        except Exception as e:
            print(f"Warning: Could not extract docstring: {e}")
            return None
    
    def _extract_parent_context(self, obj: Any) -> Optional[str]:
        """
        If the object is a method, extract the parent class docstring for context.
        
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
            if hasattr(obj, '__qualname__') and '.' in obj.__qualname__:
                # Try to get the class from the module
                if hasattr(obj, '__module__'):
                    module = sys.modules.get(obj.__module__)
                    if module:
                        class_name = obj.__qualname__.rsplit('.', 1)[0]
                        parent_class = getattr(module, class_name, None)
                        if parent_class and inspect.isclass(parent_class):
                            return inspect.getdoc(parent_class)
            
            return None
        except Exception as e:
            print(f"Warning: Could not extract parent context: {e}")
            return None
    
    def inspect_method(
        self, 
        module_name: str, 
        object_path: Optional[str] = None
    ) -> SUTInspectionResult:
        """
        Safely inspect a method/function/class to extract documentation and signature.
        
        Args:
            module_name: Fully qualified module name (e.g., "structlog.processors")
            object_path: Path to the object within the module (e.g., "TimeStamper")
                        If None, inspects the module itself
        
        Returns:
            SUTInspectionResult containing the inspection results
        """
        result = SUTInspectionResult(
            module_name=module_name,
            object_path=object_path
        )
        
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
        result.success = (result.docstring is not None or result.signature is not None)
        
        if not result.success:
            result.error_message = "No documentation or signature available"
        
        return result
    
    def format_context_string(self, result: SUTInspectionResult) -> str:
        """
        Format the inspection result into a human-readable context string for LLM prompts.
        
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


def inspect_from_focal_info(
    focal_method_name: str,
    module_alias: Optional[str],
    resolved_module_name: Optional[str],
    project_root: Optional[str] = None
) -> SUTInspectionResult:
    """
    Convenience function to inspect a focal method using information from AST analyzer.
    
    Args:
        focal_method_name: The method name (e.g., "logger.bind" or "TimeStamper")
        module_alias: The alias used in code (e.g., "sp", "module_0")
        resolved_module_name: The actual module name (e.g., "structlog.processors")
        project_root: Root directory for local module imports
    
    Returns:
        SUTInspectionResult
    """
    inspector = SUTInspector(project_root=project_root)
    
    if not resolved_module_name:
        return SUTInspectionResult(
            success=False,
            error_message="No module name provided"
        )
    
    # Parse the resolved_module_name to extract module and object path
    # e.g., "collections.Counter" -> module="collections", object="Counter"
    # e.g., "structlog.processors" -> module="structlog.processors", object from focal_method_name
    
    # Check if the last part of resolved_module_name looks like a class/function
    # (starts with uppercase or matches the focal_method_name)
    parts = resolved_module_name.split('.')
    
    # If focal_method_name (without alias prefix) matches the last part of resolved_module_name,
    # then the last part is the object, not part of the module path
    focal_name_base = focal_method_name.split('.')[-1] if '.' in focal_method_name else focal_method_name
    
    if parts[-1] == focal_name_base or (len(parts) > 1 and parts[-1][0].isupper()):
        # Last part is the object name
        module_name = '.'.join(parts[:-1]) if len(parts) > 1 else parts[0]
        object_path = parts[-1]
    else:
        # Entire resolved_module_name is the module path
        module_name = resolved_module_name
        object_path = focal_name_base
    
    return inspector.inspect_method(module_name, object_path)


# Example usage and testing
if __name__ == "__main__":
    print("=" * 80)
    print("SUTInspector Example Usage")
    print("=" * 80)
    
    # Example 1: Inspect a standard library function
    print("\n[Example 1] Inspecting os.path.join")
    print("-" * 80)
    inspector = SUTInspector()
    result = inspector.inspect_method("os.path", "join")
    
    if result.success:
        print(f"[OK] Success")
        print(f"Signature: {result.signature}")
        print(f"Docstring: {result.docstring[:100]}..." if result.docstring else "No docstring")
    else:
        print(f"[FAIL] Failed: {result.error_message}")
    
    # Example 2: Inspect a module that might not exist
    print("\n[Example 2] Inspecting non-existent module")
    print("-" * 80)
    result = inspector.inspect_method("nonexistent.module", "SomeClass")
    print(f"[FAIL] Expected failure: {result.error_message}")
    
    # Example 3: Format context string
    print("\n[Example 3] Formatted context for LLM")
    print("-" * 80)
    result = inspector.inspect_method("json", "dumps")
    context = inspector.format_context_string(result)
    print(context)
    
    # Example 4: Inspect a class constructor
    print("\n[Example 4] Inspecting a class")
    print("-" * 80)
    result = inspector.inspect_method("collections", "Counter")
    if result.success:
        print(f"[OK] Success")
        print(f"Signature: {result.signature}")
        print(f"Docstring preview: {result.docstring[:150]}..." if result.docstring else "No docstring")
    
    print("\n" + "=" * 80)
    print("Examples complete")
    print("=" * 80)
