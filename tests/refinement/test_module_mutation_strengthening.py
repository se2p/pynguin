#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for module-level mutation-driven assertion strengthening."""

from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import pynguin.configuration as config
from pynguin.configuration import MutationStrengtheningGranularity
from pynguin.large_language_model.prompts.modulemutationstrengthenprompt import (
    ModuleMutationStrengthenPrompt,
)
from pynguin.refinement import refiner as refiner_module
from pynguin.refinement.pipeline import TestRefiner

_SUT_SOURCE = """\
def inc(x):
    return x + 1


def fallback(values):
    return values or [0]
"""

_PREAMBLE = "import strengthen_sut as module_0\n"

_EXISTING_TEST = """\
def test_inc():
    # Act
    result = module_0.inc(1)
    # Assert
    assert result == 2"""


@pytest.fixture
def sut(tmp_path, monkeypatch):
    (tmp_path / "strengthen_sut.py").write_text(_SUT_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("strengthen_sut")
    yield module
    sys.modules.pop("strengthen_sut", None)


@pytest.fixture
def refiner(sut):
    test_refiner = TestRefiner(module_under_test=sut)
    test_refiner.llm_client = MagicMock()
    return test_refiner


def test_strengthen_module_mutations_without_mutants_is_a_no_op(refiner):
    with patch("pynguin.refinement.pipeline.create_mutants", return_value=([], None)):
        preamble, tests, stats = refiner.strengthen_module_mutations(_PREAMBLE, [_EXISTING_TEST])

    assert (preamble, tests, stats) == (_PREAMBLE, [_EXISTING_TEST], {})
    refiner.llm_client.generate_from_prompt.assert_not_called()


def test_strengthen_module_mutations_chunks_survivors_by_max_mutants_per_prompt(refiner):
    def make_fake_mutant(line: int):
        mutation = MagicMock()
        mutation.operator.__name__ = "ArithmeticOperatorReplacement"
        mutation.node.lineno = line
        return (MagicMock(), [mutation])

    mutants = [make_fake_mutant(i) for i in range(1, 6)]
    refiner.llm_client.generate_from_prompt.return_value = _PREAMBLE + _EXISTING_TEST

    with (
        patch("pynguin.refinement.pipeline.create_mutants", return_value=(mutants, None)),
        patch("pynguin.refinement.pipeline.killed_set", return_value=set()),
    ):
        refiner.strengthen_module_mutations(
            _PREAMBLE, [_EXISTING_TEST], max_iterations=1, max_mutants_per_prompt=2
        )

    # 5 mutants chunked by 2 -> 3 chunks -> 3 prompt calls
    calls = refiner.llm_client.generate_from_prompt.call_args_list
    assert len(calls) == 3
    assert all(isinstance(call.args[0], ModuleMutationStrengthenPrompt) for call in calls)


def test_strengthen_module_mutations_kills_boundary_mutants(refiner):
    refiner.llm_client.generate_from_prompt.return_value = (
        "import math\n"
        "import strengthen_sut as module_0\n\n"
        "def test_inc():\n"
        "    # Act\n"
        "    result = module_0.inc(1)\n"
        "    # Assert\n"
        "    assert result == 2\n"
        "    assert isinstance(result, int)\n\n"
        "def test_fallback_empty():\n"
        "    assert module_0.fallback([]) == [0]\n"
        "    assert math.isfinite(module_0.fallback([])[0])\n\n"
        "def test_fallback_empty():\n"
        "    assert False\n\n"
        "def test_kills_nothing():\n"
        "    assert module_0.inc(0) >= 0\n"
    )

    preamble, tests, stats = refiner.strengthen_module_mutations(
        _PREAMBLE, [_EXISTING_TEST], max_iterations=1
    )

    # The import the new test needs is added; existing comments survive.
    assert "import math" in preamble
    assert "    # Act\n    result = module_0.inc(1)\n" in tests[0]
    assert "# Assert" in tests[0]
    # The vacuous isinstance assertion is pruned, the boundary test is kept once,
    # the new test that kills nothing is dropped.
    assert "isinstance" not in tests[0]
    assert len(tests) == 2
    assert "module_0.fallback([]) == [0]" in tests[1]
    assert "test_kills_nothing" not in "\n".join(tests)
    assert stats["mutants_killed_total"] > 0
    assert stats["assertions_removed"] >= 1
    assert stats["mutants_generated"] >= stats["mutants_killed_total"]


def test_strengthen_module_mutations_rejects_output_that_kills_nothing(refiner):
    refiner.llm_client.generate_from_prompt.return_value = (
        _PREAMBLE + _EXISTING_TEST + "\n    assert isinstance(result, int)\n"
    )

    _, tests, stats = refiner.strengthen_module_mutations(
        _PREAMBLE, [_EXISTING_TEST], max_iterations=1
    )

    assert tests == [_EXISTING_TEST]
    assert stats["mutants_killed_total"] == 0


def test_strengthen_module_mutations_rejects_coverage_drop(refiner):
    refiner.llm_client.generate_from_prompt.return_value = (
        _PREAMBLE + "\ndef test_fallback_empty():\n    assert module_0.fallback([]) == [0]\n"
    )

    with patch(
        "pynguin.refinement.pipeline.check_coverage_preservation",
        return_value=(False, MagicMock()),
    ):
        _, tests, stats = refiner.strengthen_module_mutations(
            _PREAMBLE, [_EXISTING_TEST], max_iterations=1
        )

    assert tests == [_EXISTING_TEST]
    assert stats["mutants_killed_total"] == 0


_FALLBACK_TEST = """\
def test_fallback():
    # Act
    result = module_0.fallback([])
    # Assert
    assert result"""


def test_strengthen_module_mutations_rejects_weakening_an_existing_test(refiner):
    # test_fallback is tightened (kills the [0] mutants), but test_inc loses the
    # only assertion that kills the inc mutants.
    refiner.llm_client.generate_from_prompt.return_value = (
        _PREAMBLE
        + _EXISTING_TEST.replace("result == 2", "result is not None")
        + "\n\n"
        + _FALLBACK_TEST.replace("assert result", "assert result == [0]")
    )

    _, tests, stats = refiner.strengthen_module_mutations(
        _PREAMBLE, [_EXISTING_TEST, _FALLBACK_TEST], max_iterations=1
    )

    assert tests == [_EXISTING_TEST, _FALLBACK_TEST]
    assert stats["mutants_killed_total"] == 0


def test_strengthen_module_mutations_ignores_unusable_unused_import(refiner):
    refiner.llm_client.generate_from_prompt.return_value = (
        _PREAMBLE
        + "import not_installed_helper\n\n"
        + _EXISTING_TEST
        + "\n\n"
        + _FALLBACK_TEST.replace("assert result", "assert result == [0]")
    )

    preamble, tests, stats = refiner.strengthen_module_mutations(
        _PREAMBLE, [_EXISTING_TEST, _FALLBACK_TEST], max_iterations=1
    )

    assert "not_installed_helper" not in preamble
    assert "assert result == [0]" in tests[1]
    assert stats["mutants_killed_total"] > 0


def test_strengthen_module_mutations_rejects_module_failing_on_clean_sut(refiner):
    # Each test passes on its own, but the new one breaks when run after test_inc,
    # so the module as a whole fails on the clean SUT and "kills" every mutant.
    order_dependent = (
        "def test_fallback_empty():\n"
        "    assert module_0.fallback([]) == [0]\n"
        "    assert 'result' not in module_0.__dict__\n"
    )
    breaking_inc = _EXISTING_TEST + "\n    module_0.result = result"
    refiner.llm_client.generate_from_prompt.return_value = (
        _PREAMBLE + breaking_inc + "\n\n" + order_dependent
    )

    with patch.object(refiner, "_validate_strengthened_test", side_effect=lambda _p, f, _o: f):
        _, tests, stats = refiner.strengthen_module_mutations(
            _PREAMBLE, [_EXISTING_TEST], max_iterations=1
        )

    assert tests == [_EXISTING_TEST]
    assert stats["mutants_killed_total"] == 0


def test_gate1_strips_the_failing_assertion_not_the_first_one(refiner):
    strengthened = _PREAMBLE + _EXISTING_TEST + "\n    assert result > 0\n    assert result == 5\n"

    _, tests = refiner._validate_and_filter_strengthened_functions(
        strengthened, _PREAMBLE, [_EXISTING_TEST]
    )

    assert "assert result > 0" in tests[0]
    assert "result == 5" not in tests[0]
    assert "# Assert" in tests[0]


def test_gate1_discards_failing_new_test(refiner):
    strengthened = (
        _PREAMBLE + _EXISTING_TEST + "\n\n\ndef test_wrong():\n    assert module_0.inc(0) == 9\n"
    )

    _, tests = refiner._validate_and_filter_strengthened_functions(
        strengthened, _PREAMBLE, [_EXISTING_TEST]
    )

    assert tests == [_EXISTING_TEST]


def test_gate1_unparseable_response(refiner):
    assert (
        refiner._validate_and_filter_strengthened_functions("def (", _PREAMBLE, [_EXISTING_TEST])
        is None
    )


def test_gate1_keeps_xfail_tests_and_their_markers(refiner):
    xfail_test = (
        "@pytest.mark.xfail(strict=True)\ndef test_raises():\n    # Act\n    module_0.inc(None)"
    )
    preamble = "import pytest\n" + _PREAMBLE

    _, tests = refiner._validate_and_filter_strengthened_functions(
        preamble + "\n" + xfail_test + "\n", preamble, [xfail_test]
    )

    assert tests == [xfail_test]


def test_refine_generated_tests_dispatches_full_module_strengthening(tmp_path, monkeypatch):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "import sample_module\n\ndef test_0():\n    assert sample_module.f(1) == 2\n"
    )

    monkeypatch.setattr(config.configuration.llm_refinement, "enabled", True)
    monkeypatch.setattr(config.configuration.llm_refinement, "enable_mutation_strengthening", True)
    monkeypatch.setattr(
        config.configuration.llm_refinement,
        "mutation_granularity",
        MutationStrengtheningGranularity.FULL_MODULE,
    )

    mock_mod = types.ModuleType("sample_module")
    mock_mod.__file__ = str(tmp_path / "sample_module.py")

    with (
        patch("pynguin.refinement.refiner._import_module_under_test", return_value=mock_mod),
        patch("pynguin.refinement.refiner._process_module") as mock_process_module,
        patch.object(TestRefiner, "strengthen_module_mutations") as mock_strengthen_mod,
    ):
        outcome = refiner_module._TestOutcome(
            func_text="def test_0():\n    assert sample_module.f(1) == 2\n",
            processed=True,
            refined=True,
            iterations=1,
            readability_original=0.5,
            readability_refined=0.7,
            mutation_stats={},
        )
        mock_process_module.return_value = [outcome]
        mock_strengthen_mod.return_value = (
            "import sample_module\n",
            ["def test_0():\n    assert sample_module.f(1) == 2\n"],
            {"mutants_killed_total": 2},
        )

        stats = refiner_module.refine_generated_tests(test_file, "sample_module")

        mock_strengthen_mod.assert_called_once()
        assert stats["tests_refined"] == 1
