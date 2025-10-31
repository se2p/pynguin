#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the client module."""

import logging

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pynguin.generator import ReturnCode
from pynguin.master_worker.client import PynguinClient
from pynguin.master_worker.client import run_pynguin_with_master_worker
from pynguin.master_worker.master import MasterProcess
from pynguin.master_worker.worker import WorkerResult


# Fixtures
@pytest.fixture
def mock_configuration():
    """Mock configuration for testing."""
    config = MagicMock()
    config.use_master_worker = True
    config.subprocess_if_recommended = True
    return config


@pytest.fixture
def client(mock_configuration):
    """PynguinClient instance for testing."""
    return PynguinClient(mock_configuration)


@pytest.fixture
def started_client(client):
    """Started PynguinClient instance for testing."""
    client._started = True
    return client


@pytest.fixture
def success_worker_result():
    """Successful worker result for testing."""
    return WorkerResult(task_id="test_task", status="success", return_code=0)


@pytest.mark.parametrize(
    "worker_result,expected_return_code",
    [
        (WorkerResult(task_id="test_task", status="success", return_code=0), ReturnCode.OK),
        (
            WorkerResult(task_id="test_task", status="timeout", return_code=1),
            ReturnCode.SETUP_FAILED,
        ),
        (
            WorkerResult(
                task_id="test_task",
                status="error",
                return_code=1,
                error_message="Test error",
                traceback_str="Traceback...",
            ),
            ReturnCode.SETUP_FAILED,
        ),
    ],
)
def test_generate_tests_different_results(started_client, worker_result, expected_return_code):
    """Test generate_tests with different worker results."""
    with (
        patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
        patch.object(started_client.master, "run", return_value=True),
        patch.object(started_client.master, "get_result", return_value=worker_result),
    ):
        mock_convert.return_value = {"module_name": "test"}

        result = started_client.generate_tests()

    assert result == expected_return_code


def test_generate_tests_no_result(started_client):
    """Test generate_tests with no result."""
    with (
        patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
        patch.object(started_client.master, "run", return_value=True),
        patch.object(started_client.master, "get_result", return_value=None),
    ):
        mock_convert.return_value = {"module_name": "test"}

        result = started_client.generate_tests()

    assert result == ReturnCode.SETUP_FAILED


def test_generate_tests_master_run_failed(started_client):
    """Test generate_tests when master run fails."""
    with (
        patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
        patch.object(started_client.master, "run", return_value=False),
    ):
        mock_convert.return_value = {"module_name": "test"}

        result = started_client.generate_tests()

    assert result == ReturnCode.SETUP_FAILED


def test_generate_tests_exception(started_client):
    """Test generate_tests with exception."""
    with patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert:
        mock_convert.side_effect = Exception("Test exception")

        result = started_client.generate_tests()

    assert result == ReturnCode.SETUP_FAILED


def test_context_manager(mock_configuration):
    """Test context manager functionality."""
    with (
        patch.object(PynguinClient, "start") as mock_start,
        patch.object(PynguinClient, "stop") as mock_stop,
        PynguinClient(mock_configuration) as client,
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
def test_run_pynguin_with_master_worker(mock_configuration, generate_result, expected_result):
    """Test the convenience function."""
    with (
        patch.object(PynguinClient, "start"),
        patch.object(PynguinClient, "stop"),
        patch.object(PynguinClient, "generate_tests", return_value=generate_result),
    ):
        result = run_pynguin_with_master_worker(mock_configuration)

    assert result == expected_result


def test_run_pynguin_with_master_worker_exception(mock_configuration):
    """Test the convenience function with exception during context management."""
    with (
        patch.object(PynguinClient, "start", side_effect=Exception("Test error")),
        pytest.raises(Exception, match="Test error"),
    ):
        run_pynguin_with_master_worker(mock_configuration)


class TestPynguinClient:
    """Test cases for PynguinClient class."""

    def test_init(self):
        """Test client initialization."""
        configuration = MagicMock()
        client = PynguinClient(configuration)

        assert client.configuration == configuration
        assert isinstance(client.master, MasterProcess)
        assert not client._started

    def test_start_success(self):
        """Test successful client start."""
        configuration = MagicMock()
        client = PynguinClient(configuration)

        with patch.object(client.master, "start", return_value=True):
            result = client.start()

        assert result is True
        assert client._started

    def test_start_failure(self):
        """Test client start failure."""
        configuration = MagicMock()
        client = PynguinClient(configuration)

        with patch.object(client.master, "start", return_value=False):
            result = client.start()

        assert result is False
        assert not client._started

    def test_start_already_started(self, caplog):
        """Test starting already started client."""
        configuration = MagicMock()
        client = PynguinClient(configuration)
        client._started = True

        with caplog.at_level(logging.WARNING):
            result = client.start()

        assert result is True
        assert "Client is already started" in caplog.text

    def test_stop_not_started(self):
        """Test stopping client that is not started."""
        configuration = MagicMock()
        client = PynguinClient(configuration)

        # Should not raise any exception
        client.stop()

    def test_stop_started(self):
        """Test stopping started client."""
        configuration = MagicMock()
        client = PynguinClient(configuration)
        client._started = True

        with patch.object(client.master, "stop") as mock_stop:
            client.stop()

        mock_stop.assert_called_once()
        assert not client._started

    def test_generate_tests_not_started(self, caplog):
        """Test generate_tests when client is not started."""
        configuration = MagicMock()
        client = PynguinClient(configuration)

        with caplog.at_level(logging.ERROR):
            result = client.generate_tests()

        assert result == ReturnCode.SETUP_FAILED
        assert "Client is not started" in caplog.text

    def test_generate_tests_success(self):
        """Test successful test generation."""
        configuration = MagicMock()
        configuration.use_master_worker = True
        configuration.subprocess_if_recommended = True

        client = PynguinClient(configuration)
        client._started = True

        worker_result = WorkerResult(task_id="test_task", status="success", return_code=0)

        with (
            patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
            patch.object(client.master, "run", return_value=True),
            patch.object(client.master, "get_result", return_value=worker_result),
        ):
            mock_convert.return_value = {"module_name": "test"}

            result = client.generate_tests()

        assert result == ReturnCode.OK

    def test_generate_tests_timeout(self):
        """Test test generation timeout."""
        configuration = MagicMock()
        configuration.use_master_worker = True
        configuration.subprocess_if_recommended = False

        client = PynguinClient(configuration)
        client._started = True

        worker_result = WorkerResult(task_id="test_task", status="timeout", return_code=1)

        with (
            patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
            patch.object(client.master, "run", return_value=True),
            patch.object(client.master, "get_result", return_value=worker_result),
        ):
            mock_convert.return_value = {"module_name": "test"}

            result = client.generate_tests()

        assert result == ReturnCode.SETUP_FAILED

    def test_generate_tests_error(self):
        """Test test generation error."""
        configuration = MagicMock()
        configuration.use_master_worker = True
        configuration.subprocess_if_recommended = False

        client = PynguinClient(configuration)
        client._started = True

        worker_result = WorkerResult(
            task_id="test_task",
            status="error",
            return_code=1,
            error_message="Test error",
            traceback_str="Traceback...",
        )

        with (
            patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
            patch.object(client.master, "run", return_value=True),
            patch.object(client.master, "get_result", return_value=worker_result),
        ):
            mock_convert.return_value = {"module_name": "test"}

            result = client.generate_tests()

        assert result == ReturnCode.SETUP_FAILED

    def test_generate_tests_no_result(self):
        """Test test generation with no result."""
        configuration = MagicMock()
        client = PynguinClient(configuration)
        client._started = True

        with (
            patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
            patch.object(client.master, "run", return_value=True),
            patch.object(client.master, "get_result", return_value=None),
        ):
            mock_convert.return_value = {"module_name": "test"}

            result = client.generate_tests()

        assert result == ReturnCode.SETUP_FAILED

    def test_generate_tests_master_run_failed(self):
        """Test test generation when master run fails."""
        configuration = MagicMock()
        client = PynguinClient(configuration)
        client._started = True

        with (
            patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert,
            patch.object(client.master, "run", return_value=False),
        ):
            mock_convert.return_value = {"module_name": "test"}

            result = client.generate_tests()

        assert result == ReturnCode.SETUP_FAILED

    def test_generate_tests_exception(self):
        """Test test generation with exception."""
        configuration = MagicMock()
        client = PynguinClient(configuration)
        client._started = True

        with patch("pynguin.utils.configuration_writer.convert_config_to_dict") as mock_convert:
            mock_convert.side_effect = Exception("Test exception")

            result = client.generate_tests()

        assert result == ReturnCode.SETUP_FAILED

    def test_context_manager(self):
        """Test context manager functionality."""
        configuration = MagicMock()

        with (
            patch.object(PynguinClient, "start") as mock_start,
            patch.object(PynguinClient, "stop") as mock_stop,
            PynguinClient(configuration) as client,
        ):
            assert isinstance(client, PynguinClient)

        mock_start.assert_called_once()
        mock_stop.assert_called_once()


class TestRunPynguinWithMasterWorker:
    """Test cases for run_pynguin_with_master_worker function."""

    def test_run_pynguin_with_master_worker(self):
        """Test the convenience function."""
        configuration = MagicMock()

        with (
            patch.object(PynguinClient, "start") as mock_start,
            patch.object(PynguinClient, "stop") as mock_stop,
            patch.object(
                PynguinClient, "generate_tests", return_value=ReturnCode.OK
            ) as mock_generate,
        ):
            result = run_pynguin_with_master_worker(configuration)

        assert result == ReturnCode.OK
        mock_start.assert_called_once()
        mock_stop.assert_called_once()
        mock_generate.assert_called_once()

    def test_run_pynguin_with_master_worker_exception(self):
        """Test the convenience function with exception during context management."""
        configuration = MagicMock()

        with (
            patch.object(PynguinClient, "start", side_effect=Exception("Test error")),
            pytest.raises(Exception, match="Test error"),
        ):
            run_pynguin_with_master_worker(configuration)
