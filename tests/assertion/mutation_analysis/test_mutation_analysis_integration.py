#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
import importlib

import pynguin.analyses.seeding.testimport.ast_to_statement as ats
import pynguin.assertion.mutation_analysis.mutationanalysisgenerator as mag
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor


def test_generate_assertions():
    config.configuration.module_name = "tests.fixtures.examples.queue"
    config.configuration.test_case_output.generate_all_assertions = True
    module_name = config.configuration.module_name
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = TestClusterGenerator(module_name).generate_cluster()
        transformer = ats.AstToTestCaseTransformer(cluster, False)
        transformer.visit(
            ast.parse(
                """def test_case():
    int_0 = 42
    queue_0 = module_0.Queue(int_0)
    bool_0 = queue_0.enqueue(int_0)
"""
            )
        )
        test_case = transformer.testcases[0]

        chromosome = tcc.TestCaseChromosome(test_case)
        suite = tsc.TestSuiteChromosome()
        suite.add_test_case_chromosome(chromosome)

        gen = mag.MutationAnalysisGenerator(executor)
        suite.accept(gen)
        assert test_case.size_with_assertions() == 12
