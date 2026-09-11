#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import importlib.util
import pathlib
import sys

import coverage
import networkx as nx


def assert_generated_test_covers_lines(
    output_dir: pathlib.Path,
    target_file_path: pathlib.Path,
    target_lines: set[int],
    expected_symbol: str | None = None,
) -> None:
    """Execute a generated test suite under coverage and assert target lines are covered.

    Args:
        output_dir: Directory where Pynguin output the generated test file.
        target_file_path: Path to the SUT file under test.
        target_lines: Set of target line numbers expected to be covered.
        expected_symbol: Optional symbol name expected in generated test file.
    """
    test_files = list(output_dir.glob("test_*.py"))
    assert len(test_files) == 1, f"Expected 1 test file, found {len(test_files)}"
    generated_test_file = test_files[0]

    content = generated_test_file.read_text()
    if expected_symbol is not None:
        assert expected_symbol in content, (
            f"Expected symbol '{expected_symbol}' not in generated test file."
        )

    rel_target = target_file_path.relative_to(pathlib.Path().absolute())
    cov_rc = output_dir / ".coveragerc"
    cov_rc.write_text(f"[run]\ninclude = {rel_target}\nomit =\n")
    cov_db = output_dir / ".coverage"

    cov = coverage.Coverage(data_file=str(cov_db), config_file=str(cov_rc))
    cov.start()

    spec = importlib.util.spec_from_file_location(
        f"generated_test_{generated_test_file.stem}", generated_test_file
    )
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"generated_test_{generated_test_file.stem}"] = mod
    spec.loader.exec_module(mod)

    for attr_name in dir(mod):
        if attr_name.startswith("test_"):
            getattr(mod, attr_name)()

    cov.stop()
    cov.save()

    cov_data = cov.get_data()
    covered_lines = set(cov_data.lines(str(target_file_path.absolute())) or [])
    missing = target_lines - covered_lines
    assert not missing, (
        f"Target lines {missing} were not covered by generated test suite. "
        f"Covered lines in {target_file_path.name}: {covered_lines}"
    )


def _nx_to_dot(graph: nx.DiGraph) -> str:
    """Convert a NetworkX graph to a DOT string."""
    return nx.nx_pydot.to_pydot(graph).to_string()


def show_nx_graph(graph: nx.DiGraph):
    """Show a graph using NetworkX."""
    dot_str = _nx_to_dot(graph)
    show_dot_graph(dot_str)


def show_dot_graph(dot_str: str):
    """Show a graph using Graphviz."""
    import graphviz  # noqa: PLC0415

    graph = graphviz.Source(dot_str)
    graph.view()


def show_graph(graph):
    """Show a graph using Graphviz."""
    graph.view()


def print_dunder(obj):
    """Prints all dunder (__) attributes of an object row by row.

    DISCLAIMER: This function is only used for debugging purposes. Do not use it in
    production code as it uses the print function.

    Usage: Set a breakpoint somewhere in the code, execute the debugger and once it
    stops at the breakpoint, switch over to the console and type print_dunder(my_obj).

    :param obj: The object to inspect.
    """
    for attr in dir(obj):
        if attr.startswith("__"):
            print(f"{attr}: {getattr(obj, attr)}")  # noqa: T201
