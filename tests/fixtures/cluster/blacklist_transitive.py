#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import tempfile as temp

from tempfile import SpooledTemporaryFile
from tempfile import mkdtemp


def bar():
    temp.mktemp()
    SpooledTemporaryFile()
    mkdtemp()
