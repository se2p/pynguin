#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides capabilities to export chromosomes."""

import ast
import dataclasses
import importlib.util
import logging
import sys
from pathlib import Path

import pynguin.ga.chromosomevisitor as cv
import pynguin.testcase.testcase_to_ast as tc_to_ast
import pynguin.utils.namingscope as ns

_LOGGER = logging.getLogger(__name__)


def _dotted_from_origin(origin: str) -> str | None:
    """Return the dotted module path derived from ``spec.origin``.

    Check the parent directory for __init__.py until none is found. Then get the path
    based on the first __init__.py found.

    Args:
        origin: The origin of the module spec.

    Returns:
        The dotted module path or None if the origin is not a file.
    """
    if not origin or origin in {"built-in", "frozen"}:
        return None

    module = Path(origin)
    if not module.is_file():
        return None

    # Walk upward while parent contains __init__.py
    module_root = module
    while (module_root.parent / "__init__.py").exists():
        module_root = module_root.parent

    if module_root.parent is None:
        return None

    rel = module.relative_to(module_root.parent)

    # If the resolved origin points to a package's __init__.py, use the directory
    # name as the canonical module path (e.g., pathlib/__init__.py -> pathlib).
    if rel.name == "__init__.py":
        rel = rel.parent
        return ".".join(rel.parts)

    return ".".join(rel.with_suffix("").parts)


def _canonical_module_name(name: str) -> str:
    """Return a fully qualified module name for use in import statements.

    Strategy:
    1) Try ``importlib.util.find_spec(name)`` and derive from ``spec.origin``.
    2) Fall back to ``spec.name`` if available.
    3) Otherwise, return ``name`` unchanged.

    Args:
        name: The module name.

    Returns:
        The fully qualified module name.
    """
    try:
        spec = importlib.util.find_spec(name)
    except Exception:  # noqa: BLE001
        spec = None

    if spec and getattr(spec, "origin", None):
        dotted = _dotted_from_origin(spec.origin)  # type: ignore[arg-type]
        if dotted:
            return dotted
    if spec and getattr(spec, "name", None):
        return spec.name

    return name


@dataclasses.dataclass
class _AstConversionResult:
    """Result of converting a test case and its assertions to AST."""

    test_case_ast_stmts: list[ast.stmt]
    """List of AST statement representing the converted test case"""

    exception_status: bool
    """Does the test case fail by default, i.e., raises an undeclared exception
    on execution?"""


class PyTestChromosomeToAstVisitor(cv.ChromosomeVisitor):
    """Visits chromosomes and builds a module AST containing all visited test cases."""

    def __init__(
        self,
        *,
        store_call_return: bool = False,
        no_xfail: bool = False,
        sut_module_name: str | None = None,
    ) -> None:
        """The module aliases are shared between test cases.

        Args:
            store_call_return: Whether to store the return value of function calls
                when the references are not used by the following statements.
            no_xfail: If True, unexpected exceptions will be wrapped with pytest.raises()
                instead of marking the test with @pytest.mark.xfail(strict=True).
            sut_module_name: The name of the system under test module. If provided and
                no test cases remain after empty test removal, the module will still be
                imported to ensure coverage is achieved by import alone.
        """
        self._module_aliases = ns.NamingScope("module")
        # Common modules (e.g. math) are not aliased.
        self._common_modules: set[str] = set()
        self._conversion_results: list[_AstConversionResult] = []
        self._store_call_return: bool = store_call_return
        self._no_xfail: bool = no_xfail
        self._sut_module_name: str | None = sut_module_name

    @property
    def module_aliases(self) -> ns.NamingScope:
        """Provides the module aliases that were used when transforming all test cases.

        Returns:
            The module aliases
        """
        return self._module_aliases

    @property
    def common_modules(self) -> set[str]:
        """Provides the common modules that were used when transforming all test cases.

        This is used, because common modules (e.g., math) should not be aliased.

        Returns:
            A set of the modules names
        """
        return self._common_modules

    def visit_test_suite_chromosome(self, chromosome) -> None:  # noqa: D102
        for test_case_chromosome in chromosome.test_case_chromosomes:
            test_case_chromosome.accept(self)

    def visit_test_case_chromosome(self, chromosome) -> None:  # noqa: D102
        visitor = tc_to_ast.TestCaseToAstVisitor(
            module_aliases=self._module_aliases,
            common_modules=self._common_modules,
            exec_result=chromosome.get_last_execution_result(),
            store_call_return=self._store_call_return,
            no_xfail=self._no_xfail,
        )
        chromosome.test_case.accept(visitor)
        self._conversion_results.append(
            _AstConversionResult(visitor.test_case_ast, visitor.is_failing_test)
        )

    @staticmethod
    def __create_ast_imports(
        module_aliases: ns.NamingScope, common_modules: set[str] | None = None
    ) -> list[ast.stmt]:
        imports: list[ast.stmt] = []
        if common_modules is not None:
            imports.extend(
                ast.Import(names=[ast.alias(name=module, asname=None)]) for module in common_modules
            )
        for module_name, alias in module_aliases:
            imports.append(
                ast.Import(
                    names=[
                        ast.alias(
                            name=_canonical_module_name(module_name),
                            asname=alias,
                        )
                    ]
                )
            )
        return imports

    @staticmethod
    def __create_functions(
        results: list[_AstConversionResult], *, with_self_arg: bool
    ) -> list[ast.stmt]:
        functions: list[ast.stmt] = []
        for i, result in enumerate(results):
            nodes = result.test_case_ast_stmts
            function_name = f"case_{i}"
            if len(nodes) == 0:
                nodes = [ast.Pass()]
            function_node = PyTestChromosomeToAstVisitor.__create_function_node(
                function_name,
                nodes,
                with_self_arg=with_self_arg,
                is_failing=result.exception_status,
            )
            functions.append(function_node)
        return functions

    @staticmethod
    def __create_function_node(
        function_name: str,
        nodes: list[ast.stmt],
        *,
        with_self_arg: bool,
        is_failing: bool,
    ) -> ast.FunctionDef:
        name = f"test_{function_name}"
        args = ast.arguments(
            args=[ast.Name(id="self", ctx="Param")] if with_self_arg else [],  # type: ignore[arg-type, list-item]
            defaults=[],
            vararg=None,
            kwarg=None,
            posonlyargs=[],
            kwonlyargs=[],
            kw_defaults=[],
        )
        decorator_list = PyTestChromosomeToAstVisitor.__create_decorator_list(is_failing)
        returns = None
        type_comment = None

        if sys.version_info >= (3, 12):
            return ast.FunctionDef(
                name=name,
                args=args,
                body=nodes,
                decorator_list=decorator_list,
                returns=returns,
                type_comment=type_comment,
                type_params=[],
            )

        return ast.FunctionDef(
            name=name,
            args=args,
            body=nodes,
            decorator_list=decorator_list,
            returns=returns,
            type_comment=type_comment,
        )

    @staticmethod
    def __create_decorator_list(is_failing: bool) -> list[ast.expr]:  # noqa: FBT001
        if is_failing:
            return [
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id="pytest", ctx=ast.Load()),
                            attr="mark",
                            ctx=ast.Load(),
                        ),
                        attr="xfail",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[ast.keyword(arg="strict", value=ast.Constant(value=True))],
                )
            ]
        return []

    def to_module(self) -> tuple[ast.Module, bool]:
        """Provides a module in PyTest style that contains all visited test cases.

        Returns:
            A tuple of (ast module containing all visited test cases, bool indicating
            whether coverage is achieved by import alone - i.e., no test cases remain).
        """
        if any(result.exception_status for result in self._conversion_results):
            self._common_modules.add("pytest")
        import_nodes = PyTestChromosomeToAstVisitor.__create_ast_imports(
            self._module_aliases, self._common_modules
        )
        functions = self.__create_functions(self._conversion_results, with_self_arg=False)

        coverage_by_import_only = False
        if len(functions) == 0 and self._sut_module_name is not None:
            coverage_by_import_only = True
            sut_import = ast.Import(
                names=[ast.alias(name=_canonical_module_name(self._sut_module_name), asname=None)]
            )
            import_nodes.append(sut_import)

        return ast.Module(body=import_nodes + functions, type_ignores=[]), coverage_by_import_only


_PYNGUIN_FILE_HEADER = (
    "# Test cases automatically generated by Pynguin (https://www.pynguin.eu).\n"
    "# Please check them before you use them.\n"
)

_COVERAGE_BY_IMPORT_COMMENT = "# Importing this module achieves coverage.\n"


def save_module_to_file(
    module: ast.Module,
    target: Path,
    *,
    format_with_black: bool = True,
    coverage_by_import_only: bool = False,
) -> None:
    """Saves an AST module to a file.

    Args:
        target: Destination file
        module: The AST module
        format_with_black: ast.unparse is not PEP-8 compliant, so we apply black
            on the result.
        coverage_by_import_only: If True, adds a comment explaining that importing
            the module achieves coverage, and appends '# noqa: F401' to the import
            statement to prevent it from being removed by linters.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open(mode="w", encoding="UTF-8") as file:
        file.write(_PYNGUIN_FILE_HEADER)
        output = ast.unparse(ast.fix_missing_locations(module))
        if format_with_black:
            # Import of black might cause problems if it is a SUT dependency,
            # so we only import it if we need it.
            import black  # noqa: PLC0415
            import black.parsing  # noqa: PLC0415

            try:
                output = black.format_str(output, mode=black.FileMode())
            except black.parsing.InvalidInput as e:
                _LOGGER.warning("Could not format the module '%s' with black: %s", target, e)

        if coverage_by_import_only:
            file.write(_COVERAGE_BY_IMPORT_COMMENT)
            output = output.rstrip("\n") + "  # noqa: F401\n"

        file.write(output)
