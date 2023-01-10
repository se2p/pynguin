#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast

import pytest

import pynguin.ga.testcasechromosome as tcc
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.generation import export


@pytest.mark.parametrize(
    "testcase_seed",
    [
        (
            """    float_0 = 1.1
    var_0 = module_0.positional_only(float_0)
"""
        ),
        (
            """    float_0 = 1.1
    int_0 = 42
    list_0 = []
    str_0 = "test"
    bytes_0 = b"key"
    str_1 = "value"
    dict_0 = {bytes_0: str_1}
    var_0 = module_0.all_params(float_0, int_0, *list_0, param4=str_0, **dict_0)
"""
        ),
    ],
)
def test_parameter_mapping_roundtrip(testcase_seed, tmp_path):
    testcase_seed = (
        export._PYNGUIN_FILE_HEADER
        + """import tests.fixtures.grammar.parameters as module_0


def test_case_0():
"""
        + testcase_seed
    )
    test_cluster = generate_test_cluster("tests.fixtures.grammar.parameters")
    transformer = AstToTestCaseTransformer(test_cluster, False, EmptyConstantProvider())
    transformer.visit(ast.parse(testcase_seed))
    export_path = tmp_path / "export.py"
    chromosome = tcc.TestCaseChromosome(transformer.testcases[0])
    exporter = export.PyTestChromosomeToAstVisitor()
    chromosome.accept(exporter)
    export.save_module_to_file(exporter.to_module(), export_path)
    with open(export_path) as f:
        content = f.read()
        assert content == testcase_seed
