#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the master process module."""

from unittest.mock import Mock

import pytest

import pynguin.configuration as config

from pynguin.master_worker.master import MasterProcess
from pynguin.master_worker.worker import WorkerReturnCode


@pytest.fixture
def sample_config():
    """Sample configuration."""
    return config.configuration


@pytest.fixture
def master_process(sample_config):
    """Create a MasterProcess instance for testing."""
    master_process = MasterProcess()
    master_process._configuration = sample_config
    return master_process


def test_master_process_init():
    """Test MasterProcess initialization."""
    master = MasterProcess()
    assert master._restart_count == 0
    assert master._current_task_start_time is None
    assert master._force_subprocess_mode is False
    assert master._configuration is None
    assert master._worker_process is None


def test_adjust_search_time_after_crash(master_process):
    """Test search time adjustment after worker crash."""
    master_process._configuration.stopping.maximum_search_time = 100

    master_process._adjust_search_time_after_crash(30.0)

    assert master_process._configuration.stopping.maximum_search_time == 70


def test_adjust_search_time_after_crash_minimum_zero(master_process):
    """Test search time adjustment doesn't go below zero."""
    master_process._configuration.stopping.maximum_search_time = 30

    master_process._adjust_search_time_after_crash(50.0)

    assert master_process._configuration.stopping.maximum_search_time == 0


def test_run_forces_subprocess_mode(master_process, sample_config):
    """Test run forces subprocess mode when enabled."""
    master_process._is_running = True
    master_process._force_subprocess_mode = True
    master_process._worker_process = Mock()
    master_process._worker_process.is_alive.return_value = True
    master_process._task_queue = Mock()

    master_process.start_pynguin(sample_config)

    assert master_process._configuration.subprocess is True
    assert master_process._configuration.subprocess_if_recommended is False


def test_get_result_exception(master_process):
    """Test result retrieval handles exceptions."""
    master_process._result_queue = Mock()
    master_process._result_queue.get.side_effect = Exception("Test error")

    result = master_process.get_result()

    assert result.worker_return_code == WorkerReturnCode.ERROR
    assert result.task_id == "unknown"
