#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import re

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def bump(version: str) -> str:
    if VERSION_RE.match(version) is None:
        return "invalid"
    major = int(version.split(".")[0])
    if major >= 1:
        return "stable"
    return "pre-release"


def is_hex_color(text: str) -> bool:
    if re.fullmatch(r"#[0-9a-f]{6}", text):
        return True
    return False


def find_word(text: str) -> bool:
    match = VERSION_RE.search(text, 1)
    if not match:
        return False
    return True


class Matcher:
    def match(self, text: str) -> str | None:
        return None if text else "empty"


def not_a_regex(matcher: Matcher, text: str) -> bool:
    return matcher.match(text) is None


def check_later(text: str, flag: object) -> bool:
    match = VERSION_RE.match(text)
    if flag is None:
        flag = 0
    if match is None:
        return False
    return True
