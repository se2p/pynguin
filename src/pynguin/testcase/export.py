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
import re
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
        pynguin_seed: int | None = None,
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
            pynguin_seed: The seed used by Pynguin. If provided, an autouse pytest
                fixture that reseeds Python's module-level random before each test
                will be emitted into the generated module.
        """
        self._module_aliases = ns.NamingScope("module")
        # Common modules (e.g. math) are not aliased.
        self._common_modules: set[str] = set()
        self._conversion_results: list[_AstConversionResult] = []
        self._store_call_return: bool = store_call_return
        self._no_xfail: bool = no_xfail
        self._sut_module_name: str | None = sut_module_name
        self._pynguin_seed: int | None = pynguin_seed

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

    @staticmethod
    def __create_patch_nodes(seed: int) -> list[ast.stmt]:
        """Build AST nodes for the deterministic random-seed patch.

        The patch is emitted at module level *before* any SUT imports so that
        Random instances created during import are already tracked.

        Args:
            seed: The Pynguin seed used to replace calls with a default argument of
                ``None``.

        Returns:
            A list of AST statements implementing the patch.
        """
        patch_source = (
            "import weakref as _pynguin_weakref\n"
            "if not getattr(random.Random.seed, '__pynguin_patched__', False):\n"
            "    _pynguin_orig_seed = random.Random.seed\n"
            "    _pynguin_tracked = _pynguin_weakref.WeakSet()\n"
            "    def _pynguin_deterministic_seed(self, x=None):\n"
            "        if x is None:\n"
            f"            x = {seed}\n"
            "        elif type(x).__hash__ is object.__hash__:\n"
            "            x = f'{type(x).__module__}.{type(x).__name__}'\n"
            "        _pynguin_orig_seed(self, x)\n"
            "        _pynguin_tracked.add(self)\n"
            "    _pynguin_deterministic_seed.__pynguin_patched__ = True\n"
            "    _pynguin_deterministic_seed.__pynguin_instances__ = _pynguin_tracked\n"
            "    random.Random.seed = _pynguin_deterministic_seed\n"
        )
        return ast.parse(patch_source).body

    @staticmethod
    def __create_seed_fixture(seed: int) -> ast.FunctionDef:
        """Build the autouse pytest fixture that reseeds random before each test.

        Args:
            seed: The Pynguin seed to use for reseeding.

        Returns:
            An AST FunctionDef for the ``_pynguin_seed_random`` fixture.
        """
        fixture_decorator = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="pytest", ctx=ast.Load()),
                attr="fixture",
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[ast.keyword(arg="autouse", value=ast.Constant(value=True))],
        )
        fixture_source = (
            f"random.seed({seed})\n"
            "_pynguin_instances = getattr(random.Random.seed, '__pynguin_instances__', None)\n"
            "if _pynguin_instances is not None:\n"
            "    for _inst in list(_pynguin_instances):\n"
            f"        _inst.seed({seed})\n"
        )
        fixture_body: list[ast.stmt] = [
            *ast.parse(fixture_source).body,
            ast.Expr(value=ast.Yield(value=None)),
        ]
        return ast.FunctionDef(
            name="_pynguin_seed_random",
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=fixture_body,
            decorator_list=[fixture_decorator],
            returns=None,
        )

    @staticmethod
    def __maybe_add_sut_import_for_coverage(
        import_nodes: list[ast.stmt],
        functions: list[ast.stmt],
        sut_module_name: str | None,
    ) -> bool:
        """Add a bare SUT import when no test functions exist.

        When Pynguin cannot generate any test functions, importing the SUT still
        provides coverage via side-effects at import time.  This helper mutates
        *import_nodes* and *functions* in place and returns whether the
        coverage-by-import path was taken.

        Args:
            import_nodes: The list of import statements to extend.
            functions: The list of test functions to extend.
            sut_module_name: The SUT module name, or ``None`` if not set.

        Returns:
            ``True`` if coverage-by-import was applied, ``False`` otherwise.
        """
        if functions or sut_module_name is None:
            return False
        import_nodes.append(
            ast.Import(names=[ast.alias(name=_canonical_module_name(sut_module_name), asname=None)])
        )
        functions.append(
            PyTestChromosomeToAstVisitor.__create_function_node(
                "empty", [ast.Pass()], with_self_arg=False, is_failing=False
            )
        )
        return True

    def to_module(self) -> tuple[ast.Module, bool]:
        """Provides a module in PyTest style that contains all visited test cases.

        Returns:
            A tuple of (ast module containing all visited test cases, bool indicating
            whether coverage is achieved by import alone - i.e., no test cases remain).
        """
        if any(result.exception_status for result in self._conversion_results):
            self._common_modules.add("pytest")
        functions = self.__create_functions(self._conversion_results, with_self_arg=False)

        coverage_by_import_only = False

        if self._pynguin_seed is not None:
            # The patch must be applied before any SUT imports, because importing
            # the SUT may create random.Random instances at module level.
            preamble_imports: list[ast.stmt] = [
                ast.Import(names=[ast.alias(name="random", asname=None)]),
                ast.Import(names=[ast.alias(name="pytest", asname=None)]),
            ]
            patch_nodes = self.__create_patch_nodes(self._pynguin_seed)

            # All remaining imports (SUT aliases + other common modules)
            remaining_common = self._common_modules - {"random", "pytest"}
            sut_import_nodes = PyTestChromosomeToAstVisitor.__create_ast_imports(
                self._module_aliases, remaining_common or None
            )

            coverage_by_import_only = self.__maybe_add_sut_import_for_coverage(
                sut_import_nodes, functions, self._sut_module_name
            )

            fixture_func = self.__create_seed_fixture(self._pynguin_seed)
            body = preamble_imports + patch_nodes + sut_import_nodes + [fixture_func] + functions

        else:
            import_nodes = PyTestChromosomeToAstVisitor.__create_ast_imports(
                self._module_aliases, self._common_modules
            )

            coverage_by_import_only = self.__maybe_add_sut_import_for_coverage(
                import_nodes, functions, self._sut_module_name
            )

            body = import_nodes + functions

        return ast.Module(body=body, type_ignores=[]), coverage_by_import_only


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
    module_name_with_coverage: str | None = None,
) -> None:
    """Saves an AST module to a file.

    Args:
        target: Destination file
        module: The AST module
        format_with_black: ast.unparse is not PEP-8 compliant, so we apply black
            on the result.
        module_name_with_coverage: If provided, adds a comment explaining that importing
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

        # Add a newline after the seed patch
        output = output.replace(
            "random.Random.seed = _pynguin_deterministic_seed",
            "random.Random.seed = _pynguin_deterministic_seed\n",
            1,
        )

        if module_name_with_coverage:
            file.write(_COVERAGE_BY_IMPORT_COMMENT)
            # Add
            pattern = re.compile(rf"^import {re.escape(module_name_with_coverage)}\b", re.MULTILINE)
            output = pattern.sub(rf"import {module_name_with_coverage}  # noqa: F401", output)

        file.write(output)
