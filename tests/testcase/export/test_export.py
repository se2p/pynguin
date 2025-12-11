#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import tempfile
from logging import Logger
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.ga.testcasechromosome as tcc
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase import export
from pynguin.testcase.execution import TestCaseExecutor
from tests.testutils import (
    execute_test_with_pytest,
    execute_with_pytest,
)


def test_export_sequence(exportable_test_case, tmp_path):
    path = tmp_path / "generated.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case.accept(exporter)
    exportable_test_case.accept(exporter)
    export.save_module_to_file(exporter.to_module(), path)
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
    export.save_module_to_file(exporter.to_module(), path)
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
    export.save_module_to_file(exporter.to_module(), path)
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
    export.save_module_to_file(exporter.to_module(), path)
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
    export.save_module_to_file(exporter.to_module(), path)
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
        export.save_module_to_file(exporter.to_module(), path)

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
    config.configuration.test_case_output.output_path = tmp_path

    logger = MagicMock(Logger)
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(module_name)
        search_algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        search_algorithm._logger = logger
        test_cases = search_algorithm.generate_tests()
        assert test_cases.size() >= 0

        target_file = Path(config.configuration.test_case_output.output_path).resolve() / "test.py"
        export_visitor = export.PyTestChromosomeToAstVisitor(store_call_return=False)
        test_cases.accept(export_visitor)
        export.save_module_to_file(
            export_visitor.to_module(),
            target_file,
            format_with_black=config.configuration.test_case_output.format_with_black,
        )

    assert execute_with_pytest(target_file) == 0


def extract_test_case_0(text: str) -> str:
    lines = text.splitlines(keepends=True)

    # Find the line number where the function starts
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("def test_case_0"):
            start = i
            break

    if start is None:
        return None

    result = []

    # Include decorators above it
    decorator_line_idx = start - 1
    while decorator_line_idx > 0 and lines[decorator_line_idx].lstrip().startswith("@"):
        result.append(lines[decorator_line_idx])
        decorator_line_idx -= 1

    # Include the function header
    result.append(lines[start])

    # Collect the function body
    for line in lines[start + 1 :]:
        if line.startswith((" ", "\t")):
            result.append(line)
        else:
            break

    # Remove the final newline
    return "".join(result).rstrip("\n")


def _import_execute_export(
    module_name: str, test_case_code: str, *, store_call_return: bool = True
) -> str:
    """Import a test case, execute it and export it again.

    Args:
        module_name: The name of the SUT module.
        test_case_code: The test case code to add assertions for.
        store_call_return: Whether to store the return value of each call.

    Returns:
        The exported test case.
    """
    subject_properties = SubjectProperties()
    config.configuration.module_name = module_name
    test_case_code = "import " + module_name + " as module_0\n\n" + test_case_code

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Parse seed into DefaultTestCase
        test_cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(
            test_cluster=test_cluster,
            create_assertions=False,  # do not import assertions
            constant_provider=EmptyConstantProvider(),
        )
        transformer.visit(ast.parse(test_case_code))
        assert transformer.testcases, "No test case parsed from seed source"
        test_case_chrom = tcc.TestCaseChromosome(transformer.testcases[0])

        # Instrument and import target module for assertion generation
        with install_import_hook(module_name, subject_properties):
            with subject_properties.instrumentation_tracer:
                module = importlib.import_module(module_name)
                importlib.reload(module)

            # Execute the imported test case
            executor = TestCaseExecutor(subject_properties)
            execution_result = executor.execute(test_case_chrom.test_case)
            test_case_chrom.set_last_execution_result(execution_result)

            # Export the augmented test with assertions
            export_path = tmp_path / "test_with_assertions.py"
            exporter = export.PyTestChromosomeToAstVisitor(store_call_return=store_call_return)
            test_case_chrom.accept(exporter)
            export.save_module_to_file(
                exporter.to_module(),
                export_path,
                format_with_black=config.configuration.test_case_output.format_with_black,
            )

        exported = export_path.read_text(encoding="utf-8")
        return extract_test_case_0(exported)


def test_import_export():
    module_name = "tests.fixtures.accessibles.accessible"
    test_case_code = """def test_case_0():
    int_0 = 5
    some_type_0 = module_0.SomeType(int_0)
    float_0 = 42.23
    float_1 = module_0.simple_function(float_0)"""
    exported = _import_execute_export(module_name, test_case_code)
    assert exported == test_case_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_not_add_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)"""
    exported = _import_execute_export(module_name, test_case_code)
    assert exported == test_case_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_remove_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """@pytest.mark.xfail(strict=True)
def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)"""
    expected_code = """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)"""
    exported = _import_execute_export(module_name, test_case_code)
    assert exported == expected_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_keep_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)"""
    exported = _import_execute_export(module_name, test_case_code)
    assert exported == test_case_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_add_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)"""
    expected_code = """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)"""
    exported = _import_execute_export(module_name, test_case_code)
    assert exported == expected_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_nocr():
    module_name = "tests.fixtures.accessibles.accessible"
    test_case_code = """def test_case_0():
    int_0 = 5
    module_0.SomeType(int_0)
    float_0 = 42.23
    module_0.simple_function(float_0)"""
    exported = _import_execute_export(module_name, test_case_code, store_call_return=False)
    assert exported == test_case_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_nocr_not_add_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)"""
    exported = _import_execute_export(module_name, test_case_code, store_call_return=False)
    assert exported == test_case_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_nocr_remove_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """@pytest.mark.xfail(strict=True)
def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)"""
    expected_code = """def test_case_0():
    bool_0 = True
    module_0.foo(bool_0)"""
    exported = _import_execute_export(module_name, test_case_code, store_call_return=False)
    assert exported == expected_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_nocr_keep_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    module_0.foo(none_type_0)"""
    exported = _import_execute_export(module_name, test_case_code, store_call_return=False)
    assert exported == test_case_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0


def test_import_export_nocr_add_fail():
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    test_case_code = """def test_case_0():
    none_type_0 = None
    module_0.foo(none_type_0)"""
    expected_code = """@pytest.mark.xfail(strict=True)
def test_case_0():
    none_type_0 = None
    module_0.foo(none_type_0)"""
    exported = _import_execute_export(module_name, test_case_code, store_call_return=False)
    assert exported == expected_code
    execution_result = execute_test_with_pytest(module_name, exported)
    assert execution_result == 0
