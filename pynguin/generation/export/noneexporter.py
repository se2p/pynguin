#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a no op exporter."""
import os
from typing import List, Union

from pynguin.generation.export.abstractexporter import AbstractTestExporter
from pynguin.testcase import testcase as tc


# pylint: disable=too-few-public-methods
class NoneExporter(AbstractTestExporter):
    """An exporter, which does basically nothing."""

    def export_sequences(
        self, path: Union[str, os.PathLike], test_cases: List[tc.TestCase]
    ):
        pass
