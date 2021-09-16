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

import pynguin.assertion.assertion as ass
import pynguin.assertion.complexassertion as ca
import pynguin.assertion.fieldassertion as fa
import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.assertion.mutation_analysis.mutationadapter as ma
import pynguin.assertion.mutation_analysis.mutationanalysisexecution as ce
import pynguin.assertion.mutation_analysis.statecollectingobserver as sco
import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.execution.testcaseexecutor as ex
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.statement as st
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.utils.collection_utils as cu
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
        # TODO(fk) what to do with existing observers?
        self._executor.add_observer(sco.StateCollectingObserver(self._storage))
        self._global_assertions: Set[fa.FieldAssertion] = set()
        self._field_assertions: Set[fa.FieldAssertion] = set()
        self._last_obj_assertion: Optional[ass.Assertion] = None

        self._statement: Optional[st.Statement] = None
        self._test_case: Optional[tc.TestCase] = None

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        test_cases = [chrom.test_case for chrom in chromosome.test_case_chromosomes]

        mutated_modules = [x for x, _ in self._mutate_module()]

        execution = ce.MutationAnalysisExecution(
            self._executor, mutated_modules, self._storage
        )
        self._logger.info("Execute %d test cases", len(test_cases))
        execution.execute(test_cases)

        self._logger.info("Generating assertions for test cases")
        self._generate_assertions(test_cases)

    def visit_test_case_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        pass  # nothing to do here

    @staticmethod
    def _mutate_module() -> List[Tuple[ModuleType, Any]]:
        adapter = ma.MutationAdapter()
        return adapter.mutate_module()

    def _generate_assertions(self, test_cases: List[tc.TestCase]) -> None:
        # Get the reference data from the execution on the not mutate module
        reference = self._storage.get_items(0)

        # Iterate over all dataframes for the reference execution
        for ref_dataframe in reference:

            # Get the test case id and position of the frame
            tc_id = cast(int, ref_dataframe[cs.KEY_TEST_ID])
            pos = cast(int, ref_dataframe[cs.KEY_POSITION])

            # Get the corresponding test case and statement
            self._test_case = self._get_testcase_by_id(test_cases, tc_id)
            assert self._test_case is not None, "Expected a testcase to be found."
            self._statement = self._get_statement_by_pos(self._test_case, pos)
            assert self._statement is not None, "Expected a statement to be found."

            # Get the mutated frames corresponding to the id and position
            mutated_dataframes = self._storage.get_dataframe_of_mutations(tc_id, pos)

            # Get the reference state of the return value of the current statement
            ref_rv = ref_dataframe[cs.KEY_RETURN_VALUE]

            # Get the reference states of the global fields at this dataframe
            ref_globals = ref_dataframe[cs.KEY_GLOBALS]

            # Get all stored object fragments
            remainders = cu.dict_without_keys(
                ref_dataframe,
                {cs.KEY_TEST_ID, cs.KEY_POSITION, cs.KEY_RETURN_VALUE, cs.KEY_GLOBALS},
            )

            # Reset the last obj assertion
            self._last_obj_assertion = None

            # Compare the data of the not mutated run with the ones with mutations
            self._compare_with_mutated(
                mutated_dataframes, ref_globals, ref_rv, remainders
            )

    def _compare_with_mutated(
        self, mutated_dataframes, ref_globals, ref_rv, remainders
    ):
        # Iterate over all mutated dataframes and compare
        for dataframe in mutated_dataframes:

            # Compare the Return Value
            self._compare_return_value(dataframe[cs.KEY_RETURN_VALUE], ref_rv)

            # Compare the global fields
            self._compare_globals(dataframe[cs.KEY_GLOBALS], ref_globals)

            # Compare the remaining objects
            for key, ref_fragment in remainders.items():
                fragment = dataframe.get(key)
                assert fragment is not None, "Expected any data from the datafragment"
                for frag_key, ref_frag_val in ref_fragment.items():
                    frag_val = fragment.get(frag_key)
                    if frag_key == cs.KEY_CLASS_FIELD:
                        # Class fields
                        self._compare_class_fields(frag_val, ref_frag_val, key)
                    elif frag_key == cs.KEY_OBJECT_ATTRIBUTE:
                        # Object attributes
                        self._compare_object_attributes(frag_val, ref_frag_val, key)

    # pylint: disable=too-many-arguments
    def _compare_class_fields(
        self, frag_val: Dict[str, Any], ref_frag_val: Dict[str, Any], obj_index: int
    ) -> None:
        for field, ref_value in ref_frag_val.items():
            if ref_value != frag_val.get(field):
                obj_vr = self._get_current_object_ref(obj_index)
                obj_class = self._get_current_object_class(obj_vr)
                obj_module = self._get_current_object_module(obj_vr)
                if self._is_assertable_item(ref_value):
                    # Class variable can be asserted straight away
                    self._gen_assertable_cf(field, obj_class, obj_module, ref_value)
                elif hasattr(ref_value, "__dict__"):
                    # Class variable cannot be asserted, if the attribute is an object,
                    # we try to generate an assertion for each of the attributes
                    # of this object
                    self._gen_not_assertable_cf(field, obj_class, obj_module, ref_value)

    def _gen_assertable_cf(
        self,
        field: str,
        obj_class: Optional[str],
        obj_module: Optional[str],
        ref_value: Any,
    ) -> None:
        assertion = fa.FieldAssertion(None, ref_value, field, obj_module, [obj_class])
        if assertion and assertion not in self._field_assertions:
            self._field_assertions.add(assertion)
            self._add_assertion(assertion)

    def _gen_not_assertable_cf(
        self,
        field: str,
        obj_class: Optional[str],
        obj_module: Optional[str],
        ref_value: Any,
    ) -> None:
        for item_field, field_val in vars(ref_value).items():
            if self._is_assertable_item(field_val):
                assertion = fa.FieldAssertion(
                    None,
                    ref_value,
                    item_field,
                    obj_module,
                    [field, obj_class],
                )
                if assertion not in self._field_assertions:
                    self._field_assertions.add(assertion)
                    self._add_assertion(assertion)

    # pylint: disable=too-many-arguments
    def _compare_object_attributes(
        self, frag_val: Dict[str, Any], ref_frag_val: Dict[str, Any], obj_index: int
    ) -> None:
        for field, ref_value in ref_frag_val.items():
            value = frag_val.get(field)
            if ref_value != value:
                obj_vr = self._get_current_object_ref(obj_index)
                if self._is_assertable_item(ref_value):
                    # Attribute can be asserted straight away
                    self._gen_assertable_attr(field, obj_vr, ref_value)
                elif hasattr(ref_value, "__dict__"):
                    # Attribute cannot be asserted, if the attribute is an object,
                    # we try to generate an assertion for each of the attributes
                    # of this object
                    self._gen_not_assertable_attr(field, obj_vr, ref_value)

    def _gen_assertable_attr(
        self, field: str, obj_vr: Optional[vr.VariableReference], ref_value: Any
    ) -> None:
        assertion = fa.FieldAssertion(obj_vr, ref_value, field)
        if assertion not in self._field_assertions:
            self._field_assertions.add(assertion)
            self._add_assertion(assertion)

    def _gen_not_assertable_attr(
        self, field: str, obj_vr: Optional[vr.VariableReference], ref_value: Any
    ) -> None:
        for item_field, field_val in vars(ref_value).items():
            if self._is_assertable_item(field_val):
                assertion = fa.FieldAssertion(
                    obj_vr, ref_value, item_field, None, [field]
                )
                if assertion not in self._field_assertions:
                    self._field_assertions.add(assertion)
                    self._add_assertion(assertion)

    def _compare_globals(
        self,
        globals_frame: Dict[str, Dict[str, Any]],
        globals_frame_ref: Dict[str, Dict[str, Any]],
    ) -> None:
        for module_name in globals_frame_ref.keys():
            globals_frame_ref_modules = globals_frame_ref.get(module_name)
            assert (
                globals_frame_ref_modules is not None
            ), "Expected a module for the module alias"
            for global_field, ref_value in globals_frame_ref_modules.items():
                value = globals_frame[module_name][global_field]
                if ref_value != value:
                    if self._is_assertable_item(ref_value):
                        # Global field can be asserted straight away
                        self._gen_assertable_global(
                            global_field, module_name, ref_value
                        )
                    elif hasattr(ref_value, "__dict__"):
                        # Global field cannot be asserted, if the attribute is an
                        # object, we try to generate an assertion for each of
                        # the attributes of this object
                        self._gen_not_assertable_global(
                            global_field, module_name, ref_value
                        )

    def _gen_assertable_global(
        self, global_field: str, module_name: str, ref_value: Any
    ) -> None:
        assertion = fa.FieldAssertion(None, ref_value, global_field, module_name)
        if assertion not in self._global_assertions:
            self._global_assertions.add(assertion)
            self._add_assertion(assertion)

    def _gen_not_assertable_global(
        self, global_field: str, module_name: str, ref_value: Any
    ) -> None:
        for field, field_val in vars(ref_value).items():
            if self._is_assertable_item(field_val):
                assertion = fa.FieldAssertion(
                    None, ref_value, field, module_name, [global_field]
                )
                if assertion not in self._global_assertions:
                    self._global_assertions.add(assertion)
                    self._add_assertion(assertion)

    def _compare_return_value(self, retval: Any, ref_rv: Any) -> None:
        if retval != ref_rv:
            if self._is_assertable_item(ref_rv):
                # Return value can be asserted straight away
                self._gen_assertable_retval(ref_rv)
            elif hasattr(ref_rv, "__dict__"):
                # Return value cannot be asserted, if the attribute is an object,
                # we try to generate an assertion for each of the attributes
                # of this object
                self._gen_not_assertable_retval(ref_rv)

    def _gen_assertable_retval(self, ref_rv: Any) -> None:
        assertion: ass.Assertion = ca.ComplexAssertion(
            self._get_variable_reference(), ref_rv
        )
        if (
            not self._last_obj_assertion
            or self._last_obj_assertion.value is not assertion.value
        ):
            self._last_obj_assertion = assertion
            self._add_assertion(assertion)

    def _gen_not_assertable_retval(self, ref_rv: Any) -> None:
        for field, field_val in vars(ref_rv).items():
            if self._is_assertable_item(field_val):
                assertion = fa.FieldAssertion(
                    self._get_variable_reference(), field_val, field
                )
                if assertion not in self._field_assertions:
                    self._field_assertions.add(assertion)
                    self._add_assertion(assertion)

    @staticmethod
    def _get_testcase_by_id(
        test_cases: List[tc.TestCase], test_case_id: int
    ) -> Optional[tc.TestCase]:
        for test_case in test_cases:
            if (
                isinstance(test_case, dtc.DefaultTestCase)
                and test_case.id == test_case_id
            ):
                return test_case
        return None

    @staticmethod
    def _get_statement_by_pos(
        test_case: tc.TestCase, position: int
    ) -> Optional[st.Statement]:
        if 0 <= position < len(test_case.statements):
            return test_case.statements[position]
        return None

    def _get_current_object_ref(self, obj_index: int) -> Optional[vr.VariableReference]:
        if self._test_case:
            return cu.find_xth_element_of_type(
                self._test_case.statements, ps.ConstructorStatement, int(obj_index) + 1
            ).ret_val
        raise ValueError(
            "A test case must be present in order to get the object reference."
        )

    @staticmethod
    def _get_current_object_class(
        var_ref: Optional[vr.VariableReference],
    ) -> Optional[str]:
        if var_ref and var_ref.variable_type:
            return var_ref.variable_type.__name__
        return None

    @staticmethod
    def _get_current_object_module(
        var_ref: Optional[vr.VariableReference],
    ) -> Optional[str]:
        if var_ref and var_ref.variable_type:
            return var_ref.variable_type.__module__
        return None

    @staticmethod
    def _is_comparable_object(obj: Any) -> bool:
        return vars(obj.__class__).get("__eq__", None) and vars(obj.__class__).get(
            "__hash__", None
        )

    def _is_assertable_item(self, item: Any) -> bool:
        return (
            tu.is_primitive_type(type(item))
            or tu.is_none_type(type(item))
            or tu.is_enum(type(item))
            or tu.is_collection_type(type(item))
            or self._is_comparable_object(item)
        )

    def _add_assertion(self, assertion: ass.Assertion) -> None:
        if self._statement:
            self._statement.add_assertion(assertion)
        else:
            raise ValueError("A statement must be present in order to add an assertion")

    def _get_variable_reference(self) -> vr.VariableReference:
        if self._statement:
            return self._statement.ret_val
        raise ValueError(
            "A statement must be present in order to get the variable reference."
        )
