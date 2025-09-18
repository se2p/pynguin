#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pynguin.instrumentation.transformer import ModuleAstInfo


def get_module_path(module_name: str, extension: str = ".py") -> str:
    return module_name.replace(".", "/") + extension


def test_ast_info_from_covered_function():
    module_name = "tests.fixtures.instrumentation.covered_functions"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(),
        no_cover=(),
        enable_inline_pragma_no_cover=True,
        enable_inline_pynguin_no_cover=True,
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {8, 14, 20}

    not_covered1 = module_ast_info.get_scope(8)
    assert not_covered1 is not None
    assert not not_covered1.should_be_covered()

    not_covered2 = module_ast_info.get_scope(14)
    assert not_covered2 is not None
    assert not not_covered2.should_be_covered()

    not_covered3 = module_ast_info.get_scope(20)
    assert not_covered3 is not None
    assert not not_covered3.should_be_covered()

    covered = module_ast_info.get_scope(27)
    assert covered is not None
    assert covered.should_be_covered()


def test_ast_info_from_covered_function_no_cover():
    module_name = "tests.fixtures.instrumentation.covered_functions"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(),
        no_cover=(f"{module_name}.covered",),
        enable_inline_pragma_no_cover=False,
        enable_inline_pynguin_no_cover=False,
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {27}

    not_covered1 = module_ast_info.get_scope(8)
    assert not_covered1 is not None
    assert not_covered1.should_be_covered()

    not_covered2 = module_ast_info.get_scope(14)
    assert not_covered2 is not None
    assert not_covered2.should_be_covered()

    not_covered3 = module_ast_info.get_scope(20)
    assert not_covered3 is not None
    assert not_covered3.should_be_covered()

    covered = module_ast_info.get_scope(27)
    assert covered is not None
    assert not covered.should_be_covered()


def test_ast_info_from_covered_function_only_cover():
    module_name = "tests.fixtures.instrumentation.covered_functions"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(f"{module_name}.not_covered1",),
        no_cover=(),
        enable_inline_pragma_no_cover=False,
        enable_inline_pynguin_no_cover=False,
    )

    assert module_ast_info is not None
    assert module_ast_info.only_cover_lines == {8}
    assert not module_ast_info.no_cover_lines

    not_covered1 = module_ast_info.get_scope(8)
    assert not_covered1 is not None
    assert not_covered1.should_be_covered()

    not_covered2 = module_ast_info.get_scope(14)
    assert not_covered2 is not None
    assert not not_covered2.should_be_covered()

    not_covered3 = module_ast_info.get_scope(20)
    assert not_covered3 is not None
    assert not not_covered3.should_be_covered()

    covered = module_ast_info.get_scope(27)
    assert covered is not None
    assert not covered.should_be_covered()


def test_ast_info_from_covered_classes():
    module_name = "tests.fixtures.instrumentation.covered_classes"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(),
        no_cover=(),
        enable_inline_pragma_no_cover=True,
        enable_inline_pynguin_no_cover=True,
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {8, 13}

    foo_foo = module_ast_info.get_scope(9)
    assert foo_foo is not None
    assert not foo_foo.should_be_covered()

    bar_bar = module_ast_info.get_scope(13)
    assert bar_bar is not None
    assert not bar_bar.should_be_covered()

    baz_baz = module_ast_info.get_scope(17)
    assert baz_baz is not None
    assert baz_baz.should_be_covered()


def test_ast_info_from_covered_branches():  # noqa: PLR0915
    module_name = "tests.fixtures.instrumentation.covered_branches"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(),
        no_cover=(),
        enable_inline_pragma_no_cover=True,
        enable_inline_pynguin_no_cover=True,
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {9, 17, 25, 29, 39, 47, 52}

    if_x = module_ast_info.get_scope(8)
    assert if_x is not None
    assert if_x.should_be_covered()
    assert not if_x.should_cover_line(9)
    assert not if_x.should_cover_line(10)
    assert if_x.should_cover_line(11)
    assert if_x.should_cover_line(12)

    elif_x = module_ast_info.get_scope(14)
    assert elif_x is not None
    assert elif_x.should_be_covered()
    assert elif_x.should_cover_line(15)
    assert elif_x.should_cover_line(16)
    assert not elif_x.should_cover_line(17)
    assert not elif_x.should_cover_line(18)
    assert elif_x.should_cover_line(19)
    assert elif_x.should_cover_line(20)

    else_x = module_ast_info.get_scope(22)
    assert else_x is not None
    assert else_x.should_be_covered()
    assert else_x.should_cover_line(23)
    assert else_x.should_cover_line(24)
    assert not else_x.should_cover_line(25)
    assert not else_x.should_cover_line(26)

    nested_if_x = module_ast_info.get_scope(28)
    assert nested_if_x is not None
    assert nested_if_x.should_be_covered()
    assert not nested_if_x.should_cover_line(29)
    assert not nested_if_x.should_cover_line(30)
    assert not nested_if_x.should_cover_line(31)
    assert not nested_if_x.should_cover_line(32)
    assert not nested_if_x.should_cover_line(33)
    assert nested_if_x.should_cover_line(34)
    assert nested_if_x.should_cover_line(35)

    nested_if_y = module_ast_info.get_scope(37)
    assert nested_if_y is not None
    assert nested_if_y.should_be_covered()
    assert nested_if_y.should_cover_line(38)
    assert not nested_if_y.should_cover_line(39)
    assert not nested_if_y.should_cover_line(40)
    assert nested_if_y.should_cover_line(41)
    assert nested_if_y.should_cover_line(42)
    assert nested_if_y.should_cover_line(43)
    assert nested_if_y.should_cover_line(44)

    while_x = module_ast_info.get_scope(46)
    assert while_x is not None
    assert while_x.should_be_covered()
    assert not while_x.should_cover_line(47)
    assert not while_x.should_cover_line(48)
    assert while_x.should_cover_line(49)

    for_i = module_ast_info.get_scope(51)
    assert for_i is not None
    assert for_i.should_be_covered()
    assert not for_i.should_cover_line(52)
    assert not for_i.should_cover_line(53)
    assert for_i.should_cover_line(54)


def test_ast_info_from_covered_lines():
    module_name = "tests.fixtures.instrumentation.covered_lines"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(),
        no_cover=(),
        enable_inline_pragma_no_cover=True,
        enable_inline_pynguin_no_cover=True,
    )

    assert module_ast_info is not None
    assert not module_ast_info.only_cover_lines
    assert module_ast_info.no_cover_lines == {10, 16}

    no_cover_lines = module_ast_info.get_scope(8)
    assert no_cover_lines is not None
    assert no_cover_lines.should_be_covered()
    assert no_cover_lines.should_cover_line(9)
    assert not no_cover_lines.should_cover_line(10)
    assert no_cover_lines.should_cover_line(12)
    assert no_cover_lines.should_cover_line(13)
    assert no_cover_lines.should_cover_line(14)
    assert no_cover_lines.should_cover_line(15)
    assert not no_cover_lines.should_cover_line(16)
    assert no_cover_lines.should_cover_line(18)


def test_ast_info_from_invalid():
    module_name = "tests.fixtures.test"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name, ".conf"),
        module_name,
        only_cover=(),
        no_cover=(),
        enable_inline_pragma_no_cover=True,
        enable_inline_pynguin_no_cover=True,
    )

    assert module_ast_info is None


def test_ast_info_from_nonexistent():
    module_name = "tests.fixtures.instrumentation.nonexistent"
    module_ast_info = ModuleAstInfo.from_path(
        get_module_path(module_name),
        module_name,
        only_cover=(),
        no_cover=(),
        enable_inline_pragma_no_cover=True,
        enable_inline_pynguin_no_cover=True,
    )

    assert module_ast_info is None
