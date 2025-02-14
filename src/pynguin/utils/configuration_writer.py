#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility to write the current configuration to a TOML file."""

import enum
import pprint

from pathlib import Path
from typing import Any

import toml

import pynguin.configuration as config


def write_configuration():
    """Save the current configuration to a txt and a toml file."""
    if config.configuration.statistics_output.statistics_backend == config.StatisticsBackend.CSV:
        report_dir = Path(config.configuration.statistics_output.report_dir).resolve()

        # Write configuration to a TOML file
        toml_file = report_dir / "pynguin-config.toml"
        config_repr = convert_config_to_dict(config.configuration)
        with toml_file.open("w", encoding="utf-8") as f:
            toml.dump(config_repr, f)

        # Write configuration to a TXT file
        txt_file = report_dir / "pynguin-config.txt"
        txt_file.write_text(pprint.pformat(repr(config.configuration)))


def convert_config_to_dict(config_obj: object) -> dict[str, str | dict[str, str]]:
    """Converts a configuration object to a dictionary.

    Args:
        config_obj: The configuration object to convert.

    Returns:
        A dictionary representation of the configuration object.
    """
    return _convert_config_to_dict(config_obj, set())


def _convert_config_to_dict(config_obj: object, seen: set[int]) -> Any:
    """Recursively converts a configuration object to a dictionary, avoiding cycles.

    Args:
        config_obj: The configuration object to convert.
        seen: A set to track visited objects and prevent infinite recursion.

    Returns:
        A dictionary representation of the configuration object.
    """
    obj_id = id(config_obj)
    if obj_id in seen:
        return None  # Prevent infinite recursion

    # Mark object as seen
    seen.add(obj_id)

    if isinstance(config_obj, dict):
        converted_dict = {}
        for k, v in config_obj.items():
            if k == "_value_":  # Handle enum case
                return _convert_config_to_dict(v, seen)  # Return value directly
            converted_dict[k] = _convert_config_to_dict(v, seen)
        return converted_dict
    if isinstance(config_obj, list):
        return [_convert_config_to_dict(v, seen) for v in config_obj]
    if isinstance(config_obj, Path):
        return str(config_obj)  # Convert Path to string
    if isinstance(config_obj, enum.Enum):
        return config_obj.value  # Convert Enum to its string value
    if hasattr(config_obj, "__dict__"):
        return {
            k: _convert_config_to_dict(v, seen)
            for k, v in vars(config_obj).items()
            if not callable(v) and not k.startswith("__")
        }
    return config_obj  # Return primitive types as-is
