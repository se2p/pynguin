#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import tempfile
from pathlib import Path
from unittest import mock

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.ga.testcasechromosome as tcc
import pynguin.generator as gen
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.assertion.assertiongenerator import AssertionGenerator
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase import export
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.export import PyTestChromosomeToAstVisitor
from tests.testutils import extract_test_case_0


def test_export_sequence(exportable_test_case, tmp_path):
    path = tmp_path / "generated.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case.accept(exporter)
    exportable_test_case.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.accessibles.accessible as module_0


def test_case_0():
    int_0 = 5
    some_type_0 = module_0.SomeType(int_0)
    assert some_type_0 == 5
    float_0 = 42.23
    float_1 = module_0.simple_function(float_0)
    assert float_1 == pytest.approx(42.23, abs=0.01, rel=0.01)


def test_case_1():
    int_0 = 5
    some_type_0 = module_0.SomeType(int_0)
    assert some_type_0 == 5
    float_0 = 42.23
    float_1 = module_0.simple_function(float_0)
    assert float_1 == pytest.approx(42.23, abs=0.01, rel=0.01)
"""
    )


def test_export_survives_black_import_failure(exportable_test_case, tmp_path, monkeypatch):
    """A failing ``import black`` must not discard the generated tests.

    Regression test: black is imported lazily to format the output. If importing
    black raises (e.g. the SUT on sys.path shadows one of black's dependencies and
    black's module-level code crashes), the exporter must still write the full,
    unformatted test module -- not just the two-line header.
    """
    import sys  # noqa: PLC0415

    # ``import black`` raises ImportError when its sys.modules entry is None,
    # simulating black's import blowing up.
    monkeypatch.setitem(sys.modules, "black", None)
    monkeypatch.setitem(sys.modules, "black.parsing", None)

    path = tmp_path / "generated.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path, format_with_black=True)

    content = path.read_text()
    assert content.startswith(export._PYNGUIN_FILE_HEADER)
    # The test body survived: the file is more than the bare header.
    assert content != export._PYNGUIN_FILE_HEADER
    assert "def test_case_0():" in content
    assert "module_0.simple_function" in content


def test_export_sequence_expected_exception(
    exportable_test_case_with_expected_asserted_exception, tmp_path
):
    """An expected asserted exception is an exception that was raised and is expected.

    It is expected because the SUT code declares that it may raise this exception
    or has an assert statement.
    It is asserted because an assertion for that exception was generated, which leads
    to a ``with pytest.raises(...):`` statement.
    """
    path = tmp_path / "expected_asserted_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case_with_expected_asserted_exception.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.accessibles.accessible as module_0


def test_case_0():
    float_0 = 42.23
    with pytest.raises(ValueError):
        module_0.simple_function(float_0)
"""
    )


def test_export_sequence_unexpected_exception(
    exportable_test_case_with_expected_not_asserted_exception, tmp_path
):
    """An expected not asserted exception is an exception that was raised and is not expected.

    It is expected because the SUT code declares that it may raise this exception
    or has an assert statement.
    No assertion for the exception was generated, thus the exported test case passes.
    """
    path = tmp_path / "expected_not_asserted_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case_with_expected_not_asserted_exception.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import tests.fixtures.accessibles.accessible as module_0


def test_case_0():
    float_0 = 42.23
    module_0.simple_function(float_0)
"""
    )


def test_export_lambda(exportable_test_case_with_lambda, tmp_path):
    path = tmp_path / "generated_with_unexpected_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor(store_call_return=True)
    exportable_test_case_with_lambda.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import tests.conftest as module_0


def test_case_0():
    int_0 = 1
    int_1 = module_0.just_z(int_0)
"""
    )


def test_export_lambda_complex(exportable_test_case_with_lambda_complex, tmp_path):
    path = tmp_path / "generated_with_unexpected_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor(store_call_return=True)
    exportable_test_case_with_lambda_complex.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import tests.conftest as module_0


def test_case_0():
    complex_0 = 3 + 4j
    complex_1 = 1 + 0j
    float_0 = 0.1
    float_1 = 0.3
    complex_2 = module_0.weighted_avg(complex_0, complex_1, float_0, float_1)
"""
    )


def test_invalid_export(exportable_test_case, tmp_path):
    path = tmp_path / "invalid.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case.accept(exporter)

    from black.parsing import InvalidInput  # noqa: PLC0415

    with mock.patch("black.format_str", side_effect=InvalidInput("Invalid input")):
        module_ast, _ = exporter.to_module()
        export.save_module_to_file(module_ast, path)

    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.accessibles.accessible as module_0

def test_case_0():
    int_0 = 5
    some_type_0 = module_0.SomeType(int_0)
    assert some_type_0 == 5
    float_0 = 42.23
    float_1 = module_0.simple_function(float_0)
    assert float_1 == pytest.approx(42.23, abs=0.01, rel=0.01)"""
    )


def _imports_from_module(module: ast.Module) -> list[ast.Import]:
    """Collect plain import statements from a module AST."""
    return [node for node in module.body if isinstance(node, ast.Import)]


@pytest.mark.parametrize(
    ("module_name", "expected_canonical"),
    [
        # Single-file stdlib module
        ("pathlib", "pathlib"),
        # Dotted stdlib submodule that resolves to a file
        ("importlib.util", "importlib.util"),
        # Built-in module falls back to spec.name
        ("builtins", "builtins"),
        # Compiled extension module (e.g., array.cpython-310-darwin.so) should strip suffix
        ("array", "array"),
        # Local package module from this project
        ("src.pynguin.utils.namingscope", "pynguin.utils.namingscope"),
        ("pynguin.utils.namingscope", "pynguin.utils.namingscope"),
        # Non-existent name falls back to the provided name unchanged
        ("_pynguin_this_does_not_exist_", "_pynguin_this_does_not_exist_"),
    ],
)
def test_canonical_module_name(module_name: str, expected_canonical: str) -> None:
    """Test that various module names are canonicalised as expected."""
    visitor = PyTestChromosomeToAstVisitor()

    # Register an alias for the module name to force creation of an import with alias.
    alias_name = visitor.module_aliases.get_name(module_name)

    module_ast, _ = visitor.to_module()

    imports = _imports_from_module(module_ast)

    # Find the import that uses our alias and verify its name is canonicalised.
    matched: list[str] = []
    for imp in imports:
        matched.extend(alias.name for alias in imp.names if alias.asname == alias_name)

    # Exactly one import should match the alias we registered
    assert matched == [expected_canonical]


def _install_shadow_pkg(tmp_path: Path, monkeypatch) -> None:
    """Install ``shadowpkg`` where a ``retry`` function shadows the ``retry`` submodule."""
    import sys  # noqa: PLC0415

    pkg = tmp_path / "shadowpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from shadowpkg.retry import Retryer\n\n\ndef retry(*a, **k):\n    return Retryer()\n"
    )
    (pkg / "retry.py").write_text("class Retryer:\n    pass\n\n\ndef retry_all(x):\n    return x\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in ("shadowpkg", "shadowpkg.retry"):
        monkeypatch.delitem(sys.modules, name, raising=False)


def test_is_shadowed_submodule(tmp_path: Path, monkeypatch) -> None:
    _install_shadow_pkg(tmp_path, monkeypatch)
    # The submodule is shadowed by a same-named function on the package.
    assert export._is_shadowed_submodule("shadowpkg.retry") is True
    # A dotless name and a genuine (non-shadowed) module are not shadowed.
    assert export._is_shadowed_submodule("shadowpkg") is False
    assert export._is_shadowed_submodule("importlib.util") is False


def test_shadowed_submodule_uses_importlib_import(tmp_path: Path, monkeypatch) -> None:
    _install_shadow_pkg(tmp_path, monkeypatch)

    visitor = PyTestChromosomeToAstVisitor()
    alias_name = visitor.module_aliases.get_name("shadowpkg.retry")
    module_ast, _ = visitor.to_module()

    # The alias must be bound via importlib.import_module, not a plain `import ... as`,
    # and a plain top-level `import importlib` must be present to support it.
    assert any(
        isinstance(node, ast.Import) and any(a.name == "importlib" for a in node.names)
        for node in module_ast.body
    )
    assigns = [
        node
        for node in module_ast.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == alias_name
    ]
    assert len(assigns) == 1
    call = assigns[0].value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Attribute)
    assert call.func.attr == "import_module"
    assert isinstance(call.args[0], ast.Constant)
    assert call.args[0].value == "shadowpkg.retry"

    # Executing the generated import block binds the real module (exposes Retryer),
    # whereas a plain `import shadowpkg.retry as x` would bind the shadowing function.
    import_block = ast.Module(
        body=[n for n in module_ast.body if isinstance(n, ast.Import | ast.Assign)],
        type_ignores=[],
    )
    namespace: dict = {}
    exec(compile(ast.fix_missing_locations(import_block), "<gen>", "exec"), namespace)  # noqa: S102
    assert hasattr(namespace[alias_name], "Retryer")


def _make_namespace_package(tmp_path: Path) -> Path:
    """Create ``google/auth/_helpers.py`` with ``google`` a PEP 420 namespace package."""
    auth = tmp_path / "google" / "auth"
    auth.mkdir(parents=True)
    (auth / "__init__.py").write_text("")
    helpers = auth / "_helpers.py"
    helpers.write_text("")
    # Intentionally no ``google/__init__.py`` -> ``google`` is a namespace package.
    return helpers


def test_dotted_from_origin_drops_namespace_prefix(tmp_path: Path) -> None:
    # Documents the raw filesystem derivation the canonical-name guard compensates
    # for: climbing while __init__.py exists stops at the namespace boundary.
    helpers = _make_namespace_package(tmp_path)
    assert export._dotted_from_origin(str(helpers)) == "auth._helpers"


def test_canonical_module_name_keeps_namespace_package_prefix(tmp_path: Path, monkeypatch) -> None:
    # `google.auth._helpers` must not collapse to the unimportable `auth._helpers`.
    helpers = _make_namespace_package(tmp_path)

    def fake_find_spec(name: str):
        if name == "google.auth._helpers":
            return importlib.util.spec_from_file_location(name, str(helpers))
        # The namespace-stripped name does not import.
        return None

    monkeypatch.setattr(export.importlib.util, "find_spec", fake_find_spec)

    assert export._canonical_module_name("google.auth._helpers") == "google.auth._helpers"


def test_export_integration(subject_properties: SubjectProperties, tmp_path: Path):
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    config.configuration.module_name = module_name
    config.configuration.algorithm = config.Algorithm.DYNAMOSA
    config.configuration.stopping.maximum_iterations = 20
    config.configuration.search_algorithm.min_initial_tests = 10
    config.configuration.search_algorithm.max_initial_tests = 10
    config.configuration.search_algorithm.population = 20
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    config.configuration.seeding.seed = 1
    config.configuration.test_case_output.output_path = tmp_path
    gen._setup_random_number_generator()

    expected = (
        export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.examples.unasserted_exceptions as module_0


def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)


@pytest.mark.xfail(strict=True)
def test_case_1():
    none_type_0 = None
    module_0.foo(none_type_0)
"""
    )

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(module_name)
        search_algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        test_cases = search_algorithm.generate_tests()
        assert test_cases.size() >= 0

        target_file = Path(config.configuration.test_case_output.output_path).resolve() / "test.py"
        export_visitor = export.PyTestChromosomeToAstVisitor(store_call_return=False)
        test_cases.accept(export_visitor)
        module_ast, coverage_by_import_only = export_visitor.to_module()
        export.save_module_to_file(
            module_ast,
            target_file,
            format_with_black=config.configuration.test_case_output.format_with_black,
            module_name_with_coverage=module_name if coverage_by_import_only else None,
        )
    assert target_file.exists()
    content = target_file.read_text(encoding="utf-8")
    assert expected == content


def _import_execute_export(
    module_name: str,
    test_case_code: str,
    *,
    store_call_return: bool = True,
    no_xfail: bool = False,
) -> str:
    """Import a test case, execute it and export it again.

    Args:
        module_name: The name of the SUT module.
        test_case_code: The test case code to add assertions for.
        store_call_return: Whether to store the return value of each call.
        no_xfail: If True, unexpected exceptions will be wrapped with pytest.raises()
            instead of marking the test with @pytest.mark.xfail(strict=True).

    Returns:
        The exported test case.
    """
    subject_properties = SubjectProperties()
    config.configuration.module_name = module_name
    test_case_code = "import " + module_name + " as module_0\n\n" + test_case_code

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        test_cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(
            test_cluster=test_cluster,
            create_assertions=False,
            constant_provider=EmptyConstantProvider(),
        )
        transformer.visit(ast.parse(test_case_code))
        assert transformer.testcases, "No test case parsed from seed source"
        test_case_chrom = tcc.TestCaseChromosome(transformer.testcases[0])

        with install_import_hook(module_name, subject_properties):
            with subject_properties.instrumentation_tracer:
                module = importlib.import_module(module_name)
                importlib.reload(module)

            executor = TestCaseExecutor(subject_properties)
            execution_result = executor.execute(test_case_chrom.test_case)
            test_case_chrom.set_last_execution_result(execution_result)

            if no_xfail:
                assertion_generator = AssertionGenerator(executor, filtering_executions=0)
                assertion_generator.visit_test_case_chromosome(test_case_chrom)

            export_path = tmp_path / "test_with_assertions.py"
            exporter = export.PyTestChromosomeToAstVisitor(
                store_call_return=store_call_return, no_xfail=no_xfail
            )
            test_case_chrom.accept(exporter)
            module_ast, coverage_by_import_only = exporter.to_module()
            export.save_module_to_file(
                module_ast,
                export_path,
                format_with_black=config.configuration.test_case_output.format_with_black,
                module_name_with_coverage=module_name if coverage_by_import_only else None,
            )

        exported = export_path.read_text(encoding="utf-8")
        return extract_test_case_0(exported)


@pytest.mark.parametrize(
    "module_name,test_case_code,expected_code,store_call_return",
    [
        # Simple example
        (
            "tests.fixtures.accessibles.accessible",
            """def test_case_0():
    int_0 = 5
    some_type_0 = module_0.SomeType(int_0)
    float_0 = 42.23
    float_1 = module_0.simple_function(float_0)""",
            None,
            True,
        ),
        # Don't add @pytest.mark.xfail(strict=True) for a non-failing test
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)""",
            None,
            True,
        ),
        # Remove @pytest.mark.xfail(strict=True) for a non-failing test
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)""",
            """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)""",
            True,
        ),
        # Keep @pytest.mark.xfail(strict=True) for a failing test
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)""",
            None,
            True,
        ),
        # Add @pytest.mark.xfail(strict=True) for a failing test
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)""",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)""",
            True,
        ),
        # The same cases with store_call_return=False
        (
            "tests.fixtures.accessibles.accessible",
            """def test_case_0():
    int_0 = 5
    module_0.SomeType(int_0)
    float_0 = 42.23
    module_0.simple_function(float_0)""",
            None,
            False,
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)""",
            None,
            False,
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)""",
            """def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)""",
            False,
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    module_0.foo(none_type_0)""",
            None,
            False,
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    none_type_0 = None
    module_0.foo(none_type_0)""",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    module_0.foo(none_type_0)""",
            False,
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)
    module_0.foo(bool_1)""",
            None,
            False,
        ),
    ],
)
def test_import_export_parameterized(
    module_name: str, test_case_code: str, expected_code: str | None, *, store_call_return: bool
) -> None:
    exported = _import_execute_export(
        module_name, test_case_code, store_call_return=store_call_return
    )
    if expected_code is None:
        assert exported == test_case_code
    else:
        assert exported == expected_code


@pytest.mark.parametrize(
    "module_name,test_case_code,expected_code",
    [
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)""",
            """def test_case_0():
    none_type_0 = None
    with pytest.raises(AssertionError):
        bool_0 = module_0.foo(none_type_0)""",
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)""",
            """def test_case_0():
    none_type_0 = None
    with pytest.raises(AssertionError):
        bool_0 = module_0.foo(none_type_0)""",
        ),
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)""",
            """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)
    assert bool_1 is False""",
        ),
    ],
)
def test_import_export_no_xfail(
    module_name: str, test_case_code: str, expected_code: str | None
) -> None:
    exported = _import_execute_export(module_name, test_case_code, no_xfail=True)
    if expected_code is None:
        assert exported == test_case_code
    else:
        assert exported == expected_code


def test_coverage_by_import_only(tmp_path: Path) -> None:
    """When no test cases exist, SUT is imported with coverage comment and an empty test."""
    module_name = "tests.fixtures.accessibles.accessible"
    visitor = export.PyTestChromosomeToAstVisitor(sut_module_name=module_name)

    module_ast, coverage_by_import_only = visitor.to_module()

    assert coverage_by_import_only is True

    target_file = tmp_path / "test_coverage_by_import.py"
    export.save_module_to_file(
        module_ast,
        target_file,
        format_with_black=False,
        module_name_with_coverage=module_name if coverage_by_import_only else None,
    )

    content = target_file.read_text(encoding="utf-8")

    assert "# Importing this module achieves coverage." in content
    assert "import tests.fixtures.accessibles.accessible  # noqa: F401" in content
    assert "def test_empty():" in content


def test_to_module_with_seed_emits_patch_preamble_and_fixture(exportable_test_case, tmp_path):
    path = tmp_path / "seeded.py"
    exporter = export.PyTestChromosomeToAstVisitor(pynguin_seed=42)
    exportable_test_case.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    text = path.read_text()
    assert "import random" in text
    assert "__pynguin_patched__" in text
    assert "_pynguin_seed_random" in text
    assert "random.seed(42)" in text


def test_to_module_without_seed_no_patch_preamble_and_fixture(exportable_test_case, tmp_path):
    path = tmp_path / "no_seed.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case.accept(exporter)
    module_ast, _ = exporter.to_module()
    export.save_module_to_file(module_ast, path)
    text = path.read_text()
    assert "__pynguin_patched__" not in text
    assert "_pynguin_seed_random" not in text
