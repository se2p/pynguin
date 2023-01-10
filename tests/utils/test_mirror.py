#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

from pynguin.utils.mirror import Mirror


@pytest.fixture
def mirror():
    return Mirror()


def test_mirror(mirror):
    assert mirror[5] == 5
    assert mirror["5"] == "5"
