#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a assertion generation by utilizing the mutation-analysis approach."""
import logging
from types import ModuleType
from typing import Any, List, Tuple

import pynguin.assertion.assertion as ass
import pynguin.assertion.complexassertion as ca
import pynguin.assertion.fieldassertion as fa
import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.assertion.mutation_analysis.mutationadapter as ma
import pynguin.assertion.mutation_analysis.mutationanalysisexecution as ce
import pynguin.assertion.mutation_analysis.statecollectingobserver as sco
import pynguin.configuration as config
import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.execution as ex
import pynguin.utils.type_utils as tu


class MutationAnalysisGenerator(cv.ChromosomeVisitor):
    """Assertion generator using the mutation analysis approach."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: ex.TestCaseExecutor):
        """
        Create new assertion generator.

        Args:
            executor: the executor that will be used to execute the test cases.
        """
        self._storage = cs.CollectorStorage()
        # TODO(fk) permanently disable tracer
        self._executor = executor
        self._executor.add_observer(sco.StateCollectingObserver(self._storage))

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        test_cases = [chrom.test_case for chrom in chromosome.test_case_chromosomes]

        mutated_modules = [x for x, _ in self._mutate_module()]

        execution = ce.MutationAnalysisExecution(
            self._executor, mutated_modules, self._storage
        )
        self._logger.info("Execute %d test cases", len(test_cases))
        execution.execute(test_cases)

        self._logger.info("Generating assertions for test cases")
        self._generate_assertions()

    def visit_test_case_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        pass  # nothing to do here

    @staticmethod
    def _mutate_module() -> List[Tuple[ModuleType, Any]]:
        adapter = ma.MutationAdapter()
        return adapter.mutate_module()

    def _generate_assertions(self) -> None:
        # Get the reference data from the execution on the not mutated module
        reference = self._storage.get_execution_entry(0)

        # Iterate over all entries of the reference
        for key, ref_value in reference.items():
            mutated = self._storage.get_mutations(key)
            # Iterate over each mutated item
            for mut_value in mutated:
                _compare(key, ref_value, mut_value)


def _compare(key: Tuple[Any, ...], ref_value: Any, mut_value: Any):
    if _is_assertable_item(ref_value):
        # ref_value and mut_value can be compared straight away
        if (
            ref_value != mut_value
            or config.configuration.test_case_output.generate_all_assertions
        ):
            _switch_generation(key, ref_value)
    elif hasattr(ref_value, "__dict__"):
        # ref_value and mut_value need to be disassembled and partially compared
        for (ref_field, ref_field_value), (mut_field, mut_field_value) in zip(
            vars(ref_value).items(), vars(mut_value).items()
        ):
            if (
                ref_field == mut_field
                and _is_assertable_item(ref_field_value)
                and (
                    ref_field_value != mut_field_value
                    or config.configuration.test_case_output.generate_all_assertions
                )
            ):
                _switch_generation(key, ref_field_value, ref_field)


def _switch_generation(key: Tuple[Any, ...], ref_value: Any, field: str = None):
    if key[0] == cs.EntryTypes.RETURN_VALUE:
        _gen_return_value_assertion(key, ref_value, field)
    elif key[0] == cs.EntryTypes.GLOBAL_FIELD:
        _gen_global_field_assertion(key, ref_value, field)
    elif key[0] == cs.EntryTypes.OBJECT_ATTRIBUTE:
        _gen_object_attribute_assertion(key, ref_value, field)
    elif key[0] == cs.EntryTypes.CLASS_FIELD:
        _gen_class_variable_assertion(key, ref_value, field)
    else:
        raise ValueError("Unknown entry type.")


def _gen_return_value_assertion(
    key: Tuple[Any, ...], ref_value: Any, field: str = None
):
    statement = key[1]
    if field:
        assertion: ass.Assertion = fa.FieldAssertion(
            statement.ret_val, ref_value, field
        )
    else:
        assertion = ca.ComplexAssertion(statement.ret_val, ref_value)
    statement.add_assertion(assertion)


def _gen_global_field_assertion(
    key: Tuple[Any, ...], ref_value: Any, field: str = None
):
    statement = key[1]
    module_name = key[2]
    global_field = key[3]
    if field:
        assertion = fa.FieldAssertion(
            None, ref_value, field, module_name, [global_field]
        )
    else:
        assertion = fa.FieldAssertion(None, ref_value, global_field, module_name)
    statement.add_assertion(assertion)


def _gen_object_attribute_assertion(
    key: Tuple[Any, ...], ref_value: Any, field: str = None
):
    statement = key[1]
    obj_vr = key[2]
    obj_field = key[3]
    if field:
        assertion = fa.FieldAssertion(obj_vr, ref_value, field, None, [obj_field])
    else:
        assertion = fa.FieldAssertion(obj_vr, ref_value, obj_field)
    statement.add_assertion(assertion)


def _gen_class_variable_assertion(
    key: Tuple[Any, ...], ref_value: Any, field: str = None
):
    statement = key[1]
    clazz = key[2]
    clazz_field = key[3]
    clazz_name = clazz.__name__
    clazz_module = clazz.__module__
    if field:
        assertion = fa.FieldAssertion(
            None,
            ref_value,
            field,
            clazz_module,
            [clazz_field, clazz_name],
        )
    else:
        assertion = fa.FieldAssertion(
            None, ref_value, clazz_field, clazz_module, [clazz_name]
        )
    statement.add_assertion(assertion)


def _is_comparable_object(obj: Any) -> bool:
    return vars(obj.__class__).get("__eq__", None) and vars(obj.__class__).get(
        "__hash__", None
    )


def _is_assertable_item(item: Any) -> bool:
    return (
        tu.is_primitive_type(type(item))
        or tu.is_none_type(type(item))
        or tu.is_enum(type(item))
        or tu.is_collection_type(type(item))
        or _is_comparable_object(item)
    )
