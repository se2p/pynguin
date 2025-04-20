#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import multiprocessing.shared_memory as sm

# Uses function from blacklisted module
import tempfile as temp

from tempfile import SpooledTemporaryFile
from tempfile import mkdtemp
from time import sleep

import tests.fixtures.cluster.blacklist_transitive as bl_tr


def foo():
    temp.mktemp()
    SpooledTemporaryFile()
    mkdtemp()
    bl_tr.bar()
    sm.SharedMemory()
    sleep(1)


def main():
    """main usually calls sys.exit so we don't want it."""


def test():
    """test usually performs some tests on the module, we don't want them."""


def test_foo():
    """test usually performs some tests on the module, we don't want them."""
