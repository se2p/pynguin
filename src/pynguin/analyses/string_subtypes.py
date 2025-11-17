#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Performs string grammar inference based on observed calls on strings."""

import logging
import re
from collections.abc import Callable, Iterable, Mapping

import rstr

from pynguin.utils.randomness import RNG

_LOGGER = logging.getLogger(__name__)

STRING_GENERATOR: rstr.Rstr = rstr.Xeger(RNG)


class RegexBuilder:
    """Helper for constructing regex patterns based on string method calls."""

    def __init__(self) -> None:
        """Initialize the builder."""
        self.prefix: list[str] = []
        self.body: list[str] = []
        self.suffix: list[str] = []

    def handle_startswith(self, *args: str) -> None:
        """Handle the startswith method."""
        self.prefix.extend([f"^(?:{re.escape(a)})" for a in args])

    def handle_endswith(self, *args: str) -> None:
        """Handle the endswith method."""
        self.suffix.extend([f"(?:{re.escape(a)})$" for a in args])

    def handle_splitlike(self, *args: str) -> None:
        """Handle split, rsplit, and join."""
        sep = re.escape(args[0]) if args else "_"
        self.body.append(f"(?:[A-Za-z0-9]+(?:{sep}[A-Za-z0-9]+)*)")

    def handle_partition(self, *args: str) -> None:
        """Handle partition and rpartition."""
        if args:
            sep = re.escape(args[0])
            self.body.append(f"(?:.*?{sep}.*?)")

    def handle_findlike(self, *args: str) -> None:
        """Handle find, rfind, index, and rindex."""
        self.body.extend([f".*{re.escape(a)}.*" for a in args])

    def handle_replace(self, *args: str) -> None:
        """Handle replace."""
        if len(args) >= 2:
            old, new = args[:2]
            self.body.append(f"(?:.*{re.escape(old)}.*|.*{re.escape(new)}.*)")

    def handle_strip(self, *args: str) -> None:
        """Handle strip, lstrip, and rstrip."""
        self.body.append(r"\s*(.*?)\s*")

    def handle_zfill(self, *args: str) -> None:
        """Handle zfill."""
        if args:
            width = int(args[0])
            self.body.append(rf"0*\d{{1,{width}}}")

    def handle_justify(self, *args: str) -> None:
        """Handle center, ljust, and rjust."""
        if args:
            width = int(args[0])
            self.body.append(rf".{{1,{width}}}")

    def handle_removeprefix(self, *args: str) -> None:
        """Handle removeprefix."""
        self.prefix.extend([f"(?:{re.escape(a)})?" for a in args])

    def handle_removesuffix(self, *args: str) -> None:
        """Handle removesuffix."""
        self.suffix.extend([f"(?:{re.escape(a)})?" for a in args])

    def handle_translate(self, *args: str) -> None:
        """Handle translate."""
        self.body.append("[A-Za-z0-9]+")

    def handle_count(self, *args: str) -> None:
        """Handle count."""
        self.body.append(".*")

    def handle_splitlines(self, *args: str) -> None:
        """Handle splitlines."""
        self.body.append(r"(?:.*(?:\r?\n.*)*)")

    def handle_format(self, *args: str) -> None:
        """Handle format."""
        self.body.append(".*")

    def build(self) -> str:
        """Combine collected fragments into a regex string."""
        return "".join(self.prefix + self.body + self.suffix) or ".*"


DISPATCH: dict[str, Callable] = {
    "startswith": RegexBuilder.handle_startswith,
    "endswith": RegexBuilder.handle_endswith,
    "split": RegexBuilder.handle_splitlike,
    "rsplit": RegexBuilder.handle_splitlike,
    "join": RegexBuilder.handle_splitlike,
    "partition": RegexBuilder.handle_partition,
    "rpartition": RegexBuilder.handle_partition,
    "find": RegexBuilder.handle_findlike,
    "rfind": RegexBuilder.handle_findlike,
    "index": RegexBuilder.handle_findlike,
    "rindex": RegexBuilder.handle_findlike,
    "replace": RegexBuilder.handle_replace,
    "strip": RegexBuilder.handle_strip,
    "lstrip": RegexBuilder.handle_strip,
    "rstrip": RegexBuilder.handle_strip,
    "zfill": RegexBuilder.handle_zfill,
    "center": RegexBuilder.handle_justify,
    "ljust": RegexBuilder.handle_justify,
    "rjust": RegexBuilder.handle_justify,
    "removeprefix": RegexBuilder.handle_removeprefix,
    "removesuffix": RegexBuilder.handle_removesuffix,
    "translate": RegexBuilder.handle_translate,
    "count": RegexBuilder.handle_count,
    "splitlines": RegexBuilder.handle_splitlines,
    "format": RegexBuilder.handle_format,
}


def infer_regex_from_methods(called_str_methods: Mapping[str, Iterable[str]]) -> re.Pattern:
    """Infer a regex from the methods called on strings.

    Args:
        called_str_methods: A mapping of method names to arguments.

    Returns:
        A compiled regex pattern.
    """
    builder = RegexBuilder()
    for method, args in called_str_methods.items():
        handler = DISPATCH.get(method)
        if handler:
            handler(builder, *args)

    return re.compile(builder.build())


def generate_from_regex(regex: re.Pattern) -> str:
    """Generate a random string matching the given regex.

    Args:
        regex: The regex to match against.

    Returns:
        A random string matching the regex.
    """
    pattern = regex.pattern if isinstance(regex, re.Pattern) else regex
    try:
        return STRING_GENERATOR.xeger(pattern)
    except Exception as ex:  # noqa: BLE001
        _LOGGER.warning("Could not generate string from regex: %s", ex)
        return ""
