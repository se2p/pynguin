#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for handling compiled C-extension SUTs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

import pynguin.configuration as config
from pynguin.analyses.module import is_file_loader_module
from pynguin.generator import ReturnCode, run_pynguin, set_configuration

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def base_config(tmp_path: Path) -> config.Configuration:
    """Provides a base configuration for running Pynguin.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        A Configuration object.
    """
    conf = config.Configuration(
        algorithm=config.Algorithm.RANDOM,
        project_path=str(tmp_path),
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path / "out")),
        module_name="",
    )
    conf.stopping.maximum_search_time = 5
    return conf


@pytest.mark.parametrize("module_name", ["_json", "math"])
def test_run_pynguin_compiled_c_extension_returns_setup_failed(
    base_config: config.Configuration,
    caplog: pytest.LogCaptureFixture,
    module_name: str,
) -> None:
    """Verifies that running Pynguin on a C-extension SUT fails cleanly during setup.

    Args:
        base_config: Fixture providing test configuration.
        caplog: Fixture capturing log messages.
        module_name: Name of the C-extension module under test.
    """
    base_config.module_name = module_name
    set_configuration(base_config)

    with caplog.at_level(logging.ERROR):
        result = run_pynguin()

    assert result == ReturnCode.SETUP_FAILED
    expected_message = (
        f"Module '{module_name}' is a compiled C-extension or non-FileLoader module. "
        "Compiled C-extension modules cannot be instrumented."
    )
    assert any(expected_message in record.message for record in caplog.records)


def test_run_pynguin_blib2to3_compiled_c_extension(
    base_config: config.Configuration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verifies graceful exit for blib2to3.pgen2.literals if available.

    Args:
        base_config: Fixture providing test configuration.
        caplog: Fixture capturing log messages.
    """
    mod = pytest.importorskip("blib2to3.pgen2.literals")
    if is_file_loader_module(mod):
        pytest.skip("blib2to3.pgen2.literals is not compiled as a C-extension in this environment")
    module_name = "blib2to3.pgen2.literals"
    base_config.module_name = module_name
    set_configuration(base_config)

    with caplog.at_level(logging.ERROR):
        result = run_pynguin()

    assert result == ReturnCode.SETUP_FAILED
    expected_message = (
        f"Module '{module_name}' is a compiled C-extension or non-FileLoader module. "
        "Compiled C-extension modules cannot be instrumented."
    )
    assert any(expected_message in record.message for record in caplog.records)
