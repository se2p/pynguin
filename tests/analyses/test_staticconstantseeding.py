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


def _create_two_projects(tmp_path: Path) -> None:
    """Two sibling top-level packages under one project_path.

    ``sut`` is the project under test (a target module plus a sibling helper module);
    ``other`` is an unrelated package that merely shares the project_path root (as an
    installed dependency would in a site-packages directory).
    """
    sut = tmp_path / "sut"
    sut.mkdir()
    (sut / "__init__.py").write_text("", encoding="utf-8")
    (sut / "mod.py").write_text("SUT_MOD = 'sut_mod_const'\n", encoding="utf-8")
    (sut / "helper.py").write_text("SUT_HELPER = 'sut_helper_const'\n", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    (other / "__init__.py").write_text("", encoding="utf-8")
    (other / "mod.py").write_text("OTHER = 'other_const'\n", encoding="utf-8")


def test_collection_scoped_to_sut_top_level_package(tmp_path: Path):
    _create_two_projects(tmp_path)
    pool = collect_static_constants(tmp_path, module_names=["sut.mod"])
    strings = pool.get_all_constants_for(str)
    # The whole SUT project is collected -- the target module and its sibling helper --
    # not just the single target module.
    assert "sut_mod_const" in strings
    assert "sut_helper_const" in strings
    # An unrelated package sharing the project_path root is excluded.
    assert "other_const" not in strings


def test_collection_falls_back_to_all_packages_without_module_names(tmp_path: Path):
    _create_two_projects(tmp_path)
    pool = collect_static_constants(tmp_path)
    strings = pool.get_all_constants_for(str)
    assert "sut_mod_const" in strings
    assert "other_const" in strings
