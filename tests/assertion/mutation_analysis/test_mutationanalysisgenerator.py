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
import pynguin.testcase.execution.testcaseexecutor as ex
import pynguin.testcase.statements.parametrizedstatements as ps


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
    gen.visit_test_suite_chromosome(MagicMock())
    execution_mock.assert_called_once()


@mock.patch.object(ma.MutationAdapter, "mutate_module", return_value=MagicMock())
@mock.patch.object(
    mag.MutationAnalysisGenerator,
    "_get_testcase_by_id",
    return_value=MagicMock(statements=[MagicMock(spec=ps.ConstructorStatement)]),
)
@mock.patch.object(
    mag.MutationAnalysisGenerator, "_get_current_object_class", return_value=MagicMock()
)
@mock.patch.object(
    mag.MutationAnalysisGenerator, "_get_statement_by_pos", return_value=MagicMock()
)
def test_visit_test_suite_chromosome_step3(
    adapter_mock, get_tc_mock, get_obj_class_mock, get_st_mock
):
    dfs = [
        {
            cs.KEY_TEST_ID: MagicMock(),
            cs.KEY_POSITION: 0,
            cs.KEY_RETURN_VALUE: 0,
            cs.KEY_GLOBALS: {"module0": {"foo": "bar"}},
            "0": {
                cs.KEY_CLASS_FIELD: {"foo": 42},
                cs.KEY_OBJECT_ATTRIBUTE: {"test": "foo"},
            },
        }
    ]

    dfs_mut = [
        {
            cs.KEY_TEST_ID: MagicMock(),
            cs.KEY_POSITION: 0,
            cs.KEY_RETURN_VALUE: 1,
            cs.KEY_GLOBALS: {"module0": {"foo": "test"}},
            "0": {
                cs.KEY_CLASS_FIELD: {"foo": 1337},
                cs.KEY_OBJECT_ATTRIBUTE: {"test": "bar"},
            },
        }
    ]

    with mock.patch.object(
        cs.CollectorStorage, "get_items", return_value=dfs
    ) as cs_get_items_mock:
        with mock.patch.object(
            cs.CollectorStorage, "get_dataframe_of_mutations", return_value=dfs_mut
        ) as cs_get_def_mut_mock:
            gen = mag.MutationAnalysisGenerator(ex.TestCaseExecutor(MagicMock()))
            gen.visit_test_suite_chromosome(MagicMock())
            cs_get_items_mock.assert_called_once_with(0)
            cs_get_def_mut_mock.assert_called_once()
