#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides capabilites to create a coverage report."""
from __future__ import annotations

import dataclasses
import datetime
import importlib.resources
import inspect
import sys
import typing
from pathlib import Path

import pygments
from jinja2 import Template
from pygments.formatters.html import HtmlFormatter
from pygments.lexers.python import PythonLexer

import pynguin.configuration as config
import pynguin.ga.computations as ff

if typing.TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc
    from pynguin.testcase.execution import TestCaseExecutor


@dataclasses.dataclass(frozen=True)
class CoverageEntry:
    """How many things exist and how many are covered?"""

    covered: int = 0
    existing: int = 0

    def __add__(self, other: CoverageEntry) -> CoverageEntry:
        """Add data from another coverage entry to this one.

        Args:
            other: another CoverageEntry whose values are added to this one.

        Returns:
            A new coverage entry with the summed up elements of self and other.
        """
        return CoverageEntry(
            self.covered + other.covered, self.existing + other.existing
        )


@dataclasses.dataclass
class LineAnnotation:
    """Coverage information for a single line."""

    line_no: int

    total: CoverageEntry

    branches: CoverageEntry

    branchless_code_objects: CoverageEntry

    def message(self):
        """Compute the message that should be displayed as a tool tip
        when hovering over this line number.

        Returns:
            The message for this line.
        """
        msgs = []
        if self.branches.existing > 0:
            msgs.append(
                f"{self.branches.covered}/{self.branches.existing} branches covered"
            )
        if self.branchless_code_objects.existing > 0:
            msgs.append(
                f"{self.branchless_code_objects.covered}/"
                f"{self.branchless_code_objects.existing}"
                f" branchless code objects covered"
            )
        return ";".join(msgs)


@dataclasses.dataclass
class CoverageReport:
    """All coverage related data required to create a coverage report."""

    module: str

    # Raw source code of the module under test
    source: list[str]

    # Achieved branch coverage
    branch_coverage: float

    # Information about total covered branches
    branches: CoverageEntry

    # Information about total covered branchless code objects
    branchless_code_objects: CoverageEntry

    line_annotations: list[LineAnnotation]


# pylint:disable=too-many-locals
def get_coverage_report(
    suite: tsc.TestSuiteChromosome, executor: TestCaseExecutor
) -> CoverageReport:
    """Create a coverage report for the given test suite

    Args:
        suite: The suite for which a coverage report should be generated.
        executor: The executor

    Returns:
        The coverage report.
    """
    results = []
    for test_case_chromosome in suite.test_case_chromosomes:
        result = test_case_chromosome.get_last_execution_result()
        assert result is not None
        results.append(result)
    trace = ff.analyze_results(results)
    known_data = executor.tracer.get_known_data()

    line_to_branchless_code_object_coverage = (
        _get_line_to_branchless_code_object_coverage(known_data, trace)
    )

    line_to_branch_coverage = _get_line_to_branch_coverage(known_data, trace)

    source = inspect.getsourcelines(sys.modules[config.configuration.module_name])[0]
    branch_coverage = ff.compute_branch_coverage(trace, known_data)

    branchless_code_objects = CoverageEntry()
    for cov in line_to_branchless_code_object_coverage.values():
        branchless_code_objects += cov
    branches = CoverageEntry()
    for cov in line_to_branch_coverage.values():
        branches += cov

    line_annotations = [
        _get_line_annotations(
            idx + 1, line_to_branchless_code_object_coverage, line_to_branch_coverage
        )
        for idx in range(len(source))
    ]

    return CoverageReport(
        config.configuration.module_name,
        source,
        branch_coverage,
        branches,
        branchless_code_objects,
        line_annotations,
    )


def render_coverage_report(
    cov_report: CoverageReport, report_path: Path, timestamp: datetime.datetime
) -> None:
    """Render the given coverage report to the given file.

    Args:
        timestamp: When was the report created.
        cov_report: The coverage report to render
        report_path: To file where the report should be rendered to.
    """
    with report_path.open(mode="w", encoding="utf-8") as html_file:
        template = Template(
            importlib.resources.read_text("pynguin.resources", "coverage-template.html")
        )
        html_file.write(
            template.render(
                cov_report=cov_report,
                highlight=pygments.highlight,
                lexer=PythonLexer,
                formatter=HtmlFormatter,
                date=timestamp,
            )
        )


def _get_line_to_branch_coverage(known_data, trace):
    line_to_branch_coverage = {}
    for predicate in known_data.existing_predicates:
        lineno = known_data.existing_predicates[predicate].line_no
        if lineno not in line_to_branch_coverage:
            line_to_branch_coverage[lineno] = CoverageEntry()
        line_to_branch_coverage[lineno] += CoverageEntry(existing=2)
        if (predicate, 0.0) in trace.true_distances.items():
            line_to_branch_coverage[lineno] += CoverageEntry(covered=1)
        if (predicate, 0.0) in trace.false_distances.items():
            line_to_branch_coverage[lineno] += CoverageEntry(covered=1)
    return line_to_branch_coverage


def _get_line_to_branchless_code_object_coverage(known_data, trace):
    line_to_branchless_code_object_coverage = {}
    for code in known_data.branch_less_code_objects:
        lineno = known_data.existing_code_objects[code].code_object.co_firstlineno
        if lineno not in line_to_branchless_code_object_coverage:
            line_to_branchless_code_object_coverage[lineno] = CoverageEntry()
        line_to_branchless_code_object_coverage[lineno] += CoverageEntry(existing=1)
        if code in trace.executed_code_objects:
            line_to_branchless_code_object_coverage[lineno] += CoverageEntry(covered=1)
    return line_to_branchless_code_object_coverage


def _get_line_annotations(
    lineno: int,
    code_object_coverage: dict[int, CoverageEntry],
    predicate_coverage: dict[int, CoverageEntry],
) -> LineAnnotation:
    """Compute line annotation for the given line no.

    Args:
        lineno: The lineno for which we should generate the information.
        code_object_coverage: code object coverage data
        predicate_coverage: predicate coverage data

    Returns:
        LineAnnotation data for the given line.
    """
    total = CoverageEntry()
    branches = CoverageEntry()
    branchless_code_objects = CoverageEntry()
    if lineno in code_object_coverage:
        branchless_code_objects = code_object_coverage[lineno]
        total += branchless_code_objects
    if lineno in predicate_coverage:
        branches = predicate_coverage[lineno]
        total += branches
    return LineAnnotation(lineno, total, branches, branchless_code_objects)
