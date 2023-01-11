#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import tempfile as temp

from tempfile import SpooledTemporaryFile
from tempfile import mkdtemp


def bar():
    temp.mktemp()
    SpooledTemporaryFile()
    mkdtemp()
