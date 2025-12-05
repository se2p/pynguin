#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
from logging import Logger
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
from pynguin.analyses.module import generate_test_cluster
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase import export
from pynguin.testcase.execution import TestCaseExecutor
from testutils import execute_with_pytest


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


def test_export_sequence_expected_exception(exportable_test_case_with_expected_exception, tmp_path):
    """An expected exception is an exception that is expected to be raised.

    This leads to a ``with pytest.raises(...):`` statement.
    """
    path = tmp_path / "generated_with_expected_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case_with_expected_exception.accept(exporter)
    export.save_module_to_file(exporter.to_module(), path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.accessibles.accessible as module_0


def test_case_0():
    float_0 = 42.23
    with pytest.raises(ValueError):
        float_1 = module_0.simple_function(float_0)
"""
    )


def test_export_sequence_unexpected_exception(
    exportable_test_case_with_unexpected_exception, tmp_path
):
    """An unexpected exception is an exception not expected to be raised.

    This leads to a test failure and thus the test case is marked with xfail.
    """
    path = tmp_path / "generated_with_unexpected_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case_with_unexpected_exception.accept(exporter)
    export.save_module_to_file(exporter.to_module(), path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.accessibles.accessible as module_0


@pytest.mark.xfail(strict=True)
def test_case_0():
    float_0 = 42.23
    module_0.simple_function(float_0)
"""
    )


def test_export_sequence_expected_then_unexpected_exception(
    exportable_test_case_expected_then_unexpected_exception, tmp_path
):
    """First call has expected exception, second call is unexpected.

    The first call should be exported within a ``with pytest.raises(...)`` block, while
    the second call should be emitted bare. As the second call is unexpected, the test
    must be marked with ``xfail``.
    """
    path = tmp_path / "generated_with_expected_then_unexpected_exception.py"
    exporter = export.PyTestChromosomeToAstVisitor()
    exportable_test_case_expected_then_unexpected_exception.accept(exporter)
    export.save_module_to_file(exporter.to_module(), path)
    assert (
        path.read_text()
        == export._PYNGUIN_FILE_HEADER
        + """import pytest
import tests.fixtures.accessibles.accessible as module_0


@pytest.mark.xfail(strict=True)
def test_case_0():
    float_0 = 42.23
    with pytest.raises(ValueError):
        float_1 = module_0.simple_function(float_0)
    module_0.simple_function(float_0)
"""
    )


def test_export_sequence_unexpected_assertion(exportable_test_case_with_unexpected_assertion):
    """An unexpected assertion is an assertion not expected to be raised.

    This indicates a bug in the assertion generation.
    """
    exporter = export.PyTestChromosomeToAstVisitor()
    with pytest.raises(AssertionError, match="Unexpected assertion"):
        exportable_test_case_with_unexpected_assertion.accept(exporter)


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
