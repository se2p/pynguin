#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides capabilities to export chromosomes."""

import ast
import dataclasses

from pathlib import Path

import pynguin.ga.chromosomevisitor as cv
import pynguin.testcase.testcase_to_ast as tc_to_ast
import pynguin.utils.namingscope as ns


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
    ) -> None:
        """The module aliases are shared between test cases.

        Args:
            store_call_return: Whether to store the return value of function calls
                when the references are not used by the following statements.
        """
        self._module_aliases = ns.NamingScope("module")
        # Common modules (e.g. math) are not aliased.
        self._common_modules: set[str] = set()
        self._conversion_results: list[_AstConversionResult] = []
        self._store_call_return: bool = store_call_return

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
                            name=module_name,
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
        return ast.FunctionDef(
            name=f"test_{function_name}",
            args=ast.arguments(
                args=[ast.Name(id="self", ctx="Param")] if with_self_arg else [],  # type: ignore[arg-type, list-item]
                defaults=[],
                vararg=None,
                kwarg=None,
                posonlyargs=[],
                kwonlyargs=[],
                kw_defaults=[],
            ),
            body=nodes,
            decorator_list=PyTestChromosomeToAstVisitor.__create_decorator_list(is_failing),
            returns=None,
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

    def to_module(self) -> ast.Module:
        """Provides a module in PyTest style that contains all visited test cases.

        Returns:
            An ast module containing all visited test cases.
        """
        import_nodes = PyTestChromosomeToAstVisitor.__create_ast_imports(
            self._module_aliases, self._common_modules
        )
        functions = self.__create_functions(self._conversion_results, with_self_arg=False)
        return ast.Module(body=import_nodes + functions, type_ignores=[])


_PYNGUIN_FILE_HEADER = (
    "# Test cases automatically generated by Pynguin (https://www.pynguin.eu).\n"
    "# Please check them before you use them.\n"
)


def save_module_to_file(
    module: ast.Module, target: Path, *, format_with_black: bool = True
) -> None:
    """Saves an AST module to a file.

    Args:
        target: Destination file
        module: The AST module
        format_with_black: ast.unparse is not PEP-8 compliant, so we apply black
            on the result.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open(mode="w", encoding="UTF-8") as file:
        file.write(_PYNGUIN_FILE_HEADER)
        output = ast.unparse(ast.fix_missing_locations(module))
        if format_with_black:
            # Import of black might cause problems if it is a SUT dependency,
            # so we only import it if we need it.
            import black  # noqa: PLC0415

            output = black.format_str(output, mode=black.FileMode())
        file.write(output)
