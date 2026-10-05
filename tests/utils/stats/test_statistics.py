#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pynguin.utils.statistics.stats as stat
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def test_variables_generator():
    value_1 = 23.42
    value_2 = 42.23
    stat.track_output_variable(RuntimeVariable.TotalTime, value_1)
    stat.track_output_variable(RuntimeVariable.TotalTime, value_2)
    result = [v for _, v in stat.variables_generator]
    assert result in ([], [value_1, value_2])


def test_add_sequence_samples_are_returned_by_get_sequence_samples():
    samples = [(1_000_000_000, 0.25), (2_000_000_000, 0.5)]

    stat.add_sequence_samples(RuntimeVariable.CoverageTimeline, samples)

    assert stat.get_sequence_samples(RuntimeVariable.CoverageTimeline) == samples
    assert stat.get_sequence_samples(RuntimeVariable.SizeTimeline) == []
