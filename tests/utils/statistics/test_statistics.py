#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.utils.statistics.statistics as stat
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.statistics.timer import Timer


def test_variables_generator():
    value_1 = MagicMock(Timer)
    value_2 = MagicMock(Timer)
    stat.track_output_variable(RuntimeVariable.TotalTime, value_1)
    stat.track_output_variable(RuntimeVariable.TotalTime, value_2)
    result = [v for _, v in stat.variables_generator]
    assert result == [value_1, value_2]
