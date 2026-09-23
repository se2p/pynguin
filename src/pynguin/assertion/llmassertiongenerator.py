#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a Large Language Model (LLM) assertion generator."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import DEFAULT, NonCallableMock

import libcst as cst

import pynguin.configuration as config
import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat
from pynguin.assertion.assertiongenerator import MutationAnalysisAssertionGenerator
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.parsing.deserializer import parse_assertion
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import ModuleTestCluster

_logger = logging.getLogger(__name__)


def extract_assertions(input_str: str) -> list[str]:
    """Extract assertions from the input string.

    Args:
        input_str (str): The input string containing multiple lines,
        some of which may be assertions.

    Returns:
        list[str]: A list of strings, each containing an extracted assertion.
    """
    # Use regex to find all lines starting with 'assert' (ignoring leading whitespace)
    return re.findall(r"^\s*assert.*", input_str, flags=re.MULTILINE)


def _binding_index(test_case: tc.TestCase) -> dict[str, type | None]:
    """Map bound variable names to their (best-effort) type, last binding wins.

    Args:
        test_case: The test case to index.

    Returns:
        The mapping from bound variable name to type.
    """
    index: dict[str, type | None] = {}
    for statement in test_case.statements():
        if statement.bound_variable is not None:
            index[statement.bound_variable] = statement.bound_type
    return index


def _last_binding_index(test_case: tc.TestCase, var: str) -> int | None:
    """Return the index of the last statement binding *var*, if any.

    Args:
        test_case: The test case to search.
        var: The variable name to look for.

    Returns:
        The statement index, or ``None`` if *var* is never bound.
    """
    for index in range(test_case.size() - 1, -1, -1):
        if test_case.get_statement(index).bound_variable == var:
            return index
    return None


class _CallArgumentNameCollector(cst.CSTVisitor):
    """Collect the names of variables that appear anywhere inside a ``Call`` node.

    A variable is only mutated in place by a subsequent statement when it is passed
    into a call -- as an argument (``f(var)``, ``f(k=var)``) or as the receiver of a
    method call (``var.append(x)``). Names read outside any call (``var_1 = var_0``,
    ``var_0 + 1``) cannot mutate the object, so they are ignored.
    """

    def __init__(self) -> None:
        """Initialize the collector."""
        self.names: set[str] = set()
        self._call_depth = 0

    def visit_Call(self, node: cst.Call) -> bool:  # noqa: N802
        self._call_depth += 1
        return True

    def leave_Call(self, original_node: cst.Call) -> None:  # noqa: N802
        self._call_depth -= 1

    def visit_Name(self, node: cst.Name) -> bool:  # noqa: N802
        if self._call_depth > 0:
            self.names.add(node.value)
        return True


def _passes_variable_to_call(statement: tc.Statement, var: str) -> bool:
    """Return whether *statement* passes *var* into a call (a possible in-place mutation).

    Args:
        statement: The statement to inspect.
        var: The variable name to look for.

    Returns:
        True if *var* appears inside any call in the statement.
    """
    collector = _CallArgumentNameCollector()
    statement.node.visit(collector)
    return var in collector.names


def _last_reference_index(test_case: tc.TestCase, var: str) -> int | None:
    """Return the statement index an assertion about *var* should be attached to.

    An LLM assertion describes *var*'s value at the end of the test, so it must be
    attached after the last statement that can affect *var*. That is the later of the
    last statement that (re)binds *var* and the last statement that passes *var* into a
    call, since such a call may mutate *var* in place (an out-parameter dict/list passed
    by reference). Attaching only after the last binding places the assertion before such
    a mutating call, making it observe the pre-mutation value (issue #276). Plain reads
    that cannot mutate *var* (e.g. ``var_1 = var_0``) do not move the assertion.

    Args:
        test_case: The test case to search.
        var: The variable name to look for.

    Returns:
        The statement index, or ``None`` if *var* is never bound.
    """
    binding = _last_binding_index(test_case, var)
    if binding is None:
        return None
    last = binding
    for index in range(binding + 1, test_case.size()):
        if _passes_variable_to_call(test_case.get_statement(index), var):
            last = index
    return last


def _should_use_batch(model: Any) -> bool:
    """Check if the model supports batch assertion generation.

    If the model is a mock and only ``generate_assertions_for_test_case`` was
    configured with a return value, returns False for test backward compatibility.
    """
    if not hasattr(model, "generate_assertions_for_test_cases"):
        return False
    if isinstance(model, NonCallableMock):
        batch_method = getattr(model, "generate_assertions_for_test_cases", None)
        if (
            isinstance(batch_method, NonCallableMock)
            and batch_method._mock_return_value is DEFAULT  # noqa: SLF001
            and batch_method.side_effect is None
        ):
            return False
    return True


def _apply_assertions(test_case: tc.TestCase, response: str | None) -> tuple[int, int]:
    """Parse and attach assertions from an LLM response to statements in a test case.

    Args:
        test_case: The test case to attach assertions to.
        response: The LLM response containing assertion strings.

    Returns:
        A tuple of (assertions_added, assertions_from_llm).
    """
    if response is None:
        return 0, 0
    extracted_assertions = extract_assertions(response)
    assertions_from_llm = len(extracted_assertions)
    assertions_added = 0
    known_vars = _binding_index(test_case)
    for line in extracted_assertions:
        parsed = parse_assertion(line, known_vars)
        if parsed is None:
            continue
        var, assertion = parsed
        index = _last_reference_index(test_case, var)
        if index is None:
            continue
        test_case.get_statement(index).assertions.append(assertion)
        assertions_added += 1
    return assertions_added, assertions_from_llm


class LLMAssertionGenerator(cv.ChromosomeVisitor):
    """An assertion generator using a Large Language Model (LLM).

    This class generates regression assertions for test cases using an LLM.
    Because the internal representation renders statements back to their
    actual ``var_N`` source, the LLM's returned ``assert`` lines refer to the
    same names already used in the test case: no re-deserialization of the
    whole test and no reference-copying is required.
    """

    def __init__(
        self,
        test_cluster: ModuleTestCluster,
        model: LLMAgent | None = None,
        *,
        start_time: float | None = None,
        maximum_time: float | None = None,
    ):
        """Initialize the LLMAssertionGenerator with the given test cluster.

        Args:
            test_cluster: The test cluster used for generating assertions.
            model: The LLM model to use for generating assertions.
            start_time: Optional start timestamp (monotonic) for budgeting assertion generation.
            maximum_time: Optional maximum wall-clock time in seconds for assertion generation.
        """
        self._model = model if model is not None else LLMAgent()
        self._test_cluster = test_cluster
        self._start_time = start_time
        self._maximum_time = maximum_time

    def visit_test_case_chromosome(self, chromosome: tcc.TestCaseChromosome) -> None:
        """Process a test case chromosome to add assertions.

        Args:
            chromosome (tcc.TestCaseChromosome): The test case chromosome to process.
        """
        self._add_assertions_for([chromosome.test_case])

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        """Process a test suite chromosome to add assertions.

        Args:
            chromosome (tsc.TestSuiteChromosome): The test suite chromosome to process.
        """
        self._add_assertions_for([chrom.test_case for chrom in chromosome.test_case_chromosomes])

    def _add_assertions_for(self, test_cases: list[tc.TestCase]) -> None:
        """Add assertions for the given list of test cases.

        Queries the LLM with the rendered test-case source, extracts
        ``assert`` lines from the response, and attaches each parseable one
        to the statement that (last) bound the referenced variable.

        Args:
            test_cases (list[tc.TestCase]): The test cases to add assertions for.
        """
        total_assertions_added = 0
        total_assertions_from_llm = 0

        maximum_time = (
            self._maximum_time
            if self._maximum_time is not None
            else config.configuration.test_case_output.maximum_llm_assertion_time
        )
        start_time = self._start_time if self._start_time is not None else time.monotonic()

        if not _should_use_batch(self._model):
            for idx, test_case in enumerate(test_cases):
                if maximum_time >= 0 and time.monotonic() - start_time >= maximum_time:
                    _logger.info(
                        "LLM assertion generation time budget of %ss exceeded; "
                        "checked %i of %i test case(s).",
                        maximum_time,
                        idx,
                        len(test_cases),
                    )
                    break
                if test_case.size() == 0:
                    continue
                code = test_case.to_test_function().code
                response = self._model.generate_assertions_for_test_case(code)
                added, from_llm = _apply_assertions(test_case, response)
                total_assertions_added += added
                total_assertions_from_llm += from_llm
        elif maximum_time >= 0 and time.monotonic() - start_time >= maximum_time:
            _logger.info(
                "LLM assertion generation time budget of %ss exceeded; "
                "checked 0 of %i test case(s).",
                maximum_time,
                len(test_cases),
            )
        else:
            eligible_test_cases = [tc for tc in test_cases if tc.size() > 0]
            if eligible_test_cases:
                codes = [tc.to_test_function().code for tc in eligible_test_cases]
                responses = self._model.generate_assertions_for_test_cases(codes)
                for test_case, response in zip(eligible_test_cases, responses, strict=False):
                    added, from_llm = _apply_assertions(test_case, response)
                    total_assertions_added += added
                    total_assertions_from_llm += from_llm

        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalAssertionsAddedFromLLM, total_assertions_added
        )
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalAssertionsReceivedFromLLM, total_assertions_from_llm
        )


class MutationAnalysisLLMAssertionGenerator(MutationAnalysisAssertionGenerator):
    """Uses mutation analysis to filter out less relevant assertions."""

    def _add_assertions(self, test_cases: list[tc.TestCase]):
        super()._handle_add_assertions(test_cases)
