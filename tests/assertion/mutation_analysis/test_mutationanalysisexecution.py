#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.mutation_analysis.collectorstorage as cs
import pynguin.assertion.mutation_analysis.mutationanalysisexecution as mae
import pynguin.configuration as config


def test_execute_default():
    config.configuration.module_name = "sys"
    executor = MagicMock()
    execution = mae.MutationAnalysisExecution(executor, [])
    execution.execute([MagicMock()])
    executor.execute.assert_called_once()


def test_execute_mutations():
    config.configuration.module_name = "sys"
    executor = MagicMock()
    mutation = MagicMock()
    execution = mae.MutationAnalysisExecution(executor, [mutation])
    execution.execute([MagicMock()])
    assert cs.CollectorStorage._execution_index == 1
    assert executor.execute.call_count == 2
