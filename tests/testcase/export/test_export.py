#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


from pynguin.testcase import export


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
    float_1 = module_0.simple_function(float_0)
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
