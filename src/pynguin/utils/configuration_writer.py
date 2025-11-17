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


def _get_enum_classes() -> list[type[enum.Enum]]:
    """Get all enum classes from the config module."""
    return [
        getattr(config, name)
        for name in dir(config)
        if isinstance(getattr(config, name), type) and issubclass(getattr(config, name), enum.Enum)
    ]


def _get_dataclass_types() -> list[type]:
    """Get all dataclass types from the config module."""
    dataclass_types = []
    for name in dir(config):
        cls = getattr(config, name)
        if isinstance(cls, type) and dataclasses.is_dataclass(cls):
            dataclass_types.append(cls)
    return dataclass_types


def _try_construct_dataclass(obj_dict: dict[str, Any], dataclass_types: list[type]) -> Any | None:
    """Try to construct a dataclass from the given dictionary.

    Args:
        obj_dict: The dictionary to construct the dataclass from.
        dataclass_types: The list of dataclass types to try.

    Returns:
        The constructed dataclass instance or None if no suitable match found.
    """
    obj_keys = set(obj_dict.keys())

    # Sort by specificity (more fields = more specific match)
    sorted_types = sorted(
        dataclass_types,
        key=lambda cls: len([f for f in dataclasses.fields(cls) if f.name in obj_keys]),
        reverse=True,
    )

    for cls in sorted_types:
        field_names = {field.name for field in dataclasses.fields(cls)}
        # Check if at least one field matches to identify the correct dataclass
        if obj_keys & field_names:  # intersection - if any keys match
            # Process nested objects recursively
            processed = {k: read_config_from_dict(v) for k, v in obj_dict.items()}
            # Only pass fields that are defined in the dataclass
            filtered_kwargs = {k: v for k, v in processed.items() if k in field_names}
            return cls(**filtered_kwargs)
    return None


def _try_parse_enum(value: str, enum_classes: list[type[enum.Enum]]) -> Any:
    """Try to parse a string value as an enum.

    Args:
        value: The string value to parse.
        enum_classes: The list of enum classes to try.

    Returns:
        The parsed enum value or the original string if parsing fails.
    """
    for enum_cls in enum_classes:
        if value in enum_cls.__members__:
            return enum_cls(value)
    return value


def read_config_from_dict(obj: Any) -> Any:
    """Recursively reads a configuration from a dictionary.

    If this gets even more complex, one might consider using pydantic or dacite instead.

    Args:
        obj: The dictionary to read the configuration from.

    Returns:
        The read configuration.
    """
    enum_classes = _get_enum_classes()
    dataclass_types = _get_dataclass_types()

    if isinstance(obj, dict):
        # Try to construct a dataclass from the dictionary
        dataclass_instance = _try_construct_dataclass(obj, dataclass_types)
        if dataclass_instance is None:
            raise ValueError(f"Could not construct dataclass from dictionary: {obj}")

        return dataclass_instance

    if isinstance(obj, list):
        return [read_config_from_dict(item) for item in obj]

    if isinstance(obj, str):
        return _try_parse_enum(obj, enum_classes)

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
