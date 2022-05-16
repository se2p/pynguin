#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import os

import pytest

from pynguin.analyses.constants import collect_static_constants


@pytest.fixture
def fixture_dir():
    return os.path.join(
        os.path.dirname(__file__),
        "",
        "..",
        "fixtures",
        "seeding",
        "staticconstantseeding",
    )


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
