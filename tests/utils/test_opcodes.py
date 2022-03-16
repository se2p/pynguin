#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

import pynguin.utils.opcodes as op
from tests.conftest import python38, python39, python310


@python310
def test_opcodes_310():
    assert not hasattr(op, "BEGIN_FINALLY")
    assert hasattr(op, "ROT_N")
    assert op.RERAISE == 119
