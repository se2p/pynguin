#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config

from pynguin.ga.algorithms.mioalgorithm import MIOAlgorithm
from pynguin.ga.algorithms.mioalgorithm import Parameters


def test_parameters_default():
    parameters = Parameters()
    assert parameters.n == config.configuration.mio.initial_config.number_of_tests_per_target
    assert parameters.m == config.configuration.mio.initial_config.number_of_mutations
    # fmt: off
    assert (
        parameters.Pr
        == config.configuration.mio.initial_config
        .random_test_or_from_archive_probability
    )
    # fmt: on
    parameters.is_valid()


def test_update_parameters_gradual():
    strategy = MIOAlgorithm()
    strategy._archive = MagicMock()
    config.configuration.mio.exploitation_starts_at_percent = 0.4
    with mock.patch.object(strategy, "progress") as progress_mock:
        progress_mock.return_value = 0.5
        strategy._update_parameters()
        assert strategy._parameters.m == config.configuration.mio.focused_config.number_of_mutations
        assert (
            strategy._parameters.n
            == config.configuration.mio.focused_config.number_of_tests_per_target
        )
        # fmt: off
        assert (
            strategy._parameters.Pr
            == config.configuration.mio.focused_config
            .random_test_or_from_archive_probability
        )
        # fmt: on


def test_update_parameters_focused_phase():
    strategy = MIOAlgorithm()
    strategy._archive = MagicMock()
    config.configuration.mio.exploitation_starts_at_percent = 0.4
    config.configuration.mio.initial_config.number_of_tests_per_target = 2
    config.configuration.mio.initial_config.number_of_mutations = 2
    config.configuration.mio.initial_config.random_test_or_from_archive_probability = 0.2
    config.configuration.mio.focused_config.number_of_mutations = 4
    config.configuration.mio.focused_config.number_of_tests_per_target = 4
    config.configuration.mio.focused_config.random_test_or_from_archive_probability = 0.4
    with mock.patch.object(strategy, "progress") as progress_mock:
        progress_mock.return_value = 0.2
        strategy._update_parameters()
        assert strategy._parameters.m == 3
        assert strategy._parameters.n == 3
        assert strategy._parameters.Pr == pytest.approx(0.3)
