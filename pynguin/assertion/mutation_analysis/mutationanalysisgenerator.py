#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a assertion generation by utilizing the mutation-analysis approach."""
import logging
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Tuple, cast

import pynguin.assertion.complexassertion as oa
import pynguin.assertion.fieldassertion as fa
import pynguin.assertion.mutation_analysis.collectorobserver as mo
import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.assertion.mutation_analysis.mutationadapter as ma
import pynguin.assertion.mutation_analysis.mutationanalysisexecution as ce
import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.execution.testcaseexecutor as ex
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.statement as st
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.utils.collection_utils as cu


class MutationAnalysisGenerator(cv.ChromosomeVisitor):
    """Assertion generator using the mutation analysis approach."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: ex.TestCaseExecutor):
        """
        Create new assertion generator.

        Args:
            executor: the executor that will be used to execute the test cases.
        """
        self._executor = executor
        self._executor.add_observer(mo.CollectionObserver())
        self._global_assertions: Set[fa.FieldAssertion] = set()
        self._field_assertions: Set[fa.FieldAssertion] = set()

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        test_cases = [chrom.test_case for chrom in chromosome.test_case_chromosomes]

        mutated = self._mutate_module()
        mutated_modules = [x for x, y in mutated]

        execution = ce.MutationAnalysisExecution(self._executor, mutated_modules)
        execution.execute(test_cases)

        self._generate_assertions(test_cases)

    def visit_test_case_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        pass

    @staticmethod
    def _mutate_module() -> List[Tuple[ModuleType, Any]]:
        adapter = ma.MutationAdapter()
        return adapter.mutate_module()

    # pylint: disable=too-many-locals
    def _generate_assertions(self, test_cases: List[tc.TestCase]) -> None:
        # Get the reference data from the execution on the not mutate module
        reference = cs.CollectorStorage.get_items(0)

        # Just here to keep everything short and tidy
        key_id = cs.CollectorStorage.KEY_TEST_ID
        key_pos = cs.CollectorStorage.KEY_POSITION
        key_global = cs.CollectorStorage.KEY_GLOBALS
        key_retval = cs.CollectorStorage.KEY_RETURN_VALUE
        key_cf = cs.CollectorStorage.KEY_CLASS_FIELD
        key_oa = cs.CollectorStorage.KEY_OBJECT_ATTRIBUTE

        # Iterate over all dataframes for the reference execution
        for ref_dataframe in reference:

            # Get the test case id and position of the frame
            tc_id = cast(int, ref_dataframe[key_id])
            pos = cast(int, ref_dataframe[key_pos])

            # Get the corresponding test case and statement
            test_case = self._get_testcase_by_id(test_cases, tc_id)
            assert test_case is not None, "Expected a testcase to be found."
            statement = self._get_statement_by_pos(test_case, pos)
            assert statement is not None, "Expected a statement to be found."

            # Get the mutated frames corresponding to the id and position
            mutated_dataframes = cs.CollectorStorage.get_dataframe_of_mutations(
                tc_id, pos
            )

            # Get the reference state of the return value of the current statement
            ref_rv = ref_dataframe[key_retval]

            # Get the reference states of the global fields at this dataframe
            ref_globals = ref_dataframe[key_global]

            # Get all stored object fragments
            remainders = cu.dict_without_keys(
                ref_dataframe, [key_id, key_pos, key_retval, key_global]
            )

            # Iterate over all mutated dataframes and compare
            for dataframe in mutated_dataframes:

                # Compare the Return Value
                self._compare_return_value(dataframe, ref_rv, statement, key_retval)

                # Compare the global fields
                self._compare_globals(dataframe[key_global], ref_globals, statement)

                # Compare the remaining objects
                for key, ref_fragment in remainders.items():
                    fragment = dataframe.get(key)
                    assert (
                        fragment is not None
                    ), "Expected any data from the datafragment"
                    for frag_key, ref_frag_val in ref_fragment.items():
                        frag_val = fragment.get(frag_key)
                        if frag_key == key_cf:
                            # Class fields
                            self._compare_class_fields(
                                frag_val, pos, ref_frag_val, statement, test_case
                            )
                        elif frag_key == key_oa:
                            # Object attributes
                            self._compare_object_attributes(
                                frag_val, pos, ref_frag_val, statement, test_case
                            )

    # pylint: disable=too-many-arguments
    def _compare_class_fields(
        self,
        frag_val: Dict[Any, Any],
        pos: int,
        ref_frag_val: Dict[Any, Any],
        statement: st.Statement,
        test_case: tc.TestCase,
    ) -> None:
        for field, ref_value in ref_frag_val.items():
            value = frag_val.get(field)
            if ref_value != value:
                obj_vr = self._get_current_object_ref(test_case, pos)
                obj_class = self._get_current_object_class(obj_vr)
                assertion = fa.FieldAssertion(None, ref_value, field, None, [obj_class])
                if assertion not in self._field_assertions:
                    self._field_assertions.add(assertion)
                    statement.add_assertion(assertion)

    # pylint: disable=too-many-arguments
    def _compare_object_attributes(
        self,
        frag_val: Dict[Any, Any],
        pos: int,
        ref_frag_val: Dict[Any, Any],
        statement: st.Statement,
        test_case: tc.TestCase,
    ) -> None:
        for field, ref_value in ref_frag_val.items():
            value = frag_val.get(field)
            if ref_value != value:
                obj_vr = self._get_current_object_ref(test_case, pos)
                assertion = fa.FieldAssertion(obj_vr, ref_value, field)
                if assertion not in self._field_assertions:
                    self._field_assertions.add(assertion)
                    statement.add_assertion(assertion)

    def _compare_globals(
        self,
        globals_frame: Dict[Any, Any],
        globals_frame_ref: Dict[Any, Any],
        statement: st.Statement,
    ) -> None:
        for module_alias in globals_frame_ref.keys():
            globals_frame_ref_modules = globals_frame_ref.get(module_alias)
            assert (
                globals_frame_ref_modules is not None
            ), "Expected a module for the module alias"
            for global_field, ref_value in globals_frame_ref_modules.items():
                value = globals_frame[module_alias][global_field]
                if ref_value != value:
                    assertion = fa.FieldAssertion(
                        None, ref_value, global_field, module_alias
                    )
                    if assertion not in self._global_assertions:
                        self._global_assertions.add(assertion)
                        statement.add_assertion(assertion)

    @staticmethod
    def _compare_return_value(
        dataframe: Dict[Any, Any], ref_rv: Any, statement: st.Statement, key_retval: str
    ) -> None:
        retval = dataframe.get(key_retval)
        if retval != ref_rv:
            statement_vr = statement.ret_val
            assertion = oa.ComplexAssertion(statement_vr, ref_rv)
            statement.add_assertion(assertion)

    @staticmethod
    def _compare_attributes(dataframe: Dict[Any, Any]):
        pass

    @staticmethod
    def _get_testcase_by_id(
        test_cases: List[tc.TestCase], test_case_id: int
    ) -> Optional[tc.TestCase]:
        for test_case in test_cases:
            if cast(dtc.DefaultTestCase, test_case).id == test_case_id:
                return test_case
        return None

    @staticmethod
    def _get_statement_by_pos(
        test_case: tc.TestCase, position: int
    ) -> Optional[st.Statement]:
        if 0 <= position < len(test_case.statements):
            return test_case.statements[position]
        return None

    @staticmethod
    def _get_current_object_ref(
        test_case: tc.TestCase, position: int
    ) -> Optional[vr.VariableReference]:
        while position >= 0:
            if isinstance(test_case.statements[position], ps.ConstructorStatement):
                return test_case.statements[position].ret_val
            position -= 1
        return None

    @staticmethod
    def _get_current_object_class(
        var_ref: Optional[vr.VariableReference],
    ) -> Optional[str]:
        if var_ref and var_ref.variable_type:
            return var_ref.variable_type.__name__
        return None
