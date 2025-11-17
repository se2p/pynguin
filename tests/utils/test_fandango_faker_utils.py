#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import importlib.util

import pytest

from pynguin.utils.fandango_faker_utils import load_fandango_grammars

faker_installed = importlib.util.find_spec("faker")
fandango_installed = importlib.util.find_spec("fandango")


@pytest.mark.skipif(
    not faker_installed or not fandango_installed,
    reason="Fandango and Faker are not installed.",
)
def test_load_fandango_grammars():
    grammars = load_fandango_grammars("src/pynguin/resources/fans")
    assert len(grammars) > 0


@pytest.mark.skipif(
    not faker_installed or not fandango_installed,
    reason="Fandango and Faker are not installed.",
)
def test_fandango_grammars_unique():
    grammars = load_fandango_grammars("src/pynguin/resources/fans")
    assert len(grammars) == len(set(grammars))
