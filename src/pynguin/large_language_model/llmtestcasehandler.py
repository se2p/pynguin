# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module holds logic for converting LLM output to test cases and other utils."""

from __future__ import annotations

import dataclasses
import datetime
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.testcase as tc
import pynguin.utils.statistics.stats as stat
from pynguin.large_language_model.parsing.deserializer import (
    DeserializationResult,
    Disposition,
    ParseStatus,
    deserialize_code_to_testcases,
)
from pynguin.large_language_model.prompts.conversationrepairprompt import (
    ConversationRepairPrompt,
)
from pynguin.large_language_model.tracing import CallPurpose, LLMCallRecord, count, write_record
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from pynguin.analyses.module import TestCluster
    from pynguin.ga.computations import CoverageFunction, FitnessFunction
    from pynguin.large_language_model.prompts.prompt import Prompt
    from pynguin.testcase.testfactory import TestFactory

_logger = logging.getLogger(__name__)

# Single source of truth mapping each statement disposition to the runtime
# variable it is reported under. Adding/removing a bucket is a one-line change.
_DISPOSITION_STATISTICS: dict[Disposition, RuntimeVariable] = {
    Disposition.ADMITTED: RuntimeVariable.LLMAdmitted,
    Disposition.ADMITTED_UNRESOLVED_CALL: RuntimeVariable.LLMAdmittedUnresolvedCall,
    Disposition.ADMITTED_IMPORT: RuntimeVariable.LLMAdmittedImport,
    Disposition.ADMITTED_COMPOUND: RuntimeVariable.LLMAdmittedCompound,
    Disposition.DROPPED_UNKNOWN_NAMES: RuntimeVariable.LLMDroppedUnknownNames,
    Disposition.DROPPED_UNSUPPORTED_SHAPE: RuntimeVariable.LLMDroppedUnsupportedShape,
    Disposition.ASSERTION_LIFTED: RuntimeVariable.LLMAssertionLifted,
    Disposition.ASSERTION_KEPT_RAW: RuntimeVariable.LLMAssertionKeptRaw,
    Disposition.ASSERTION_DROPPED: RuntimeVariable.LLMAssertionDropped,
}

_ADMITTED_STATEMENTS = (
    Disposition.ADMITTED,
    Disposition.ADMITTED_UNRESOLVED_CALL,
    Disposition.ADMITTED_IMPORT,
    Disposition.ADMITTED_COMPOUND,
)
_DROPPED_STATEMENTS = (
    Disposition.DROPPED_UNKNOWN_NAMES,
    Disposition.DROPPED_UNSUPPORTED_SHAPE,
)

# Guards the run-wide admitted/dropped totals behind ``LLMParsedStatementRatio``;
# responses may be parsed on the search thread and on a background LLM thread.
_RATIO_LOCK = threading.Lock()
_statement_totals = {"admitted": 0, "dropped": 0}


@dataclasses.dataclass(frozen=True)
class ChromosomeContext:
    """What is needed to turn parsed LLM test cases into search chromosomes."""

    test_cluster: TestCluster
    test_factory: TestFactory
    fitness_functions: Iterable[FitnessFunction]
    coverage_functions: Iterable[CoverageFunction]


@dataclasses.dataclass
class LLMGeneration:
    """The chromosomes produced by an LLM call, with the conversation that led to them.

    The conversation is kept so that the response can be sent back for repair later,
    e.g. once executing the chromosomes showed that they raise.
    """

    chromosomes: list[tcc.TestCaseChromosome]
    prompt: Prompt | None = None
    """The prompt of the last call, None if no call was made."""
    response: str | None = None
    """The response to the last call, None if it failed."""
    call_id: str | None = None
    """The trace id of the last call."""
    targets: list[str] = dataclasses.field(default_factory=list)
    repairs_used: int = 0
    """How many repair calls were made for the original call so far."""


def _track_statement_ratio(result: DeserializationResult) -> None:
    """Adds a parse result to the run-wide ``LLMParsedStatementRatio``.

    Args:
        result: The deserialisation result.
    """
    with _RATIO_LOCK:
        _statement_totals["admitted"] += sum(result.counts[d] for d in _ADMITTED_STATEMENTS)
        _statement_totals["dropped"] += sum(result.counts[d] for d in _DROPPED_STATEMENTS)
        total = _statement_totals["admitted"] + _statement_totals["dropped"]
        if total > 0:
            stat.set_output_variable_for_runtime_variable(
                RuntimeVariable.LLMParsedStatementRatio, _statement_totals["admitted"] / total
            )


def reset_statement_ratio() -> None:
    """Resets the run-wide totals behind ``LLMParsedStatementRatio``."""
    with _RATIO_LOCK:
        _statement_totals["admitted"] = 0
        _statement_totals["dropped"] = 0


def _deserialization_summary(result: DeserializationResult | None) -> dict:
    """Summarises a parse result for the LLM call trace.

    Args:
        result: The deserialisation result, None if there was no response to parse.

    Returns:
        A JSON-serialisable summary.
    """
    if result is None:
        return {"status": None, "test_cases": 0, "counts": {}}
    return {
        "status": result.status.value,
        "test_cases": len(result.test_cases),
        "counts": {d.value: result.counts[d] for d in Disposition if result.counts[d]},
        "import_names_repaired": result.import_names_repaired,
        "import_names_dropped": result.import_names_dropped,
    }


def _syntax_error(code: str) -> str | None:
    """Describes the syntax error in a piece of code, without executing it.

    Args:
        code: The code to check.

    Returns:
        A description of the syntax error, or None if the code compiles.
    """
    try:
        compile(code, "<llm response>", "exec")
    except SyntaxError as error:
        return f"Your code is not valid Python: {error.msg} (line {error.lineno})."
    return None


def _unusable_reason(code: str, result: DeserializationResult) -> str | None:
    """Explains why a parsed response yields no usable test, for a repair prompt.

    Args:
        code: The Python code extracted from the response.
        result: The deserialisation result of that code.

    Returns:
        The explanation, or None if the response yields at least one usable statement.
    """
    if result.status is ParseStatus.UNPARSEABLE or not result.test_cases:
        # The deserializer salvages what it can from broken code, so a syntax error
        # often shows up as a response without tests rather than as UNPARSEABLE.
        syntax_error = _syntax_error(code)
        if syntax_error is not None:
            return syntax_error
    if result.status is ParseStatus.UNPARSEABLE:
        return "Your code could not be parsed."
    if sum(result.counts[d] for d in _ADMITTED_STATEMENTS) > 0:
        return None
    unknown = result.counts[Disposition.DROPPED_UNKNOWN_NAMES]
    shape = result.counts[Disposition.DROPPED_UNSUPPORTED_SHAPE]
    if unknown + shape == 0:
        return "Your answer contains no `test_*` functions with statements."
    return (
        "None of the statements in your tests could be used: "
        f"{unknown} referenced names that are not defined or imported, and "
        f"{shape} had an unsupported form (e.g. several assignment targets)."
    )


class LLMTestCaseHandler:
    """Class that holds logic for converting LLM output to test cases."""

    def __init__(self, model):
        """Initializes the LLMTestCaseHandler."""
        self._model = model

    def extract_test_cases_from_llm_output(self, llm_output: str) -> str:
        """Extracts test cases from the LLM output.

        Args:
            llm_output: The output from the LLM containing test cases.

        Returns:
            The extracted Python test case code.
        """
        python_code = self._model.extract_python_code_from_llm_output(llm_output)
        _logger.debug("Extracted Python code: %s.", python_code)
        save_llm_tests_to_file(python_code, "extracted_llm_test_cases.py")
        return python_code

    def get_test_cases_from_llm_results(
        self,
        llm_query_results: str | None,
        test_cluster: TestCluster,
    ) -> list[tc.TestCase]:
        """Parse LLM query results into test cases.

        This handles only the parsing and deserialization step and does not attach the
        test cases to a test factory or fitness functions.

        Args:
            llm_query_results: Raw results returned by the LLM. If None, an empty
                list is returned.
            test_cluster: Test cluster used during deserialization.

        Returns:
            The parsed test cases, or an empty list if no test cases could be created.
        """
        if llm_query_results is None:
            return []
        _, deserialization_result = self._deserialize(llm_query_results, test_cluster)
        if deserialization_result.status is ParseStatus.UNPARSEABLE:
            return []
        return deserialization_result.test_cases

    def _deserialize(
        self, llm_query_results: str, test_cluster: TestCluster
    ) -> tuple[str, DeserializationResult]:
        """Extracts the code from a response, deserialises it and tracks the statistics.

        Args:
            llm_query_results: The raw LLM response.
            test_cluster: Test cluster used during deserialization.

        Returns:
            The extracted code and its deserialisation result.
        """
        save_llm_tests_to_file(llm_query_results, "llm_query_results.txt")
        llm_test_cases_str = self.extract_test_cases_from_llm_output(llm_query_results)

        deserialization_result = deserialize_code_to_testcases(
            llm_test_cases_str, test_cluster=test_cluster
        )

        if deserialization_result.status is ParseStatus.UNPARSEABLE:
            _logger.error(
                "Failed to deserialize test cases %s",
                llm_test_cases_str,
            )
            return llm_test_cases_str, deserialization_result

        test_cases = deserialization_result.test_cases

        tests_source_code = "\n\n".join(
            test_case.to_test_function(i).code for i, test_case in enumerate(test_cases)
        )
        save_llm_tests_to_file(tests_source_code, "deserializer_llm_test_cases.py")

        for disposition, runtime_variable in _DISPOSITION_STATISTICS.items():
            stat.track_output_variable(runtime_variable, deserialization_result.counts[disposition])
        stat.track_output_variable(
            RuntimeVariable.LLMImportNamesRepaired, deserialization_result.import_names_repaired
        )
        stat.track_output_variable(
            RuntimeVariable.LLMImportNamesDropped, deserialization_result.import_names_dropped
        )
        _track_statement_ratio(deserialization_result)

        return llm_test_cases_str, deserialization_result

    def generate_chromosomes(
        self,
        prompt: Prompt,
        context: ChromosomeContext,
        purpose: str,
        targets: Sequence[str] = (),
        may_repair: Callable[[], bool] | None = None,
    ) -> LLMGeneration:
        """Queries the LLM, parses the response and repairs unusable responses.

        Each call, including every repair call, is written once to the LLM call trace
        together with its deserialisation result.  A response that cannot be parsed or
        whose statements are all dropped is sent back with the error, in the same
        conversation, up to ``large_language_model.repair_attempts`` times.

        Args:
            prompt: The prompt to send.
            context: Turns parsed test cases into chromosomes.
            purpose: Why the call is made, for the trace.
            targets: The names of the targeted callables, for the trace.
            may_repair: Asked before each repair call; returning False (e.g. because
                the search budget is used up) stops repairing.

        Returns:
            The chromosomes from the last call, with that call's conversation.
        """
        response, record = self._model.query_traced(prompt, purpose=purpose, targets=targets)
        return self._parse_and_repair(
            prompt, response, record, context, repairs_used=0, may_repair=may_repair
        )

    def repair_chromosomes(
        self,
        generation: LLMGeneration,
        error_message: str,
        context: ChromosomeContext,
        may_repair: Callable[[], bool] | None = None,
    ) -> LLMGeneration | None:
        """Asks the LLM to fix the response behind a generation that turned out unusable.

        Args:
            generation: The generation whose response is to be repaired.
            error_message: What went wrong with the generation's chromosomes.
            context: Turns parsed test cases into chromosomes.
            may_repair: Asked before each repair call; returning False stops repairing.

        Returns:
            The repaired generation, or None if no repair call is allowed.
        """
        if not self._can_repair(generation.response, generation.repairs_used, may_repair):
            return None
        assert generation.prompt is not None
        assert generation.response is not None
        return self._repair(
            ConversationRepairPrompt(generation.prompt, generation.response, error_message),
            generation.call_id,
            generation.targets,
            generation.repairs_used,
            context,
            may_repair,
        )

    @staticmethod
    def _can_repair(
        response: str | None, repairs_used: int, may_repair: Callable[[], bool] | None
    ) -> bool:
        if response is None:
            # Nothing to repair: the call itself failed.
            return False
        if repairs_used >= config.configuration.large_language_model.repair_attempts:
            return False
        return may_repair is None or may_repair()

    def _repair(  # noqa: PLR0917
        self,
        prompt: ConversationRepairPrompt,
        parent_call_id: str | None,
        targets: Sequence[str],
        repairs_used: int,
        context: ChromosomeContext,
        may_repair: Callable[[], bool] | None,
    ) -> LLMGeneration:
        count(RuntimeVariable.LLMRepairCalls)
        _logger.info(
            "Asking the LLM to repair its response (attempt %d): %s",
            repairs_used + 1,
            prompt.error_message,
        )
        response, record = self._model.query_traced(
            prompt,
            purpose=CallPurpose.REPAIR.value,
            targets=targets,
            parent_call_id=parent_call_id,
            repair_attempt=repairs_used + 1,
        )
        return self._parse_and_repair(
            prompt, response, record, context, repairs_used=repairs_used + 1, may_repair=may_repair
        )

    def _parse_and_repair(
        self,
        prompt: Prompt,
        response: str | None,
        record: LLMCallRecord,
        context: ChromosomeContext,
        *,
        repairs_used: int,
        may_repair: Callable[[], bool] | None,
    ) -> LLMGeneration:
        test_cases: list[tc.TestCase] = []
        reason: str | None = None
        result: DeserializationResult | None = None
        if response is not None:
            code, result = self._deserialize(response, context.test_cluster)
            reason = _unusable_reason(code, result)
            if result.status is ParseStatus.OK:
                test_cases = result.test_cases
        record.deserialization = _deserialization_summary(result)
        write_record(record)

        if reason is not None and self._can_repair(response, repairs_used, may_repair):
            assert response is not None
            return self._repair(
                ConversationRepairPrompt(prompt, response, reason),
                record.call_id,
                record.targets,
                repairs_used,
                context,
                may_repair,
            )
        return LLMGeneration(
            chromosomes=[
                _create_test_case_chromosome(
                    test_case,
                    context.test_factory,
                    context.fitness_functions,
                    context.coverage_functions,
                )
                for test_case in test_cases
            ],
            prompt=prompt,
            response=response,
            call_id=record.call_id,
            targets=list(record.targets),
            repairs_used=repairs_used,
        )

    def get_test_case_chromosomes_from_llm_results(
        self,
        llm_query_results: str | None,
        test_cluster: TestCluster,
        test_factory: TestFactory,
        fitness_functions: Iterable[FitnessFunction],
        coverage_functions: Iterable[CoverageFunction],
    ) -> list[tcc.TestCaseChromosome]:
        """Process LLM query results into test case chromosomes.

        Args:
            llm_query_results: The raw string results returned from the LLM.
                If None, no processing will occur, and an empty list will be returned.
            test_cluster: The test cluster to which the generated test cases belong.
                Provides context for deserialization and test case generation.
            test_factory: A factory object used to create instances of `TestCaseChromosome`.
            fitness_functions: An iterable collection of fitness functions
            to attach to each generated chromosome.
                These define objectives for evolutionary algorithms.
            coverage_functions: An iterable collection of coverage functions
            to attach to each generated chromosome.
                These define metrics for evaluating test case coverage.

        Returns:
            A list of `TestCaseChromosome` objects created from the deserialized
             LLM test cases. Each chromosome is augmented with the provided
             fitness and coverage functions.
        """
        test_cases = self.get_test_cases_from_llm_results(llm_query_results, test_cluster)
        return [
            _create_test_case_chromosome(
                test_case, test_factory, fitness_functions, coverage_functions
            )
            for test_case in test_cases
        ]


def _create_test_case_chromosome(
    test_case,
    test_factory,
    fitness_functions,
    coverage_functions,
):
    test_case_chromosome = tcc.TestCaseChromosome(test_case=test_case, test_factory=test_factory)
    for fitness_function in fitness_functions:
        test_case_chromosome.add_fitness_function(fitness_function)
    for coverage_function in coverage_functions:
        test_case_chromosome.add_coverage_function(coverage_function)
    return test_case_chromosome


def save_llm_tests_to_file(test_cases: str, file_name: str):
    """Save extracted test cases to a Python (.py) file.

    Args:
        file_name: the file name
        test_cases: The test cases to save, formatted as Python code.

    Raises:
        OSError: If there is an issue writing to the file, logs the exception.
    """
    try:
        output_dir = Path(config.configuration.statistics_output.report_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / file_name
        with output_file.open(mode="w", encoding="utf-8") as file:
            file.write("# LLM generated and rewritten (in Pynguin format) test cases\n")
            file.write(
                "# Date and time: "
                + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                + "\n\n"
            )
            file.write(test_cases)
        _logger.info("Test cases saved successfully to %s", output_file)
    except OSError as error:
        _logger.exception("Error while saving LLM-generated test cases to file: %s", error)
