#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the client module."""
# ruff: noqa: FBT001, FBT002

import logging

from contextlib import contextmanager
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.generator import ReturnCode
from pynguin.master_worker.client import PynguinClient
from pynguin.master_worker.client import run_pynguin_with_master_worker
from pynguin.master_worker.worker import WorkerResult


# Test Data Factories
def create_worker_result(
    task_id: str = "test_task",
    status: str = "success",
    return_code: int = 0,
    error_message: str = "",
    traceback_str: str = "",
) -> WorkerResult:
    """Factory for creating WorkerResult instances."""
    return WorkerResult(
        task_id=task_id,
        status=status,
        return_code=return_code,
        error_message=error_message,
        traceback_str=traceback_str,
    )


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


# Test Helpers
@contextmanager
def mock_master_operations(
    config_convert_return=None,
    *,
    master_run_return=True,
    master_result=None,
    config_convert_side_effect=None,
):
    """Context manager to mock common master operations."""
    if config_convert_return is None:
        config_convert_return = {"module_name": "test"}

    with (
        patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
        patch("pynguin.master_worker.master.MasterProcess.run") as mock_run,
        patch("pynguin.master_worker.master.MasterProcess.get_result") as mock_get_result,
    ):
        if config_convert_side_effect:
            mock_convert.side_effect = config_convert_side_effect
        else:
            mock_convert.return_value = config_convert_return
        mock_run.return_value = master_run_return
        mock_get_result.return_value = master_result
        yield mock_convert, mock_run, mock_get_result


def create_started_client(config=None) -> PynguinClient:
    """Helper to create a started PynguinClient."""
    if config is None:
        config = create_mock_configuration()
    client = PynguinClient(config)
    client._started = True
    return client


# Fixtures
@pytest.fixture
def mock_configuration():
    """Mock configuration for testing."""
    return create_mock_configuration()


@pytest.fixture
def client(mock_configuration):
    """PynguinClient instance for testing."""
    return PynguinClient(mock_configuration)


# Test Cases
@pytest.mark.parametrize(
    "worker_result,expected_return_code",
    [
        (create_worker_result(status="success", return_code=0), ReturnCode.OK),
        (create_worker_result(status="timeout", return_code=1), ReturnCode.SETUP_FAILED),
        (
            create_worker_result(
                status="error",
                return_code=1,
                error_message="Test error",
                traceback_str="Traceback...",
            ),
            ReturnCode.SETUP_FAILED,
        ),
    ],
)
def test_generate_tests_different_results(worker_result, expected_return_code):
    """Test generate_tests with different worker results."""
    client = create_started_client()

    with mock_master_operations(master_result=worker_result):
        result = client.generate_tests()

    assert result == expected_return_code


@pytest.mark.parametrize(
    "master_run_return,master_result,expected_return_code",
    [
        (True, None, ReturnCode.SETUP_FAILED),  # No result
        (False, None, ReturnCode.SETUP_FAILED),  # Master run failed
    ],
)
def test_generate_tests_failure_cases(master_run_return, master_result, expected_return_code):
    """Test generate_tests failure scenarios."""
    client = create_started_client()

    with mock_master_operations(
        master_run_return=master_run_return,
        master_result=master_result,
    ):
        result = client.generate_tests()

    assert result == expected_return_code


def test_generate_tests_exception():
    """Test generate_tests with exception."""
    client = create_started_client()

    with mock_master_operations(config_convert_side_effect=Exception("Test exception")):
        result = client.generate_tests()

    assert result == ReturnCode.SETUP_FAILED


def test_generate_tests_not_started(caplog):
    """Test generate_tests when client is not started."""
    client = PynguinClient(create_mock_configuration())

    with caplog.at_level(logging.ERROR):
        result = client.generate_tests()

    assert result == ReturnCode.SETUP_FAILED
    assert "Client is not started" in caplog.text


@pytest.mark.parametrize(
    "use_master_worker,subprocess_if_recommended",
    [
        (True, True),  # Should override subprocess settings
        (True, False),  # No override needed
        (False, True),  # No override needed
    ],
)
def test_generate_tests_subprocess_configuration(use_master_worker, subprocess_if_recommended):
    """Test that subprocess configuration is properly overridden."""
    config = create_mock_configuration(
        use_master_worker=use_master_worker,
        subprocess_if_recommended=subprocess_if_recommended,
    )
    client = create_started_client(config)
    worker_result = create_worker_result()

    with mock_master_operations(master_result=worker_result):
        result = client.generate_tests()

    # Verify the client ran successfully
    assert result == ReturnCode.OK


@pytest.mark.parametrize(
    "master_start_return,expected_started",
    [
        (True, True),  # Successful start
        (False, False),  # Failed start
    ],
)
def test_client_start(master_start_return, expected_started):
    """Test client start functionality."""
    client = PynguinClient(create_mock_configuration())

    with patch.object(client.master, "start", return_value=master_start_return):
        result = client.start()

    assert result == master_start_return
    assert client._started == expected_started


def test_client_start_already_started(caplog):
    """Test starting already started client."""
    client = PynguinClient(create_mock_configuration())
    client._started = True

    with caplog.at_level(logging.WARNING):
        result = client.start()

    assert result is True
    assert "Client is already started" in caplog.text


@pytest.mark.parametrize(
    "initially_started,should_call_master_stop",
    [
        (False, False),  # Not started, should not call master.stop
        (True, True),  # Started, should call master.stop
    ],
)
def test_client_stop(initially_started, should_call_master_stop):
    """Test client stop functionality."""
    client = PynguinClient(create_mock_configuration())
    client._started = initially_started

    with patch.object(client.master, "stop") as mock_stop:
        client.stop()

    if should_call_master_stop:
        mock_stop.assert_called_once()
    else:
        mock_stop.assert_not_called()

    assert not client._started


def test_client_initialization():
    """Test client initialization."""
    configuration = create_mock_configuration()
    client = PynguinClient(configuration)

    assert client.configuration == configuration
    assert client.master is not None
    assert not client._started


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
        patch.object(PynguinClient, "generate_tests", return_value=generate_result),
    ):
        result = run_pynguin_with_master_worker(configuration)

    assert result == expected_result


def test_run_pynguin_with_master_worker_exception():
    """Test the convenience function with exception during context management."""
    configuration = create_mock_configuration()

    with (
        patch.object(PynguinClient, "start", side_effect=Exception("Test error")),
        pytest.raises(Exception, match="Test error"),
    ):
        run_pynguin_with_master_worker(configuration)


@pytest.mark.parametrize("subprocess", [True, False])
def test_integration_run_pynguin_with_master_worker(subprocess):
    """Test integration between client and master."""
    config.configuration.seeding = config.SeedingConfiguration(seed=42)
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
