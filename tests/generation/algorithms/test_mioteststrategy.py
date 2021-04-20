#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.generation.algorithms.mioteststrategy import MIOTestStrategy, Parameters


def test_parameters_default():
    parameters = Parameters()
    assert parameters.n == config.configuration.number_of_tests_per_target_initial
    assert parameters.m == config.configuration.num_mutations_initial
    assert (
        parameters.Pr
        == config.configuration.random_test_or_from_archive_probability_initial
    )
    parameters.is_valid()


def test_update_parameters_gradual():
    strategy = MIOTestStrategy()
    strategy._archive = MagicMock()
    config.configuration.exploitation_starts_at_percent = 0.4
    with mock.patch.object(strategy, "progress") as progress_mock:
        progress_mock.return_value = 0.5
        strategy._update_parameters()
        assert strategy._parameters.m == config.configuration.num_mutations_focused
        assert (
            strategy._parameters.n
            == config.configuration.number_of_tests_per_target_focused
        )
        assert (
            strategy._parameters.Pr
            == config.configuration.random_test_or_from_archive_probability_focused
        )


def test_update_parameters_focused_phase():
    strategy = MIOTestStrategy()
    strategy._archive = MagicMock()
    config.configuration.exploitation_starts_at_percent = 0.4
    config.configuration.number_of_tests_per_target_initial = 2
    config.configuration.num_mutations_initial = 2
    config.configuration.random_test_or_from_archive_probability_initial = 0.2
    config.configuration.num_mutations_focused = 4
    config.configuration.number_of_tests_per_target_focused = 4
    config.configuration.random_test_or_from_archive_probability_focused = 0.4
    with mock.patch.object(strategy, "progress") as progress_mock:
        progress_mock.return_value = 0.2
        strategy._update_parameters()
        assert strategy._parameters.m == 3
        assert strategy._parameters.n == 3
        assert strategy._parameters.Pr == pytest.approx(0.3)
