#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility to write the current configuration to a TOML file."""

import dataclasses
import json
import logging
import pprint

from pathlib import Path
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


def extract_parameter_list_from_config(*, verbosity: bool = True) -> list[str]:
    """Extracts the CLI parameter list from the current configuration.

    Allows to use the dumped configuration as input for the CLI again.  Pynguin's CLI parser already
    supports the loading of configuration options from a file, as specified in the `argparse`
    documentation.

    Implementation detail: the result is sorted to make the output deterministic.

    Args:
        verbosity: Whether to include verbosity parameters in the output.

    Returns:
        A sorted list of CLI parameters.
    """

    def format_parameter(k: str, v: Any) -> str:
        if isinstance(v, list):
            values = "\n".join(v)
            return f"--{k}\n{values}"
        return f"--{k}\n{v}"

    parameter_list: list[str] = []
    cfg_dict = dataclasses.asdict(config.configuration)

    for key, value in cfg_dict.items():
        if isinstance(value, (str, list)) and not value:
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, (str, list)) and not sub_value:
                    continue
                if isinstance(sub_value, dict):
                    for sub_sub_key, sub_sub_value in sub_value.items():
                        parameter_list.append(
                            format_parameter(f"{sub_key}.{sub_sub_key}", sub_sub_value)
                        )
                else:
                    parameter_list.append(format_parameter(f"{sub_key}", sub_value))
        else:
            parameter_list.append(format_parameter(key, value))

    verbosity_params = _extract_verbosity_params() if verbosity else []
    return sorted(parameter_list + verbosity_params)


def _extract_verbosity_params() -> list[str]:
    """Extract the verbosity level from the logging configuration."""
    logging_level = logging.getLogger().getEffectiveLevel()
    if logging_level == logging.DEBUG:
        verbosity = 2
    elif logging_level == logging.INFO:
        verbosity = 1
    else:
        verbosity = 0

    # set number of 'v's to the verbosity level
    verbosity_params = []
    if verbosity > 0:
        verbosity_params.append(f"-{'v' * verbosity}")

    return verbosity_params
