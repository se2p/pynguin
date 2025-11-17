#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the client module."""
# ruff: noqa: FBT001, FBT002

import threading
from unittest.mock import MagicMock, patch

import pytest

import pynguin.configuration as config
from pynguin.generator import ReturnCode
from pynguin.master_worker.client import PynguinClient, run_pynguin_with_master_worker
from pynguin.master_worker.worker import WorkerResult, WorkerReturnCode


def create_mock_configuration(
    *,
    use_master_worker: bool = True,
    subprocess_if_recommended: bool = True,
) -> MagicMock:
    """Factory for creating mock configuration instances."""
    config = MagicMock()
    config.use_master_worker = use_master_worker
    config.subprocess_if_recommended = subprocess_if_recommended
    return config


@pytest.mark.parametrize(
    "mock_result, expected_return_code, raises_exception",
    [
        (None, ReturnCode.NO_TESTS_GENERATED, False),
        (
            WorkerResult(
                task_id="1",
                worker_return_code=WorkerReturnCode.ERROR,
                return_code=ReturnCode.NO_TESTS_GENERATED,
            ),
            ReturnCode.NO_TESTS_GENERATED,
            False,
        ),
        (
            WorkerResult(
                task_id="2",
                worker_return_code=WorkerReturnCode.TIMEOUT,
                return_code=ReturnCode.NO_TESTS_GENERATED,
            ),
            ReturnCode.NO_TESTS_GENERATED,
            False,
        ),
        (
            WorkerResult(task_id="3", worker_return_code=WorkerReturnCode.OK, return_code=None),
            ReturnCode.NO_TESTS_GENERATED,
            False,
        ),
        (
            WorkerResult(
                task_id="4", worker_return_code=WorkerReturnCode.OK, return_code="success_code"
            ),
            "success_code",
            False,
        ),
        (None, ReturnCode.SETUP_FAILED, True),
    ],
)
def test_run_pynguin(mock_result, expected_return_code, raises_exception):
    mock_config = MagicMock()
    client = PynguinClient(mock_config)
    client.master = MagicMock()

    if raises_exception:
        client.master.start_pynguin.side_effect = Exception("fail")
    else:
        client.master.start_pynguin.side_effect = None

    client.master.get_result = MagicMock(return_value=mock_result)
    result = client.run_pynguin()
    assert result == expected_return_code


def test_context_manager():
    """Test context manager functionality."""
    configuration = create_mock_configuration()

    with (
        patch.object(PynguinClient, "start") as mock_start,
        patch.object(PynguinClient, "stop") as mock_stop,
        PynguinClient(configuration) as client,
    ):
        assert isinstance(client, PynguinClient)

    mock_start.assert_called_once()
    mock_stop.assert_called_once()


@pytest.mark.parametrize(
    "generate_result,expected_result",
    [
        (ReturnCode.OK, ReturnCode.OK),
        (ReturnCode.SETUP_FAILED, ReturnCode.SETUP_FAILED),
    ],
)
def test_run_pynguin_with_master_worker(generate_result, expected_result):
    """Test the convenience function."""
    configuration = create_mock_configuration()

    with (
        patch.object(PynguinClient, "start"),
        patch.object(PynguinClient, "stop"),
        patch.object(PynguinClient, "run_pynguin", return_value=generate_result),
    ):
        result = run_pynguin_with_master_worker(configuration)

    assert result == expected_result


@pytest.mark.parametrize("subprocess", [True, False])
def test_integration_run_pynguin_with_master_worker(tmpdir, subprocess):
    """Test integration between client and master."""
    config.configuration.seeding = config.SeedingConfiguration(seed=42)
    config.configuration.test_case_output = config.TestCaseOutputConfiguration(output_path=tmpdir)
    config.configuration.stopping.maximum_iterations = 2
    config.configuration.module_name = "tests.fixtures.examples.basket"
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.test_insertion_probability = 0.5
    config.configuration.search_algorithm.population = 2
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    config.configuration.use_master_worker = True
    config.configuration.subprocess_if_recommended = False
    config.configuration.subprocess = subprocess
    return_code = run_pynguin_with_master_worker(config.configuration)
    assert return_code == ReturnCode.OK
    assert len(threading.enumerate()) == 1
