#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import argparse
import importlib
import logging
import os
import re

from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock
from unittest.mock import call

import pytest

import pynguin.configuration as config

from pynguin.cli import _DANGER_ENV  # noqa: PLC2701
from pynguin.cli import _create_argument_parser  # noqa: PLC2701
from pynguin.cli import _expand_arguments_if_necessary  # noqa: PLC2701
from pynguin.cli import _setup_logging  # noqa: PLC2701
from pynguin.cli import main
from pynguin.generator import ReturnCode


def test_main_empty_argv():
    with mock.patch("pynguin.cli.run_pynguin") as generator_mock:  # noqa: SIM117
        with mock.patch("pynguin.cli._create_argument_parser") as parser_mock:
            with mock.patch("pynguin.cli._setup_logging"):
                with mock.patch("pynguin.cli._setup_output_path"):
                    with mock.patch.dict(os.environ, {_DANGER_ENV: "foobar"}):
                        generator_mock.return_value = ReturnCode.OK
                        parser = MagicMock()
                        parser_mock.return_value = parser
                        main()
                        assert len(parser.parse_args.call_args[0][0]) > 0


def test_main_with_argv():
    with mock.patch("pynguin.cli.run_pynguin") as generator_mock:  # noqa: SIM117
        with mock.patch("pynguin.cli._create_argument_parser") as parser_mock:
            with mock.patch("pynguin.cli._setup_logging"):
                with mock.patch("pynguin.cli._setup_output_path"):
                    with mock.patch.dict(os.environ, {_DANGER_ENV: "foobar"}):
                        generator_mock.return_value = ReturnCode.OK
                        parser = MagicMock()
                        parser_mock.return_value = parser
                        args = ["foo", "--help"]
                        main(args)
                        assert parser.parse_args.call_args == call(args[1:])


def test_main_no_env_marker():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert main([]) == -1


def test__create_argument_parser():
    parser = _create_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test__setup_logging_single_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(verbosity=1, no_rich=False, log_file=None)
    logger = logging.getLogger("")
    assert len(logger.handlers) == 1
    assert logger.level == logging.INFO
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_double_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(verbosity=2, no_rich=False, log_file=None)
    logger = logging.getLogger("")
    assert len(logger.handlers) == 1
    assert logger.level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_log_file(tmp_path: Path):
    log_file = tmp_path / "pynguin.log"
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(verbosity=1, no_rich=False, log_file=log_file)
    logger = logging.getLogger("")
    assert len(logger.handlers) == 1
    logger.info("Test entry")
    assert re.match(
        r"\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]\s\[INFO\]\(.+:"
        r"test__setup_logging_log_file:[0-9]+\):\sTest\sentry",
        log_file.read_text(),
    )
    logging.shutdown()
    importlib.reload(logging)


@pytest.mark.parametrize(
    "arguments, expected",
    [
        pytest.param(["--foo", "bar", "--bar", "foo"], ["--foo", "bar", "--bar", "foo"]),
        pytest.param(
            ["--foo", "bar", "--output_variables", "foo,bar,baz", "--bar", "foo"],
            ["--foo", "bar", "--output_variables", "foo", "bar", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--output_variables", "baz", "--bar", "foo"],
            ["--foo", "bar", "--output_variables", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--output-variables", "foo,bar,baz", "--bar", "foo"],
            ["--foo", "bar", "--output-variables", "foo", "bar", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--output-variables", "baz", "--bar", "foo"],
            ["--foo", "bar", "--output-variables", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--coverage_metrics", "foo,bar,baz", "--bar", "foo"],
            ["--foo", "bar", "--coverage_metrics", "foo", "bar", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--coverage_metrics", "baz", "--bar", "foo"],
            ["--foo", "bar", "--coverage_metrics", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--coverage-metrics", "foo,bar,baz", "--bar", "foo"],
            ["--foo", "bar", "--coverage-metrics", "foo", "bar", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--coverage-metrics", "baz", "--bar", "foo"],
            ["--foo", "bar", "--coverage-metrics", "baz", "--bar", "foo"],
        ),
        pytest.param(
            [
                "--foo",
                "bar",
                "--coverage_metrics",
                "foo,bar,baz",
                "--output_variables",
                "foo,bar,baz",
                "--bar",
                "foo",
            ],
            [
                "--foo",
                "bar",
                "--coverage_metrics",
                "foo",
                "bar",
                "baz",
                "--output_variables",
                "foo",
                "bar",
                "baz",
                "--bar",
                "foo",
            ],
        ),
        pytest.param(
            [
                "--foo",
                "bar",
                "--output_variables",
                "foo,bar,baz",
                "--coverage_metrics",
                "foo,bar,baz",
                "--bar",
                "foo",
            ],
            [
                "--foo",
                "bar",
                "--output_variables",
                "foo",
                "bar",
                "baz",
                "--coverage_metrics",
                "foo",
                "bar",
                "baz",
                "--bar",
                "foo",
            ],
        ),
        pytest.param(
            [
                "--foo",
                "bar",
                "--coverage-metrics",
                "foo,bar,baz",
                "--output-variables",
                "foo,bar,baz",
                "--bar",
                "foo",
            ],
            [
                "--foo",
                "bar",
                "--coverage-metrics",
                "foo",
                "bar",
                "baz",
                "--output-variables",
                "foo",
                "bar",
                "baz",
                "--bar",
                "foo",
            ],
        ),
        pytest.param(
            [
                "--foo",
                "bar",
                "--output-variables",
                "foo,bar,baz",
                "--coverage-metrics",
                "foo,bar,baz",
                "--bar",
                "foo",
            ],
            [
                "--foo",
                "bar",
                "--output-variables",
                "foo",
                "bar",
                "baz",
                "--coverage-metrics",
                "foo",
                "bar",
                "baz",
                "--bar",
                "foo",
            ],
        ),
    ],
)
def test__expand_arguments_if_necessary(arguments, expected):
    result = _expand_arguments_if_necessary(arguments)
    assert result == expected


def test_load_configuration_from_file(tmp_path):
    config_file = Path().absolute()
    if config_file.name != "tests":
        config_file /= "tests"  # pragma: no cover
    config_file = config_file / "fixtures" / "test.conf"
    parser = _create_argument_parser()
    parsed = parser.parse_args([
        f"@{config_file}",
        "--module_name",
        "hurz",
        "--project_path",
        str(tmp_path),
        "--output_path",
        str(tmp_path),
        "--maximum_search_time",
        "50",
    ])
    configuration = parsed.config
    expected = config.Configuration(
        algorithm=config.Algorithm.MOSA,
        module_name="hurz",
        project_path=str(tmp_path),
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
    )
    expected.seeding.seed = 42
    expected.stopping.maximum_search_time = 50
    expected.statistics_output.configuration_id = "merge checker"
    assert configuration == expected


@pytest.mark.parametrize(
    "input_value, expected_bool, expected_float",
    [
        ("True", True, 1),
        ("False", False, 0),
        ("0", False, 0),
        ("1", True, 1),
    ],
)
def test_parse_arguments_type_tracing_bool(tmp_path, input_value, expected_bool, expected_float):
    parser = _create_argument_parser()
    parsed = parser.parse_args([
        "--module_name",
        "hurz",
        "--project_path",
        str(tmp_path),
        "--output_path",
        str(tmp_path),
        "--type-tracing",
        input_value,
    ])
    assert parsed.config.type_inference.type_tracing == expected_bool
    assert parsed.config.type_inference.type_tracing == expected_float


def test_parse_arguments_type_tracing_float(tmp_path):
    parser = _create_argument_parser()
    parsed = parser.parse_args([
        "--module_name",
        "hurz",
        "--project_path",
        str(tmp_path),
        "--output_path",
        str(tmp_path),
        "--type-tracing",
        "0.1",
    ])
    assert parsed.config.type_inference.type_tracing == 0.1
