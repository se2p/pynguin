#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pathlib import Path

import pytest

from pynguin.analyses.constants import collect_static_constants


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
