#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility to write the current configuration to a TOML file."""

import dataclasses
import enum
import json
import logging
import pprint

from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import toml

import pynguin.configuration as config


PYNGUIN_CLI_PARAMS = "pynguin-cli-params.txt"
PYNGUIN_CONFIG_TXT = "pynguin-config.txt"
PYNGUIN_CONFIG_TOML = "pynguin-config.toml"


def write_configuration():
    """Save the current configuration to a txt and a toml file."""
    if config.configuration.statistics_output.statistics_backend == config.StatisticsBackend.CSV:
        report_dir = Path(config.configuration.statistics_output.report_dir).resolve()

        report_dir.mkdir(parents=True, exist_ok=True)

        # Write configuration to a TOML file
        toml_file = report_dir / PYNGUIN_CONFIG_TOML
        config_repr = convert_config_to_dict(config.configuration)
        with toml_file.open("w", encoding="utf-8") as f:
            toml.dump(config_repr, f)

        # Write configuration to a TXT file
        txt_file = report_dir / PYNGUIN_CONFIG_TXT
        txt_file.write_text(pprint.pformat(repr(config.configuration)))

        # Write CLI options to a TXT file
        cli_file = report_dir / PYNGUIN_CLI_PARAMS
        cli_file.write_text("\n".join(extract_parameter_list_from_config()))


def convert_config_to_dict(config_obj: object) -> dict[str, str | dict[str, str]]:
    """Converts a configuration object to a dictionary.

    Other than the built-in `dataclasses.asdict`, this function converts enum values
    to their string representation, which is required for the TOML format.

    Args:
        config_obj: The configuration object to convert.

    Returns:
        A dictionary representation of the configuration object.
    """
    return json.loads(json.dumps(config_obj, default=lambda o: o.__dict__))


def keys_contain(obj_keys, required_keys):
    """Checks if obj_keys contains at least all required keys."""
    return any(key in obj_keys for key in required_keys)


def read_config_from_dict(obj: Any) -> Any:
    """Recursively reads a configuration from a dictionary."""
    enum_classes = [
        config.Algorithm,
        config.AssertionGenerator,
        config.MutationStrategy,
        config.StatisticsBackend,
        config.ExportStrategy,
        config.CoverageMetric,
        config.MinimizationStrategy,
        config.MinimizationDirection,
        config.TypeInferenceStrategy,
        config.SubtypeInferenceStrategy,
        config.Selection,
    ]

    class_map = [
        (["project_path", "module_name", "test_case_output"], config.Configuration),
        (["output_path", "export_strategy", "minimization"], config.TestCaseOutputConfiguration),
        (
            ["test_case_minimization_strategy", "test_case_minimization_direction"],
            config.Minimization,
        ),
        (["report_dir", "statistics_backend"], config.StatisticsOutputConfiguration),
        (["maximum_search_time"], config.StoppingConfiguration),
        (["api_key", "model_name"], config.LLMConfiguration),
        (["seed", "constant_seeding"], config.SeedingConfiguration),
        (["type_inference_strategy"], config.TypeInferenceConfiguration),
        (["ml_testing_enabled"], config.PynguinMLConfiguration),
        (["max_recursion", "max_delta"], config.TestCreationConfiguration),
        (
            [
                "min_initial_tests",
                "max_initial_tests",
                "population",
                "chromosome_length",
                "chop_max_length",
                "elite",
                "crossover_rate",
                "test_insertion_probability",
                "test_delete_probability",
                "test_change_probability",
                "test_insert_probability",
                "statement_insertion_probability",
                "random_perturbation",
                "change_parameter_probability",
                "tournament_size",
                "rank_bias",
                "selection",
            ],
            config.SearchAlgorithmConfiguration,
        ),
        (
            ["initial_config", "focused_config", "exploitation_starts_at_percent"],
            config.MIOConfiguration,
        ),
        (
            [
                "number_of_tests_per_target",
                "random_test_or_from_archive_probability",
                "number_of_mutations",
            ],
            config.MIOPhaseConfiguration,
        ),
        (["max_sequence_length", "max_sequences_combined"], config.RandomConfiguration),
        (
            ["only_cover", "no_cover"],
            config.ToCoverConfiguration,
        ),
        (["local_search", "local_search_probability"], config.LocalSearchConfiguration),
    ]

    if isinstance(obj, dict):
        obj_keys = set(obj.keys())
        for required_keys, cls in class_map:
            if keys_contain(obj_keys, required_keys):
                processed = {k: read_config_from_dict(v) for k, v in obj.items()}
                return cls(**processed)
        # fallback generic object
        return SimpleNamespace(**{k: read_config_from_dict(v) for k, v in obj.items()})

    if isinstance(obj, list):
        return [read_config_from_dict(item) for item in obj]

    if isinstance(obj, str):
        for enum_cls in enum_classes:
            try:
                return enum_cls(obj)
            except (ValueError, TypeError):  # noqa: PERF203 # TODO
                continue
        return obj

    return obj


def _format_value(value: Any) -> str:
    """Formats a configuration value for CLI output.

    Args:
        value: The configuration value to format.

    Returns:
        The formatted configuration value as a string.
    """
    if isinstance(value, list):
        return "\n".join(_format_value(v) for v in value)
    elif isinstance(value, enum.Enum):  # noqa: RET505
        return value.name
    else:
        return str(value)


def _create_params_from_config_dict(cfg_dict: dict[str, Any], prefix: str = "") -> Iterable[str]:
    """Recursively creates CLI parameters from a configuration dictionary.

    Args:
        cfg_dict: The configuration dictionary.
        prefix: The prefix for nested keys. Defaults to an empty string.

    Yields:
        CLI parameters as strings.
    """
    for key, value in cfg_dict.items():
        if isinstance(value, (str, list)) and not value:
            continue

        key_name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _create_params_from_config_dict(value, prefix=key_name)
        else:
            yield f"--{key_name}\n{_format_value(value)}"


def _extract_verbosity_params(verbosity: bool) -> Iterable[str]:  # noqa: FBT001
    """Extract the verbosity level from the logging configuration.

    Args:
        verbosity: Whether to include verbosity parameters in the output.

    Yields:
        CLI parameters representing the verbosity level, or an empty iterator.
    """
    if not verbosity:
        return

    logging_level = logging.getLogger().getEffectiveLevel()
    if logging_level == logging.DEBUG:
        verbosity_level = 2
    elif logging_level == logging.INFO:
        verbosity_level = 1
    else:
        return

    # Set number of 'v's to the verbosity level
    yield f"-{'v' * verbosity_level}"


def extract_parameter_list_from_config(*, verbosity: bool = True) -> list[str]:
    """Extracts the CLI parameter list from the current configuration.

    Allows to use the dumped configuration as input for the CLI again. Pynguin's CLI parser already
    supports the loading of configuration options from a file, as specified in the `argparse`
    documentation.

    Implementation detail: the result is sorted to make the output deterministic.

    Args:
        verbosity: Whether to include verbosity parameters in the output.

    Returns:
        A sorted list of CLI parameters.
    """
    return sorted((
        *_extract_verbosity_params(verbosity),
        *_create_params_from_config_dict(dataclasses.asdict(config.configuration)),
    ))
