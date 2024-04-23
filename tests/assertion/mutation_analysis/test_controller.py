#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import inspect
import threading

import pynguin.assertion.assertiongenerator as ag
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.configuration as config

from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.testcase.execution import ExecutionTracer


def test_create_mutants():
    mutant_generator = mu.FirstOrderMutator(
        [*mo.standard_operators, *mo.experimental_operators]
    )

    module = importlib.import_module("tests.fixtures.examples.triangle")
    module_source_code = inspect.getsource(module)

    module_ast = ParentNodeTransformer.create_ast(module_source_code)
    mutation_tracer = ExecutionTracer()
    mutation_controller = ag.InstrumentedMutationController(
        mutant_generator, module_ast, module, mutation_tracer
    )
    config.configuration.seeding.seed = 42

    mutation_controller.tracer.current_thread_identifier = (
        threading.current_thread().ident
    )
    mutations = list(mutation_controller.create_mutants())
    assert len(mutations) == 14
