#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.assertion.mutation_analysis.mutationadapter as ma
import pynguin.assertion.mutation_analysis.mutationanalysisexecution as mae
import pynguin.assertion.mutation_analysis.mutationanalysisgenerator as mag
import pynguin.testcase.execution as ex
from pynguin.testcase.statement import ConstructorStatement


class Foo:
    foo = "bar"

    def __init__(self, bar):
        self._bar = bar


def test_init():
    executor = ex.TestCaseExecutor(MagicMock())
    with mock.patch.object(executor, "add_observer") as executor_mock:
        mag.MutationAnalysisGenerator(executor)
        executor_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module")
def test_visit_test_suite_chromosome_step1(adapter_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    gen.visit_test_suite_chromosome(MagicMock())
    adapter_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module")
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step2(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    gen._storage = cs.CollectorStorage()
    gen._storage.append_execution()
    gen.visit_test_suite_chromosome(MagicMock())
    execution_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_rv(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {(cs.EntryTypes.RETURN_VALUE, statement): 42}
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[42, 43]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_rv_not(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {(cs.EntryTypes.RETURN_VALUE, statement): Foo(42)}
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[Foo(42), Foo(43)]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_attr(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {(cs.EntryTypes.OBJECT_ATTRIBUTE, statement, MagicMock(), "foo"): 1}
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[2, 2]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_attr_not(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {(cs.EntryTypes.OBJECT_ATTRIBUTE, statement, MagicMock(), "foo"): Foo(1)}
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[Foo(2), Foo(2)]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_cf(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {
        (cs.EntryTypes.CLASS_FIELD, statement, MagicMock(__name__="test"), "foo"): "bar"
    }
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=["bar", "foo"]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_cf_not(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {
        (cs.EntryTypes.CLASS_FIELD, statement, MagicMock(__name__="test"), "foo"): Foo(
            "bar"
        )
    }
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[Foo("bar"), Foo("foo")]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_g(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {(cs.EntryTypes.GLOBAL_FIELD, statement, "module", "field"): 1337}
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[69, 1]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(mae.MutationAnalysisExecution, "execute")
def test_visit_test_suite_chromosome_step3_g_not(adapter_mock, execution_mock):
    gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
    statement = ConstructorStatement(MagicMock(), MagicMock())
    ref = {(cs.EntryTypes.GLOBAL_FIELD, statement, "module", "field"): Foo(1337)}
    with mock.patch.object(
        gen._storage, "get_execution_entry", return_value=ref
    ) as ref_mock:
        with mock.patch.object(
            gen._storage, "get_mutations", return_value=[Foo(69), Foo(1)]
        ) as mut_mock:
            gen.visit_test_suite_chromosome(MagicMock())
            assert len(statement._assertions) == 1
            mut_mock.assert_called_once()
            ref_mock.assert_called_once()
