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
    assert (
        parameters.n
        == config.configuration.mio.initial_config.number_of_tests_per_target
    )
    assert parameters.m == config.configuration.mio.initial_config.number_of_mutations
    assert (
        parameters.Pr
        == config.configuration.mio.initial_config.random_test_or_from_archive_probability
    )
    parameters.is_valid()


def test_update_parameters_gradual():
    strategy = MIOTestStrategy()
    strategy._archive = MagicMock()
    config.configuration.mio.exploitation_starts_at_percent = 0.4
    with mock.patch.object(strategy, "progress") as progress_mock:
        progress_mock.return_value = 0.5
        strategy._update_parameters()
        assert (
            strategy._parameters.m
            == config.configuration.mio.focused_config.number_of_mutations
        )
        assert (
            strategy._parameters.n
            == config.configuration.mio.focused_config.number_of_tests_per_target
        )
        assert (
            strategy._parameters.Pr
            == config.configuration.mio.focused_config.random_test_or_from_archive_probability
        )


def test_update_parameters_focused_phase():
    strategy = MIOTestStrategy()
    strategy._archive = MagicMock()
    config.configuration.mio.exploitation_starts_at_percent = 0.4
    config.configuration.mio.initial_config.number_of_tests_per_target = 2
    config.configuration.mio.initial_config.number_of_mutations = 2
    config.configuration.mio.initial_config.random_test_or_from_archive_probability = (
        0.2
    )
    config.configuration.mio.focused_config.number_of_mutations = 4
    config.configuration.mio.focused_config.number_of_tests_per_target = 4
    config.configuration.mio.focused_config.random_test_or_from_archive_probability = (
        0.4
    )
    with mock.patch.object(strategy, "progress") as progress_mock:
        progress_mock.return_value = 0.2
        strategy._update_parameters()
        assert strategy._parameters.m == 3
        assert strategy._parameters.n == 3
        assert strategy._parameters.Pr == pytest.approx(0.3)
