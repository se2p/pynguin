#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""AST-based Focal Method Analyzer for Unit Test Refactoring.

This module provides tools to analyze Python test functions and identify:
1. The "Focal Method" (the method being tested - the "Act" phase)
2. The System Under Test (SUT) module context
3. Import mappings for resolving module aliases

The core logic:
- Find the first Assert node in the test function
- Find the last Call node that occurs before that assertion
- Extract the method name, line number, and resolved module path
"""

import ast
from dataclasses import dataclass


@dataclass
class FocalMethodInfo:
    """Container for focal method analysis results.

    Attributes:
        focal_method_name: The method name being tested
            (e.g., 'bind' or 'logger.bind')
        focal_line_number: The line number where the focal method call appears
        module_alias: The variable/alias used to call the method (e.g., 'logger', 'module_0')
        resolved_module_name: The actual module name after resolving imports (e.g., 'structlog')
        full_call_signature: The complete call as it appears in code
            (e.g., 'logger.bind(key="value")')
    """

    focal_method_name: str
    focal_line_number: int
    module_alias: str | None = None
    resolved_module_name: str | None = None
    full_call_signature: str | None = None


class ImportMapBuilder(ast.NodeVisitor):
    """Builds a mapping of import aliases to actual module names.

    Handles:
    - import foo as bar
    - from foo import Bar as Baz
    - import foo
    """

    def __init__(self):
        """Initialize import map builder."""
        self.import_map: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        """Handle: import foo, import foo as bar."""
        for alias in node.names:
            module_name = alias.name
            alias_name = alias.asname or alias.name
            self.import_map[alias_name] = module_name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        """Handle: from foo import Bar, from foo import Bar as Baz."""
        if node.module:
            for alias in node.names:
                # Store the full path: foo.Bar
                imported_name = alias.name
                alias_name = alias.asname or imported_name
                full_name = f"{node.module}.{imported_name}"
                self.import_map[alias_name] = full_name
        self.generic_visit(node)


class CallAndAssertCollector(ast.NodeVisitor):
    """Collects all Call nodes and Assert nodes in execution order.

    Handles nested structures:
    - try/except/finally blocks
    - with statements
    - if/elif/else branches
    - for/while loops
    """

    def __init__(self):
        """Initialize call and assert collector."""
        self.calls: list[tuple[ast.Call, int]] = []  # (Call node, line_number)
        self.first_assert_line: int | None = None

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Record all function/method calls with their line numbers."""
        line_number = getattr(node, "lineno", 0)
        self.calls.append((node, line_number))
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        """Record the first assertion encountered."""
        if self.first_assert_line is None:
            self.first_assert_line = getattr(node, "lineno", 0)
        self.generic_visit(node)


class FocalMethodAnalyzer:
    """Main analyzer class for identifying the focal method in a test function.

    Usage:
        analyzer = FocalMethodAnalyzer(test_source_code, import_context)
        result = analyzer.analyze()
        print(f"Focal method: {result.focal_method_name} at line {result.focal_line_number}")
    """

    def __init__(self, test_function_source: str, full_file_source: str | None = None):
        """Initialize the analyzer.

        Args:
            test_function_source: Source code of the test function to analyze
            full_file_source: Optional full file source for building complete import map.
                            If None, imports are extracted from test_function_source only.
        """
        self.test_function_source = test_function_source
        self.full_file_source = full_file_source or test_function_source
        self.import_map: dict[str, str] = {}
        self.focal_info: FocalMethodInfo | None = None

    def _build_import_map(self) -> dict[str, str]:
        """Parse the full file source to build import alias -> module name mapping.

        Returns:
            Dictionary mapping aliases to resolved module names
        """
        try:
            tree = ast.parse(self.full_file_source)
            builder = ImportMapBuilder()
            builder.visit(tree)
            return builder.import_map
        except SyntaxError:
            return {}

    def _extract_call_info(self, call_node: ast.Call) -> tuple[str, str | None]:
        """Extract method name and module alias from a Call node.

        Args:
            call_node: The AST Call node to analyze

        Returns:
            Tuple of (method_name, module_alias)
            - method_name: e.g., 'bind', 'logger.bind', 'TimeStamper'
            - module_alias: e.g., 'logger', 'module_0', 'structlog_processors'
        """
        # Case 1: module.method() or obj.method()
        if isinstance(call_node.func, ast.Attribute):
            method_name = call_node.func.attr

            # Get the receiver (e.g., 'logger' in logger.bind())
            if isinstance(call_node.func.value, ast.Name):
                module_alias = call_node.func.value.id
                full_method_name = f"{module_alias}.{method_name}"
                return full_method_name, module_alias

            # Handle chained calls like foo.bar.baz()
            full_method_name = (
                ast.unparse(call_node.func) if hasattr(ast, "unparse") else method_name
            )
            return full_method_name, None

        # Case 2: Direct function call like TimeStamper() or func()
        if isinstance(call_node.func, ast.Name):
            func_name = call_node.func.id
            return func_name, func_name

        # Case 3: Complex expression (e.g., dict['key']() or lambda())
        try:
            full_name = ast.unparse(call_node.func) if hasattr(ast, "unparse") else "unknown_call"
            return full_name, None
        except Exception:  # noqa: BLE001
            return "unknown_call", None

    def _resolve_module_name(self, alias: str | None) -> str | None:
        """Resolve a module alias to its actual module name using the import map.

        Args:
            alias: The alias used in the code (e.g., 'logger', 'module_0')

        Returns:
            The resolved module name (e.g., 'structlog') or None if not found
        """
        if alias and alias in self.import_map:
            return self.import_map[alias]
        return None

    def _find_focal_method(self) -> FocalMethodInfo | None:
        """Core logic: Find the last Call before the first Assert.

        Algorithm:
        1. Collect all Call nodes and their line numbers
        2. Find the line number of the first Assert
        3. Select the last Call that occurs before that assertion
        4. If no assertion exists, default to the last Call in the function

        Returns:
            FocalMethodInfo object or None if no calls found
        """
        try:
            tree = ast.parse(self.test_function_source)
        except SyntaxError:
            return None

        # Collect all calls and assertions
        collector = CallAndAssertCollector()
        collector.visit(tree)

        if not collector.calls:
            return None  # No function calls in the test

        # Filter calls that occur before the first assertion
        if collector.first_assert_line is not None:
            calls_before_assert = [
                (call, line) for call, line in collector.calls if line < collector.first_assert_line
            ]

            if calls_before_assert:
                # Take the last call before the assertion
                focal_call, focal_line = calls_before_assert[-1]
            else:
                # Edge case: All calls are inside assertions (rare)
                # Fall back to the last call overall
                focal_call, focal_line = collector.calls[-1]
        else:
            # No assertion found; use the last call in the function
            focal_call, focal_line = collector.calls[-1]

        # Extract method name and alias
        method_name, module_alias = self._extract_call_info(focal_call)
        resolved_module = self._resolve_module_name(module_alias)

        # Try to get the full call signature
        try:
            full_signature = ast.unparse(focal_call) if hasattr(ast, "unparse") else method_name
        except Exception:  # noqa: BLE001
            full_signature = method_name

        return FocalMethodInfo(
            focal_method_name=method_name,
            focal_line_number=focal_line,
            module_alias=module_alias,
            resolved_module_name=resolved_module,
            full_call_signature=full_signature,
        )

    def analyze(self) -> FocalMethodInfo | None:
        """Perform the complete analysis pipeline.

        Returns:
            FocalMethodInfo object containing the analysis results, or None if analysis fails
        """
        # Step 1: Build import map from full file
        self.import_map = self._build_import_map()

        # Step 2: Find the focal method
        self.focal_info = self._find_focal_method()

        return self.focal_info
