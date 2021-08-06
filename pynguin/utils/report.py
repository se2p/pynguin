#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides capabilites to create a coverage report."""
from __future__ import annotations

import dataclasses
import importlib.resources
import inspect
import sys
from pathlib import Path
from typing import List

from jinja2 import Template

import pynguin.configuration as config
import pynguin.ga.testsuitechromosome as tsc
from pynguin.ga.fitnessfunctions.fitness_utilities import (
    analyze_results,
    compute_branch_coverage,
)
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@dataclasses.dataclass
class CoverageEntry:
    """How many things exist and how many are covered?"""

    existing: int = 0
    covered: int = 0

    def add(self, other: CoverageEntry) -> None:
        """Add data from another coverage entry to this one.

        Args:
            other: another CoverageEntry whose values are added to this one.
        """
        self.existing += other.existing
        self.covered += other.covered


@dataclasses.dataclass
class LineAnnotation:
    """Coverage information per line."""

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
        if self.branchless_code_objects.existing > 0:
            msgs.append(
                f"{self.branchless_code_objects.covered}/"
                f"{self.branchless_code_objects.existing}"
                f" branchless code objects covered"
            )
        if self.branches.existing > 0:
            msgs.append(
                f"{self.branches.covered}/{self.branches.existing} branches covered"
            )
        if msgs:
            return ";".join(msgs)
        return ""


@dataclasses.dataclass
class CoverageData:
    """All coverage related data required to create a coverage report."""

    module: str

    # Raw source code of the module under test
    source: List[str]

    # Achieved branch coverage
    branch_coverage: float

    # Information about total covered branches
    branches: CoverageEntry

    # Information about total covered branchless code objects
    branchless_code_objects: CoverageEntry

    line_annotations: List[LineAnnotation]


# pylint:disable=too-many-locals
def create_coverage_report(
    suite: tsc.TestSuiteChromosome, executor: TestCaseExecutor
) -> None:
    """Create a coverage report for the given test suite

    Args:
        suite: The suite for which a coverage report should be generated.
        executor: The executor
    """
    results = []
    for test_case_chromosome in suite.test_case_chromosomes:
        result = test_case_chromosome.get_last_execution_result()
        assert result is not None
        results.append(result)
    trace = analyze_results(results)
    known_data = executor.tracer.get_known_data()

    line_to_branchless_code_object_coverage = (
        _get_line_to_branchless_code_object_coverage(known_data, trace)
    )

    line_to_branch_coverage = _get_line_to_branch_coverage(known_data, trace)

    source = inspect.getsourcelines(sys.modules[config.configuration.module_name])[0]
    branch_coverage = compute_branch_coverage(trace, known_data)

    branchless_code_objects = CoverageEntry()
    for cov in line_to_branchless_code_object_coverage.values():
        branchless_code_objects.add(cov)
    branches = CoverageEntry()
    for cov in line_to_branch_coverage.values():
        branches.add(cov)

    line_annotations = [
        _get_line(
            idx + 1, line_to_branchless_code_object_coverage, line_to_branch_coverage
        )
        for idx in range(len(source))
    ]

    cov_data = CoverageData(
        config.configuration.module_name,
        source,
        branch_coverage,
        branches,
        branchless_code_objects,
        line_annotations,
    )
    _write_results(cov_data)


def _write_results(cov_data: CoverageData) -> None:
    report_dir = Path(config.configuration.statistics_output.report_dir).absolute()
    report_dir.mkdir(parents=True, exist_ok=True)
    output_file = report_dir / "cov_report.html"
    with output_file.open(mode="w", encoding="utf-8") as html_file:
        template = Template(
            importlib.resources.read_text("pynguin.resources", "coverage-template.html")
        )
        html_file.write(template.render(cov_data=cov_data))
    # Copy required files.
    for file in ["highlight.min.js", "github-dark.min.css"]:
        with (report_dir / file).open(mode="w", encoding="utf-8") as out:
            out.write(importlib.resources.read_text("pynguin.resources", file))


def _get_line_to_branch_coverage(known_data, trace):
    line_to_branch_coverage = {}
    for predicate in known_data.existing_predicates:
        lineno = known_data.existing_predicates[predicate].line_no
        if lineno not in line_to_branch_coverage:
            line_to_branch_coverage[lineno] = CoverageEntry()
        line_to_branch_coverage[lineno].existing += 2
        if (predicate, 0.0) in trace.true_distances.items():
            line_to_branch_coverage[lineno].covered += 1
        if (predicate, 0.0) in trace.false_distances.items():
            line_to_branch_coverage[lineno].covered += 1
    return line_to_branch_coverage


def _get_line_to_branchless_code_object_coverage(known_data, trace):
    line_to_branchless_code_object_coverage = {}
    for code in known_data.branch_less_code_objects:
        lineno = known_data.existing_code_objects[code].code_object.co_firstlineno
        if lineno not in line_to_branchless_code_object_coverage:
            line_to_branchless_code_object_coverage[lineno] = CoverageEntry()
        line_to_branchless_code_object_coverage[lineno].existing += 1
        if code in trace.executed_code_objects:
            line_to_branchless_code_object_coverage[lineno].covered += 1
    return line_to_branchless_code_object_coverage


def _get_line(lineno, code_object_coverage, predicate_coverage) -> LineAnnotation:
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
        total.add(branchless_code_objects)
    if lineno in predicate_coverage:
        branches = predicate_coverage[lineno]
        total.add(branches)
    return LineAnnotation(lineno, total, branches, branchless_code_objects)
