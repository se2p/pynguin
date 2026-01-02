#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the StringSubtype implementations in the typesystem.

These tests verify that each concrete StringSubtype exposes a regex
that accepts a representative valid example and rejects a representative
invalid example where applicable.
"""

import re

import pytest

from pynguin.analyses import typesystem


@pytest.mark.parametrize(
    "cls,valid,invalid",
    [
        (typesystem.NumericString, "123", "abc"),
        (typesystem.EmailString, "name@example.com", "not-an-email"),
        (typesystem.HexadecimalString, "0x1A3F", "0x1G3Z"),
        (typesystem.ISOColorString, "#FF00FF", "#GGHHII"),
        (typesystem.UUIDString, "123e4567-e89b-12d3-a456-426614174000", "12345"),
        (typesystem.ISODateString, "2023-10-05", "05-10-2023"),
        (typesystem.ISOTimeString, "14:30:00", "14:30"),
        (typesystem.CSVString, "a,b,c", "a,b,"),
        (typesystem.URLString, "http://example.com", "not-a-url"),
        (typesystem.IPv4String, "192.168.0.1", "999.999.999.999"),
        (typesystem.IPv6String, "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "::gggg"),
        (typesystem.PhoneNumberString, "+1-800-555-1234", "phone#"),
        (
            typesystem.SHA256String,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "deadbeef",
        ),
    ],
)
def test_string_subtype_regex_matches_and_rejects(cls, valid, invalid):
    instance = cls()
    # The base StringSubtype stores a compiled regex in `regex` attribute.
    assert hasattr(instance, "regex"), f"{cls.__name__} has no attribute 'regex'"
    regex = instance.regex
    assert isinstance(regex, re.Pattern)

    # valid should be accepted by the regex (fullmatch if the pattern is anchored)
    # Use search for flexibility in case implementations use search patterns.
    assert regex.search(valid), f"{cls.__name__} failed to match valid example: {valid}"

    # invalid should not be accepted
    assert not regex.search(invalid), (
        f"{cls.__name__} incorrectly matched invalid example: {invalid}"
    )
