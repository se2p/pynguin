#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib

import pynguin.assertion.mutation_analysis.mutationanalysisgenerator as mag
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
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
        # TODO(fk) don't build this by hand, implement convenient way
        #  to use ast-to-statement conversion to create test cases from text.
        test_case = dtc.DefaultTestCase()
        int_0 = test_case.add_statement(stmt.IntPrimitiveStatement(test_case, 42))
        queue_0 = test_case.add_statement(
            stmt.ConstructorStatement(
                test_case,
                list(list(cluster.generators.values())[0])[0],
                {"size_max": int_0},
            )
        )
        test_case.add_statement(
            stmt.MethodStatement(
                test_case,
                list(list(cluster.modifiers.values())[0])[2],
                queue_0,
                {"x": int_0},
            )
        )

        chromosome = tcc.TestCaseChromosome(test_case)
        suite = tsc.TestSuiteChromosome()
        suite.add_test_case_chromosome(chromosome)

        gen = mag.MutationAnalysisGenerator(executor)
        suite.accept(gen)
        assert test_case.size_with_assertions() == 12
