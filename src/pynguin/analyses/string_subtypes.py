#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Performs string grammar inference based on observed calls on strings."""

import logging
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

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


class _BoundedXeger(rstr.Xeger):
    """A string generator that repeats unbounded quantifiers only a few times."""

    def __init__(self, rng: Any, repeat_limit: int) -> None:
        super().__init__(rng)
        self._repeat_limit = repeat_limit

    def _handle_repeat(self, start_range: int, end_range: int, value: str) -> str:
        return super()._handle_repeat(
            start_range, min(end_range, start_range + self._repeat_limit), value
        )


# Strings for seeding should be short, such that mutations can still change them.
SHORT_STRING_GENERATOR: rstr.Rstr = _BoundedXeger(RNG, repeat_limit=3)


def _minimal_char_key(char: str) -> tuple[bool, bool, bool, str]:
    # Prefer alphanumeric characters, then other visible ones, then " ", then the
    # remaining whitespace, e.g., "0" for ".", "!" for r"\W" and " " for r"\s".
    return (not char.isalnum(), char.isspace(), char != " ", char)


class _FirstChoiceRandom:
    """A stand-in for a random generator that always makes the smallest choice.

    Characters are chosen by a fixed order instead of by position, because rstr builds
    some candidate lists from sets (e.g., for negated classes), whose order depends on
    the hash seed.
    """

    @staticmethod
    def choice(population: Any) -> Any:
        if all(isinstance(item, str) and len(item) == 1 for item in population):
            return min(population, key=_minimal_char_key)
        return population[0]

    @staticmethod
    def randint(low: int, high: int) -> int:  # noqa: ARG004
        return low

    @staticmethod
    def shuffle(population: Any) -> None:  # noqa: ARG004
        # rstr shuffles the characters of generated strings, e.g., for ".".
        return


# Generates the shortest string with the first character of each class, e.g., "0.0.0"
# for r"\d+\.\d+\.\d+", which is a boundary value.
MINIMAL_STRING_GENERATOR: rstr.Rstr = rstr.Xeger(_FirstChoiceRandom())  # type: ignore[arg-type]


def generate_from_regex(
    regex: re.Pattern | str, *, short: bool = False, minimal: bool = False
) -> str:
    """Generate a random string matching the given regex.

    Args:
        regex: The regex to match against.
        short: Whether to repeat unbounded quantifiers at most a few times.
        minimal: Whether to generate the shortest string, using the first character
            of each character class (deterministic).

    Returns:
        A random string matching the regex.
    """
    pattern = regex.pattern if isinstance(regex, re.Pattern) else regex
    if minimal:
        generator = MINIMAL_STRING_GENERATOR
    elif short:
        generator = SHORT_STRING_GENERATOR
    else:
        generator = STRING_GENERATOR
    try:
        return generator.xeger(pattern)
    except Exception as ex:  # noqa: BLE001
        _LOGGER.warning("Could not generate string from regex: %s", ex)
        return ""
