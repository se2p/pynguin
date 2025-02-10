#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import inspect
import threading
from pathlib import Path

import pytest
import pynguin.assertion.assertiongenerator as ag
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.configuration as config
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.testcase.execution import ExecutionTracer
from tests.testutils import module_to_path


@pytest.mark.parametrize(
    "module_name, expected_mutants",
    [
        ("tests.fixtures.examples.triangle", 14),
        ("tests.fixtures.regression.argparse_sys_exit", 6),
        ("tests.fixtures.regression.not_main", 7),
    ],
)
def test_create_mutants(module_name, expected_mutants):
    mutant_generator = mu.FirstOrderMutator([
        *mo.standard_operators,
        *mo.experimental_operators,
    ])

    # Attempt to import module dynamically
    try:
        module = importlib.import_module(module_name)
        module_source_code = inspect.getsource(module)
    except SystemExit:
        # Handle modules that shouldn't execute on import
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Module {module_name} not found."
        module = importlib.util.module_from_spec(spec)
        file_name = module_to_path(module_name)
        module_source_code = Path(file_name).read_text()

    module_ast = ParentNodeTransformer.create_ast(module_source_code)
    mutation_tracer = ExecutionTracer()
    mutation_controller = ag.InstrumentedMutationController(
        mutant_generator, module_ast, module, mutation_tracer
    )
    config.configuration.seeding.seed = 42

    mutation_controller.tracer.current_thread_identifier = threading.current_thread().ident
    mutations = tuple(mutation_controller.create_mutants())
    mutant_count = mutation_controller.mutant_count()

    assert len(mutations) == expected_mutants
    assert mutant_count == expected_mutants
