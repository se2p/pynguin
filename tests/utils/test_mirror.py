#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.utils.mirror import Mirror


@pytest.fixture
def mirror():
    return Mirror()


def test_mirror(mirror):
    assert mirror[5] == 5
    assert mirror["5"] == "5"
