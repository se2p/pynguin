#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a no op exporter."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Union

from pynguin.generation.export.abstractexporter import AbstractTestExporter

if TYPE_CHECKING:
    from pynguin.testcase import testcase as tc


# pylint: disable=too-few-public-methods
class NoneExporter(AbstractTestExporter):
    """An exporter, which does basically nothing."""

    def export_sequences(
        self, path: Union[str, os.PathLike], test_cases: List[tc.TestCase]
    ):
        pass
