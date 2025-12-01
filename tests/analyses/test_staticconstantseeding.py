#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pathlib import Path

import pytest

from pynguin.analyses.constants import ConstantPool, collect_static_constants


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / ".." / "fixtures" / "seeding" / "staticconstantseeding"


@pytest.mark.parametrize(
    "type_, result",
    [(str, 2), (int, 2), (float, 1), (bytes, 2)],
)
def test_collect_constants(type_, result, fixture_dir):
    constants = collect_static_constants(fixture_dir)
    assert len(constants.get_all_constants_for(type_)) == result


def test_collect_constants_total(fixture_dir):
    constants = collect_static_constants(fixture_dir)
    assert len(constants) == 7


def _create_module(tmp_path: Path) -> list[str]:
    module_source = """def foo(d: dict[str, int]):
    if d['abcdef']:
        return True
    else:
        return False"""
    (tmp_path / "module_name.py").write_text(module_source, encoding="utf-8")
    return ["module_name"]


def test_collect_static_constants_module_names(tmp_path: Path):
    pool: ConstantPool = collect_static_constants(tmp_path, module_names=_create_module(tmp_path))
    assert pool.has_constant_for(str)
    assert "abcdef" in pool.get_all_constants_for(str)
