#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
from unittest import mock

import pytest

import pynguin.assertion.mutation_analysis.controller as ct
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.configuration as config
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.utils.timeout import TestExecutionTimeoutError
from tests.testutils import import_module_safe


@pytest.mark.parametrize(
    "module_name, expected_mutants",
    [
        ("tests.fixtures.examples.triangle", 17),
        ("tests.fixtures.regression.argparse_sys_exit", 6),
        ("tests.fixtures.regression.not_main", 7),
        ("tests.fixtures.regression.custom_error", 1),
    ],
)
def test_create_mutants(module_name, expected_mutants):
    mutant_generator = mu.FirstOrderMutator([
        *mo.standard_operators,
        *mo.experimental_operators,
    ])

    module, module_source_code = import_module_safe(module_name)

    module_ast = ParentNodeTransformer.create_ast(module_source_code)
    mutation_controller = ct.MutationController(mutant_generator, module_ast, module)
    config.configuration.seeding.seed = 42

    mutations = tuple(mutation_controller.create_mutants())
    mutant_count = mutation_controller.mutant_count()

    assert len(mutations) == expected_mutants
    assert mutant_count == expected_mutants


@pytest.mark.parametrize(
    "module_name, expected_mutants",
    [
        ("tests.fixtures.examples.triangle", 17),
        ("tests.fixtures.regression.argparse_sys_exit", 6),
        ("tests.fixtures.regression.not_main", 7),
        ("tests.fixtures.regression.custom_error", 1),
    ],
)
def test_create_mutants_instrumented(module_name, expected_mutants):
    mutant_generator = mu.FirstOrderMutator([
        *mo.standard_operators,
        *mo.experimental_operators,
    ])

    module, module_source_code = import_module_safe(module_name)

    module_ast = ParentNodeTransformer.create_ast(module_source_code)
    mutation_controller = ct.MutationController(mutant_generator, module_ast, module)
    config.configuration.seeding.seed = 42

    mutations = tuple(mutation_controller.create_mutants())
    mutant_count = mutation_controller.mutant_count()

    assert len(mutations) == expected_mutants
    assert mutant_count == expected_mutants


def test_create_mutants_timeout():
    mutant_generator = mock.MagicMock()
    mutant_generator.mutate.return_value = [
        ([mock.MagicMock()], ast.Module(body=[], type_ignores=[]))
    ]
    controller = ct.MutationController(mutant_generator, mock.MagicMock(), mock.MagicMock())
    with mock.patch.object(
        controller, "create_mutant", side_effect=TestExecutionTimeoutError("Timeout")
    ):
        mutants = list(controller.create_mutants())
        assert len(mutants) == 1
        mutant_module, _ = mutants[0]
        assert mutant_module is None
