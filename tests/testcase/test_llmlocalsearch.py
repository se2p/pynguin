#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the LLM local search hook."""

from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.llmlocalsearch as llmls
from pynguin.testcase.llmlocalsearch import LLMLocalSearch
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def _make_search(*, failing: bool = False):
    """Builds an LLMLocalSearch with fully mocked collaborators."""
    original = MagicMock(name="original_chromosome")
    chromosome = MagicMock(name="chromosome")
    chromosome.is_failing.return_value = failing
    chromosome.get_fitness_functions.return_value = []
    chromosome.get_coverage_functions.return_value = []
    objective = MagicMock(name="objective")
    factory = MagicMock(name="factory")
    suite = MagicMock(name="suite")
    suite.test_case_chromosomes = [original]
    executor = MagicMock(name="executor")
    search = LLMLocalSearch(chromosome, objective, factory, suite, executor)
    return search, chromosome, objective, factory, suite, executor, original


def _patch_agent(monkeypatch, *, output="code", parsed=None):
    """Patches the module-level LLMAgent to a mock returning ``parsed`` chromosomes."""
    agent = MagicMock(name="agent")
    agent.local_search_call.return_value = output
    handler = agent.llm_test_case_handler
    handler.get_test_case_chromosomes_from_llm_results.return_value = (
        [MagicMock(name="candidate")] if parsed is None else parsed
    )
    monkeypatch.setattr(llmls, "LLMAgent", lambda: agent)
    return agent


def test_improvement_returns_true_and_counts_success(monkeypatch):
    search, _, objective, _, suite, _, original = _make_search()
    objective.has_improved.return_value = True
    agent = _patch_agent(monkeypatch)
    monkeypatch.setattr(search, "_setup_llm_call", lambda _position: ("tc", "mod", ["ann"]))

    tracked = {}
    monkeypatch.setattr(llmls.stat, "add_to_runtime_variable", tracked.setdefault)

    assert search.llm_local_search(0) is True
    candidate = agent.llm_test_case_handler.get_test_case_chromosomes_from_llm_results.return_value[
        0
    ]
    objective.has_improved.assert_called_once_with(candidate)
    # Suite was not reverted.
    assert suite.test_case_chromosomes == [original]
    assert tracked.get(RuntimeVariable.TotalLocalSearchLLMSuccessCalls) == 1
    assert RuntimeVariable.TotalLocalSearchLLMSuccessCallsDespiteFailing not in tracked


def test_improvement_on_failing_test_counts_despite_failing(monkeypatch):
    search, _, objective, _, _, _, _ = _make_search(failing=True)
    objective.has_improved.return_value = True
    _patch_agent(monkeypatch)
    monkeypatch.setattr(search, "_setup_llm_call", lambda _position: ("tc", "mod", ["ann"]))

    tracked = {}
    monkeypatch.setattr(llmls.stat, "add_to_runtime_variable", tracked.setdefault)

    assert search.llm_local_search(0) is True
    assert tracked.get(RuntimeVariable.TotalLocalSearchLLMSuccessCallsDespiteFailing) == 1
    assert RuntimeVariable.TotalLocalSearchLLMSuccessCalls not in tracked


def test_no_improvement_reverts_suite(monkeypatch):
    search, _, objective, _, suite, _, original = _make_search()
    _patch_agent(monkeypatch)

    # Simulate the objective swapping the candidate into the suite before rejecting it.
    def swap(candidate):
        suite.test_case_chromosomes[0] = candidate
        return False

    objective.has_improved.side_effect = swap
    monkeypatch.setattr(search, "_setup_llm_call", lambda _position: ("tc", "mod", ["ann"]))
    monkeypatch.setattr(llmls.stat, "add_to_runtime_variable", lambda _var, _val: None)

    assert search.llm_local_search(0) is False
    # The swapped-in candidate was reverted back to the original chromosome.
    assert suite.test_case_chromosomes == [original]


def test_setup_failure_skips_llm_call(monkeypatch):
    search, _, objective, _, _, _, _ = _make_search()
    agent = _patch_agent(monkeypatch)
    monkeypatch.setattr(search, "_setup_llm_call", lambda _position: None)

    assert search.llm_local_search(0) is False
    agent.local_search_call.assert_not_called()
    objective.has_improved.assert_not_called()


@pytest.mark.parametrize("parsed", [[], ["a", "b"]])
def test_wrong_number_of_parsed_test_cases_returns_false(monkeypatch, parsed):
    search, _, objective, _, _, _, _ = _make_search()
    _patch_agent(monkeypatch, parsed=parsed)
    monkeypatch.setattr(search, "_setup_llm_call", lambda _position: ("tc", "mod", ["ann"]))
    monkeypatch.setattr(llmls.stat, "add_to_runtime_variable", lambda _var, _val: None)

    assert search.llm_local_search(0) is False
    objective.has_improved.assert_not_called()


def test_get_name_for_method():
    search, *_ = _make_search()
    accessible = MagicMock(spec=GenericMethod)
    accessible.owner.full_name = "module.TestClass"
    accessible.method_name = "do_thing"
    stmt = MagicMock()
    stmt.accessible = accessible
    assert search._get_name(stmt) == "TestClass.do_thing"


def test_get_name_for_function():
    search, *_ = _make_search()
    accessible = MagicMock(spec=GenericFunction)
    accessible.function_name = "some_function"
    stmt = MagicMock()
    stmt.accessible = accessible
    assert search._get_name(stmt) == "some_function"


def test_get_name_for_function_without_name():
    search, *_ = _make_search()
    accessible = MagicMock(spec=GenericFunction)
    accessible.function_name = None
    stmt = MagicMock()
    stmt.accessible = accessible
    assert search._get_name(stmt) is None


def test_get_name_for_constructor():
    search, *_ = _make_search()
    accessible = MagicMock(spec=GenericConstructor)
    accessible.owner.full_name = "module.TestClass"
    stmt = MagicMock()
    stmt.accessible = accessible
    assert search._get_name(stmt) == "TestClass.__init__"


def test_get_name_for_none_accessible():
    search, *_ = _make_search()
    stmt = MagicMock()
    stmt.accessible = None
    assert search._get_name(stmt) is None


def test_get_shortened_source_code_collects_forward_dependencies(monkeypatch):
    search, chromosome, *_ = _make_search()
    test_case = chromosome.test_case
    test_case.forward_dependencies.return_value = {2, 0}
    stmt0 = MagicMock(name="stmt0")
    stmt2 = MagicMock(name="stmt2")
    test_case.get_statement.side_effect = lambda idx: {0: stmt0, 2: stmt2}[idx]

    monkeypatch.setattr(search, "_get_name", lambda stmt: "foo" if stmt is stmt0 else "bar")
    monkeypatch.setattr(
        llmls, "get_part_of_source_code", lambda name: f"src_{name}" if name == "foo" else ""
    )
    monkeypatch.setattr(llmls, "shorten_line_annotations", lambda _ann, name: [name])

    source, annotations = search.get_shortened_source_code(0, ["whole"])
    test_case.forward_dependencies.assert_called_once_with(0)
    # Only the statement whose source was found contributes.
    assert source == "src_foo\n\n"
    assert annotations == ["foo"]


def test_setup_skips_when_statement_binds_no_variable(monkeypatch):
    search, chromosome, _, _, _, _, _ = _make_search()
    config.configuration.local_search.ls_llm_whole_module = False
    monkeypatch.setattr(llmls, "get_coverage_report", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr(llmls.stat, "add_to_runtime_variable", lambda _var, _val: None)
    statement = MagicMock()
    statement.bound_variable = None
    chromosome.test_case.get_statement.return_value = statement

    assert search._setup_llm_call(0) is None


def test_setup_whole_module_returns_inputs(monkeypatch):
    search, chromosome, _, _, _, _, _ = _make_search()
    config.configuration.local_search.ls_llm_whole_module = True
    report = MagicMock()
    report.line_annotations = ["ann"]
    monkeypatch.setattr(llmls, "get_coverage_report", lambda *_a, **_k: report)
    monkeypatch.setattr(llmls, "get_module_source_code", lambda: "module source")
    monkeypatch.setattr(llmls.stat, "add_to_runtime_variable", lambda _var, _val: None)
    chromosome.test_case.to_test_function.return_value.code = "def test_0():\n    pass"

    result = search._setup_llm_call(0)
    assert result == ("def test_0():\n    pass", "module source", ["ann"])
    # Restore default so other tests are unaffected.
    config.configuration.local_search.ls_llm_whole_module = False
