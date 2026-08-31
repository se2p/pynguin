#  SPDX-License-Identifier: MIT
#  SPDX-FileCopyrightText: 2026 Aditya Sinha
#  SPDX-License-Identifier: MIT

import pynguin.ga.coveragegoals as bg


class DummyExecutor:
    def __init__(self):
        self.subject_properties = None

    def execute(self, test_case):
        return test_case  # passthrough


class DummyChromosome:
    def __init__(self, execution_result):
        self._execution_result = execution_result


class DummyExecutionResult:
    def __init__(self, covered_lines=None, executed_code_objects=None):
        self.execution_trace = type(
            "Trace",
            (),
            {
                "covered_line_ids": covered_lines or [],
                "executed_code_objects": executed_code_objects or [],
            },
        )()


def test_line_fitness_non_binary_when_not_covered():
    executor = DummyExecutor()
    goal = bg.LineCoverageGoal(0, 1)

    fitness = bg.LineCoverageTestFitness(executor, goal)

    execution = DummyExecutionResult(covered_lines=[], executed_code_objects=[1, 2])
    chromosome = DummyChromosome(execution)

    # Monkey patch run method
    fitness._run_test_case_chromosome = lambda _: execution

    value = fitness.compute_fitness(chromosome)

    assert value > 0.0


def test_line_fitness_zero_when_covered():
    executor = DummyExecutor()
    goal = bg.LineCoverageGoal(0, 1)

    fitness = bg.LineCoverageTestFitness(executor, goal)

    execution = DummyExecutionResult(covered_lines=[1], executed_code_objects=[1])
    chromosome = DummyChromosome(execution)

    fitness._run_test_case_chromosome = lambda _: execution

    value = fitness.compute_fitness(chromosome)

    assert value == 0.0
