#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for LLM type and subtype inference integration."""

from __future__ import annotations

import re

import pytest

from pynguin.analyses.string_subtype_inference import (
    AVAILABLE_GENERATORS,
    from_faker_generator,
    from_string,
    get_generator_for_subtype,
    get_subtype_for_generator,
    has_generator,
    to_faker_generator,
)
from pynguin.analyses.typesystem import (
    EmailString,
    IPv4String,
    IPv6String,
    StringSubtype,
)
from pynguin.large_language_model.prompts.type_and_subtype_inference_prompt import (
    TypeAndSubtypeInferencePrompt,
    get_type_and_subtype_inference_system_prompt,
)


@pytest.mark.parametrize(
    ("generator_name", "expected"),
    [
        ("email", True),
        ("ipv4", True),
        ("url", True),
        ("unknown", False),
    ],
)
def test_has_generator(generator_name: str, *, expected: bool) -> None:
    """Test checking if a generator is registered."""
    assert has_generator(generator_name) == expected


@pytest.mark.parametrize(
    ("generator_name", "expected_type"),
    [
        ("email", EmailString),
        ("ipv4", IPv4String),
    ],
)
def test_get_subtype_for_generator(generator_name: str, expected_type: type) -> None:
    """Test getting StringSubtype for a generator name."""
    subtype = get_subtype_for_generator(generator_name)
    assert subtype is not None
    assert isinstance(subtype, expected_type)


def test_get_subtype_for_unknown_generator() -> None:
    """Test getting StringSubtype for unknown generator returns None."""
    subtype = get_subtype_for_generator("unknown")
    assert subtype is None


@pytest.mark.parametrize(
    ("subtype", "expected_generator"),
    [
        (EmailString(), "email"),
        (IPv4String(), "ipv4"),
    ],
)
def test_get_generator_for_subtype(subtype: StringSubtype, expected_generator: str) -> None:
    """Test getting generator name for a StringSubtype."""
    generator = get_generator_for_subtype(subtype)
    assert generator == expected_generator


def test_available_generators() -> None:
    """Test the list of available generators."""
    generators = AVAILABLE_GENERATORS
    assert "email" in generators
    assert "ipv4" in generators
    assert "ipv6" in generators
    assert "color" in generators
    assert "csv" in generators
    assert "date" in generators
    assert "url" in generators


def test_round_trip_conversion() -> None:
    """Test converting generator -> subtype -> generator."""
    for generator_name in AVAILABLE_GENERATORS:
        subtype = get_subtype_for_generator(generator_name)
        assert subtype is not None
        recovered = get_generator_for_subtype(subtype)
        assert recovered == generator_name


@pytest.mark.parametrize(
    ("input_string", "expected_type"),
    [
        ("email", EmailString),
        ("ipv4", IPv4String),
    ],
)
def test_from_faker_generator(input_string: str, expected_type: type) -> None:
    """Test converting Faker generator names to StringSubtype."""
    subtype = from_string(input_string)
    assert isinstance(subtype, expected_type)


@pytest.mark.parametrize(
    ("pattern", "expected_pattern"),
    [
        ("^[0-9]{5}$", "^[0-9]{5}$"),
        ("^[A-Z]+$", "^[A-Z]+$"),
    ],
)
def test_from_custom_regex(pattern: str, expected_pattern: str) -> None:
    """Test converting custom regex patterns to StringSubtype."""
    subtype = from_string(pattern)
    assert isinstance(subtype, StringSubtype)
    assert subtype.regex.pattern == expected_pattern


def test_invalid_regex() -> None:
    """Test that invalid regex patterns return None."""
    subtype = from_string("^[invalid(regex")
    assert subtype is None


@pytest.mark.parametrize("input_value", [None, ""])
def test_none_input(input_value: str | None) -> None:
    """Test that None and empty strings return None."""
    assert from_string(input_value) is None


def test_from_faker_generator_method_email() -> None:
    """Test the dedicated method for Faker generators with email."""
    subtype = from_faker_generator("email")
    assert isinstance(subtype, EmailString)


def test_from_faker_generator_method_unknown() -> None:
    """Test the dedicated method for Faker generators with unknown generator."""
    subtype = from_faker_generator("unknown")
    assert subtype is None


@pytest.mark.parametrize(
    ("subtype", "expected_generator"),
    [
        (EmailString(), "email"),
        (IPv6String(), "ipv6"),
    ],
)
def test_to_faker_generator(subtype: StringSubtype, expected_generator: str) -> None:
    """Test converting StringSubtype back to generator name."""
    generator = to_faker_generator(subtype)
    assert generator == expected_generator


def test_unknown_subtype_to_generator() -> None:
    """Test that unknown subtypes return None."""
    # Create a custom StringSubtype not in the registry
    subtype = StringSubtype(re.compile(r"^custom$"))
    generator = to_faker_generator(subtype)
    assert generator is None


def test_prompt_includes_faker_generators() -> None:
    """Test that the prompt includes Faker generators."""

    def dummy_function(email: str, count: int) -> str:
        """A dummy function for testing."""
        return email * count

    prompt = TypeAndSubtypeInferencePrompt(dummy_function)
    user_prompt = prompt.build_user_prompt()

    # Check that the prompt mentions Faker generators
    assert "faker" in user_prompt.lower() or "email" in user_prompt.lower()
    assert "ipv4" in user_prompt or "Available Faker Generators" in user_prompt


def test_prompt_formatting() -> None:
    """Test basic prompt formatting."""

    def sample_func(name: str) -> None:
        """Sample function."""

    prompt = TypeAndSubtypeInferencePrompt(sample_func)
    user_prompt = prompt.build_user_prompt()

    # Check that key sections are present
    assert "Module Context" in user_prompt
    assert "Target Function" in user_prompt
    assert "Task" in user_prompt
    assert "JSON" in user_prompt


def test_system_prompt() -> None:
    """Test the system prompt for type and subtype inference."""
    system_prompt = get_type_and_subtype_inference_system_prompt()

    assert "type" in system_prompt.lower()
    assert "subtype" in system_prompt.lower()
    assert "json" in system_prompt.lower()
    assert "faker" in system_prompt.lower() or "generator" in system_prompt.lower()


def test_workflow_faker_generator() -> None:
    """Test complete workflow with Faker generator."""
    # Step 1: LLM returns a Faker generator name
    subtype_str = "email"

    # Step 2: Convert to StringSubtype
    subtype = from_string(subtype_str)
    assert isinstance(subtype, EmailString)

    # Step 3: Get generator back
    generator = get_generator_for_subtype(subtype)
    assert generator == "email"


def test_workflow_custom_regex() -> None:
    """Test complete workflow with custom regex."""
    # Step 1: LLM returns a custom regex
    subtype_str = "^[0-9]{3}-[0-9]{4}$"

    # Step 2: Convert to StringSubtype
    subtype = from_string(subtype_str)
    assert isinstance(subtype, StringSubtype)
    assert subtype.regex.pattern == subtype_str

    # Step 3: Try to get generator (should be None for custom)
    generator = get_generator_for_subtype(subtype)
    assert generator is None


def test_all_generators_in_prompt() -> None:
    """Test that all available generators are included in prompt."""

    def test_func(param1: str) -> None:
        pass

    prompt = TypeAndSubtypeInferencePrompt(test_func)
    user_prompt = prompt.build_user_prompt()

    for generator in AVAILABLE_GENERATORS:
        # Generator names should be mentioned in the prompt
        assert generator in user_prompt
