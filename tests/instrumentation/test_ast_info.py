#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib.util
from pathlib import Path

import pytest

from pynguin.configuration import ToCoverConfiguration
from pynguin.instrumentation.transformer import ModuleAstInfo


def get_module_path(module_name: str, extension: str = ".py") -> str:
    """Return absolute path to a module.

    It requires the module to be in a package and it does not work for __init__ modules.

    Args:
        module_name: Dotted module path.
        extension: File extension.

    Returns:
        Absolute path to the module file.
    """
    package_name, *submodule_names = module_name.split(".")
    package_spec = importlib.util.find_spec(package_name)
    assert package_spec is not None
    assert package_spec.origin is not None
    return str(Path(package_spec.origin).parent.joinpath(*submodule_names).with_suffix(extension))


@pytest.mark.parametrize(
    "scope_line, expected_should_be_covered",
    [
        (8, False),
        (14, False),
        (20, False),
        (27, True),
    ],
)
def test_ast_info_from_covered_function(scope_line, expected_should_be_covered):
    module_name = "tests.fixtures.instrumentation.covered_functions"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(),
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {8, 14, 20}

    scope = module_ast_info.get_scope(scope_line)
    assert scope is not None
    assert scope.should_be_covered() is expected_should_be_covered


@pytest.mark.parametrize(
    "scope_line, expected_should_be_covered",
    [
        (8, True),
        (14, True),
        (20, True),
        (27, False),
    ],
)
def test_ast_info_from_covered_function_no_cover(scope_line, expected_should_be_covered):
    module_name = "tests.fixtures.instrumentation.covered_functions"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(
            no_cover=["covered"],
            enable_inline_pragma_no_cover=False,
            enable_inline_pynguin_no_cover=False,
        ),
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {27}

    scope = module_ast_info.get_scope(scope_line)
    assert scope is not None
    assert scope.should_be_covered() is expected_should_be_covered


@pytest.mark.parametrize(
    "scope_line, expected_should_be_covered",
    [
        (8, True),
        (14, False),
        (20, False),
        (27, False),
    ],
)
def test_ast_info_from_covered_function_only_cover(scope_line, expected_should_be_covered):
    module_name = "tests.fixtures.instrumentation.covered_functions"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(
            only_cover=["not_covered1"],
            enable_inline_pragma_no_cover=False,
            enable_inline_pynguin_no_cover=False,
        ),
    )

    assert module_ast_info is not None
    assert module_ast_info.only_cover_lines == {8}
    assert not module_ast_info.no_cover_lines

    scope = module_ast_info.get_scope(scope_line)
    assert scope is not None
    assert scope.should_be_covered() is expected_should_be_covered


@pytest.mark.parametrize(
    "scope_line, expected_should_be_covered",
    [
        (9, False),
        (13, False),
        (17, True),
    ],
)
def test_ast_info_from_covered_classes(scope_line, expected_should_be_covered):
    module_name = "tests.fixtures.instrumentation.covered_classes"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(),
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {8, 13}

    scope = module_ast_info.get_scope(scope_line)
    assert scope is not None
    assert scope.should_be_covered() is expected_should_be_covered


@pytest.mark.parametrize(
    "scope_line, expected_lines, expected_branches",
    [
        # scope_line, dict of line: expected_should_cover, dict of line: expected_should_cover
        (
            8,
            {9: False, 10: False, 11: True, 12: True},
            {9: False, 11: False},
        ),
        (
            14,
            {15: True, 16: True, 17: False, 18: False, 19: True, 20: True},
            {15: True, 17: False, 19: False},
        ),
        (
            22,
            {23: True, 24: True, 25: False, 26: False},
            {23: False, 25: False},
        ),
        (
            28,
            {29: False, 30: False, 31: False, 32: False, 33: False, 34: True, 35: True},
            {29: False, 30: False, 32: False, 34: False},
        ),
        (
            37,
            {38: True, 39: False, 40: False, 41: True, 42: True, 43: True, 44: True},
            {38: True, 39: False, 41: False, 43: True},
        ),
        (
            46,
            {47: False, 48: False, 49: True},
            {47: False},
        ),
        (
            51,
            {52: True, 53: False, 54: False, 55: True, 56: True, 57: True},
            {52: True, 53: False, 55: False},
        ),
        (
            59,
            {60: False, 61: False, 62: True},
            {60: False},
        ),
        (
            64,
            {65: True, 66: True, 67: False, 68: False, 69: True},
            {65: False, 67: False},
        ),
        (
            71,
            {72: False, 73: False, 74: False, 75: False, 76: False, 77: True},
            {73: False, 75: False},
        ),
        (
            79,
            {80: True, 81: False, 82: False, 83: True, 84: True, 85: True, 86: True},
            {81: False, 83: True, 85: True},
        ),
        (
            88,
            {89: True, 90: True, 91: False, 92: False, 93: True, 94: True, 95: True},
            {91: False, 93: True},
        ),
    ],
)
def test_ast_info_from_covered_branches(scope_line, expected_lines, expected_branches):
    module_name = "tests.fixtures.instrumentation.covered_branches"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(),
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {9, 17, 25, 29, 39, 47, 53, 60, 67, 72, 81, 91}

    scope = module_ast_info.get_scope(scope_line)
    assert scope is not None
    assert scope.should_be_covered()

    for line, expected in expected_branches.items():
        assert scope.should_cover_conditional_statement(line) is expected

    for line, expected in expected_lines.items():
        assert scope.should_cover_line(line) is expected


@pytest.mark.parametrize(
    "scope_line, expected_lines",
    [
        # scope_line, dict of line: expected_should_cover
        (
            8,
            {9: True, 10: False, 12: True, 13: True, 14: True, 15: True, 16: False, 18: True},
        ),
        (
            20,
            {21: True, 22: True, 23: True, 24: False, 25: False, 26: True},
        ),
        (
            28,
            {29: True, 30: True, 31: False, 32: False, 33: True},
        ),
        (
            35,
            {36: True, 37: True, 38: True, 39: True, 40: True, 41: False, 42: False, 43: True},
        ),
        (
            45,
            {46: True, 47: True, 48: True, 49: True, 50: True, 51: False, 52: False, 53: True},
        ),
        (
            55,
            {
                56: True,
                57: True,
                58: True,
                59: False,
                60: False,
                61: True,
                62: True,
                63: True,
                64: True,
                65: True,
            },
        ),
    ],
)
def test_ast_info_from_covered_lines(scope_line, expected_lines):
    module_name = "tests.fixtures.instrumentation.covered_lines"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(),
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {10, 16, 24, 31, 41, 51, 59}

    scope = module_ast_info.get_scope(scope_line)
    assert scope is not None
    assert scope.should_be_covered()

    for line, expected in expected_lines.items():
        assert scope.should_cover_line(line) is expected


def test_ast_info_from_invalid():
    module_name = "tests.fixtures.test"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name, ".conf"),
        module_name,
        to_cover_config=ToCoverConfiguration(),
    )

    assert module_ast_info is None


def test_ast_info_from_nonexistent():
    module_name = "tests.fixtures.instrumentation.nonexistent"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        to_cover_config=ToCoverConfiguration(),
    )

    assert module_ast_info is None
