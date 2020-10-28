#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

from pynguin.analyses.duckmock.duckmockanalysis import SourceCodeAnalyser


@pytest.fixture
def source_code_analyser() -> SourceCodeAnalyser:
    return SourceCodeAnalyser("tests.fixtures.duckmock.complex")


@pytest.mark.parametrize(
    "module_only_analysis, number_of_bindings",
    [pytest.param(False, 33), pytest.param(True, 15)],
)
def test_source_code_analysis(
    source_code_analyser, module_only_analysis, number_of_bindings
):
    source_code_analyser._module_only_analysis = module_only_analysis
    source_code_analyser.analyse_code()
    bindings = source_code_analyser.method_bindings
    assert len(bindings) == number_of_bindings
