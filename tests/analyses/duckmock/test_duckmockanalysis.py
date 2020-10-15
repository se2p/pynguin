#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

from pynguin.analyses.duckmock.duckmockanalysis import DuckMockAnalysis


@pytest.fixture(scope="module")
def analysis() -> DuckMockAnalysis:
    analysis = DuckMockAnalysis("pynguin.setup.testclustergenerator")
    analysis.analyse()
    return analysis


def test_analysis(analysis):
    bindings = analysis.method_bindings
    assert len(bindings) == 36


def test_get_classes_for_method(analysis):
    classes_for_method = analysis.get_classes_for_method("__init__")
    assert len(classes_for_method) == 8


def test_get_classes_for_methods(analysis):
    classes_for_methods = analysis.get_classes_for_methods(
        [
            "is_function",
            "is_method",
        ]
    )
    assert len(classes_for_methods) == 4


def test_get_classes_for_non_existing_method(analysis):
    assert analysis.get_classes_for_method("non_existing_method") is None


def test_get_classes_for_non_existing_methods(analysis):
    classes_for_methods = analysis.get_classes_for_methods(
        [
            "is_function",
            "non_existing_method",
            "is_method",
        ]
    )
    assert len(classes_for_methods) == 4
