#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for the master-worker architecture."""

import pytest

import pynguin.configuration as config

from pynguin.generator import ReturnCode
from pynguin.master_worker.client import run_pynguin_with_master_worker


@pytest.mark.parametrize("subprocess", [True, False])
def test_integration(subprocess):
    """Test integration between client and master."""
    config.configuration.stopping.maximum_iterations = 3
    config.configuration.module_name = "tests.fixtures.examples.basket"
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.test_insertion_probability = 0.5
    config.configuration.search_algorithm.population = 3
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    config.configuration.use_master_worker = True
    config.configuration.subprocess_if_recommended = False
    config.configuration.subprocess = subprocess
    return_code = run_pynguin_with_master_worker(config.configuration)
    assert return_code == ReturnCode.OK
