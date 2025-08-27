#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Performs string grammar inference based on observed calls on strings."""

import re

import rstr

from pynguin.utils.orderedset import OrderedSet


_LOGGER = __import__("logging").getLogger(__name__)


def infer_regex_from_methods(called_str_methods: dict[str, OrderedSet[str]]) -> re.Pattern:  # noqa: C901
    """Infer a regex from the methods called on strings.

    TODO: Get rid of C901

    Args:
        called_str_methods: A mapping of method names to arguments.

    Returns:
        A regex pattern.
    """
    prefix: list[str] = []
    body: list[str] = []
    suffix: list[str] = []

    for method, args in called_str_methods.items():
        if method == "startswith":
            prefix.extend([f"^(?:{re.escape(a)})" for a in args])

        elif method == "endswith":
            suffix.extend([f"(?:{re.escape(a)})$" for a in args])

        elif method in {"split", "rsplit", "join"}:
            sep = re.escape(args[0]) if args else "_"
            body.append(f"(?:[A-Za-z0-9]+(?:{sep}[A-Za-z0-9]+)*)")

        elif method in {"partition", "rpartition"}:
            sep = re.escape(args[0])
            body.append(f"(?:.*?{sep}.*?)")

        elif method in {"find", "rfind", "index", "rindex"}:
            body.extend([f".*{re.escape(a)}.*" for a in args])

        elif method == "replace":
            old, new = args
            body.append(f"(?:.*{re.escape(old)}.*|.*{re.escape(new)}.*)")

        elif method in {"strip", "lstrip", "rstrip"}:
            body.append(r"\s*(.*?)\s*")

        elif method == "zfill":
            width = int(args[0])
            body.append(rf"0*\d{{1,{width}}}")

        elif method in {"center", "ljust", "rjust"}:
            width = int(args[0])
            body.append(rf".{{1,{width}}}")

        elif method == "removeprefix":
            prefix.extend([f"(?:{re.escape(a)})?" for a in args])

        elif method == "removesuffix":
            suffix.extend([f"(?:{re.escape(a)})?" for a in args])

        elif method == "translate":
            body.append("[A-Za-z0-9]+")

        elif method == "count":
            body.append(".*")

        elif method == "splitlines":
            body.append(r"(?:.*(?:\r?\n.*)*)")

        elif method == "format":
            body.append(".*")

    # Combine into a regex
    regex = "".join(prefix + body + suffix)

    # If absolutely nothing was produced, fall back to ".*" (matches anything)
    if not regex:
        regex = ".*"

    return re.compile(regex)


def generate_from_regex(regex: re.Pattern) -> str:
    """Generate a random string matching the given regex.

    Args:
        regex: The regex to match against.

    Returns:
        A random string matching the regex.
    """
    pattern = regex.pattern if isinstance(regex, re.Pattern) else regex
    try:
        return rstr.xeger(pattern)
    except Exception as ex:  # noqa: BLE001
        _LOGGER.warning("Could not generate string from regex: %s", ex)
        return ""
