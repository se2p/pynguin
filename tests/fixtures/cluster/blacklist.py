#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

# Uses function from blacklisted module
import tempfile as temp
from tempfile import SpooledTemporaryFile, mkdtemp

import tests.fixtures.cluster.blacklist_transitive as bl_tr


def foo():
    temp.mktemp()
    SpooledTemporaryFile()
    mkdtemp()
    bl_tr.bar()


def main():
    """main usually calls sys.exit so we don't want it."""


def test():
    """test usually performs some tests on the module, we don't want them."""
