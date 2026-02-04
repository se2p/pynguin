#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility for converting LLM subtype inference to StringSubtype instances."""

from __future__ import annotations

import logging
import re

from pynguin.analyses.typesystem import (
    CSVString,
    EmailString,
    IPv4String,
    IPv6String,
    ISOColorString,
    ISODateString,
    StringSubtype,
    URLString,
)

_LOGGER = logging.getLogger(__name__)

# Mapping of Faker method names to corresponding StringSubtype classes
_GENERATOR_TO_SUBTYPE: dict[str, type[StringSubtype]] = {
    "email": EmailString,
    "ipv4": IPv4String,
    "ipv6": IPv6String,
    "color": ISOColorString,
    "csv": CSVString,
    "date": ISODateString,
    "url": URLString,
}

# Mapping of StringSubtype classes to Faker method names
_SUBTYPE_TO_GENERATOR: dict[type[StringSubtype], str] = {
    v: k for k, v in _GENERATOR_TO_SUBTYPE.items()
}

AVAILABLE_GENERATORS: list[str] = list(_GENERATOR_TO_SUBTYPE.keys())


def get_subtype_for_generator(generator_name: str) -> StringSubtype | None:
    """Get a StringSubtype instance for a given Faker generator name."""
    subtype_class = _GENERATOR_TO_SUBTYPE.get(generator_name)
    # All registered StringSubtype subclasses have no-arg constructors
    return subtype_class() if subtype_class else None  # type: ignore[call-arg]


def get_generator_for_subtype(subtype: StringSubtype) -> str | None:
    """Get the Faker generator name for a given StringSubtype instance."""
    return _SUBTYPE_TO_GENERATOR.get(type(subtype))


def has_generator(generator_name: str) -> bool:
    """Check if a generator name is registered."""
    return generator_name in _GENERATOR_TO_SUBTYPE


def from_string(subtype_str: str) -> StringSubtype | None:
    """Convert a subtype string into a StringSubtype instance.

    The subtype string can be either:
    1. A Faker generator name (e.g., "email", "ipv4", "url")
    2. A custom regex pattern (e.g., "^[a-z]+$")

    Args:
        subtype_str: The subtype string from LLM inference

    Returns:
        A StringSubtype instance, or None if conversion fails
    """
    if not subtype_str or not isinstance(subtype_str, str):
        return None

    # First, try to match against known Faker generators
    if has_generator(subtype_str):
        subtype = get_subtype_for_generator(subtype_str)
        if subtype:
            return subtype

    # Otherwise, try to parse as a custom regex pattern
    try:
        # Validate that it's a valid regex by attempting to compile it
        compiled_regex = re.compile(subtype_str)
        return StringSubtype(compiled_regex)
    except re.error as e:
        _LOGGER.warning(
            "Failed to parse subtype string '%s' as regex pattern: %s",
            subtype_str,
            e,
        )
        return None


def from_faker_generator(generator_name: str) -> StringSubtype | None:
    """Create a StringSubtype from a Faker generator name.

    Args:
        generator_name: The name of the Faker generator

    Returns:
        A StringSubtype instance, or None if the generator is not registered
    """
    return get_subtype_for_generator(generator_name)


def to_faker_generator(subtype: StringSubtype) -> str | None:
    """Get the Faker generator name for a StringSubtype, if available.

    Args:
        subtype: The StringSubtype instance

    Returns:
        The Faker generator name, or None if no mapping exists
    """
    return get_generator_for_subtype(subtype)
