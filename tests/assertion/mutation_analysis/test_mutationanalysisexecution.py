#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
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
    execution = mae.MutationAnalysisExecution(executor, [], MagicMock())
    execution.execute([MagicMock()])
    executor.execute.assert_called_once()


def test_execute_mutations():
    config.configuration.module_name = "sys"
    executor = MagicMock()
    mutation = MagicMock()
    storage = cs.CollectorStorage()
    execution = mae.MutationAnalysisExecution(executor, [mutation], storage)
    execution.execute([MagicMock()])
    assert len(storage._storage) == 2
    assert executor.execute.call_count == 2
