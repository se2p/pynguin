#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixtures for the export tests.

The previous fixtures here built ``DefaultTestCase``/old-``Statement`` object
graphs for the removed visitor-based exporter (``PyTestChromosomeToAstVisitor``).
The current libcst-based ``TestSuiteWriter`` tests in ``test_export.py`` build
their fixtures inline using ``tests/testcase/_builders.py`` instead, so no
module-specific fixtures are required here.
"""
