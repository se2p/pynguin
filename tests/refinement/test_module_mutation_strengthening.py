#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Tests for module-level mutation-driven assertion strengthening."""

from __future__ import annotations

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


def _dummy_module() -> types.ModuleType:
    mod = types.ModuleType("dummy_sut")
    mod.__file__ = "/fake/dummy_sut.py"
    return mod


@pytest.fixture
def fake_refiner():
    refiner = TestRefiner(module_under_test=_dummy_module())
    refiner.llm_client = MagicMock()
    return refiner


def test_strengthen_module_mutations_no_survivors(fake_refiner):
    preamble = "import dummy_sut as module_0\n"
    tests = ["def test_0():\n    assert module_0.f(1) == 2\n"]

    with patch("pynguin.refinement.pipeline.get_surviving_mutants", return_value=[]):
        p_out, t_out, stats = fake_refiner.strengthen_module_mutations(
            preamble=preamble,
            refined_tests=tests,
            max_iterations=1,
        )

    assert p_out == preamble
    assert t_out == tests
    assert stats["mutants_killed_total"] == 0
    fake_refiner.llm_client.generate_from_prompt.assert_not_called()


def test_strengthen_module_mutations_chunks_survivors_by_max_mutants_per_prompt(fake_refiner):
    preamble = "import dummy_sut as module_0\n"
    tests = ["def test_0():\n    assert module_0.f(1) == 2\n"]

    # Create 5 fake mutant tuples: (mutant_module, [mutation_obj])
    def make_fake_mutant(line: int):
        m = MagicMock()
        m.operator.__name__ = "ArithmeticOperatorReplacement"
        m.node = MagicMock()
        m.node.lineno = line
        m.replacement_node = MagicMock()
        return (MagicMock(), [m])

    mutants_list = [make_fake_mutant(i) for i in range(1, 6)]

    llm_response = (
        "import dummy_sut as module_0\n\n"
        "def test_0():\n"
        "    # Assert\n"
        "    assert module_0.f(1) == 2\n"
        "    assert module_0.f(1) > 0\n"
    )
    fake_refiner.llm_client.generate_from_prompt.return_value = llm_response

    with (
        patch("pynguin.refinement.pipeline.get_surviving_mutants", return_value=mutants_list),
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, MagicMock()),
        ),
        patch(
            "pynguin.refinement.pipeline._killed_set",
            side_effect=[set(), {0}, set(), {0}, set(), {0}],
        ),
        patch("inspect.getsource", return_value="def f(x): return x + 1"),
    ):
        _, _, _ = fake_refiner.strengthen_module_mutations(
            preamble=preamble,
            refined_tests=tests,
            max_iterations=1,
            max_mutants_per_prompt=2,
        )

    # 5 mutants chunked by 2 -> 3 chunks -> 3 prompt calls
    assert fake_refiner.llm_client.generate_from_prompt.call_count == 3
    # Every call used ModuleMutationStrengthenPrompt
    for call_args in fake_refiner.llm_client.generate_from_prompt.call_args_list:
        prompt_arg = call_args[0][0]
        assert isinstance(prompt_arg, ModuleMutationStrengthenPrompt)


def test_strengthen_module_mutations_gate1_accepts_green_boundary_test(fake_refiner):
    preamble = "import dummy_sut as module_0\n"
    tests = ["def test_0():\n    assert module_0.f(1) == 2\n"]

    mutant = MagicMock()
    mutant.operator.__name__ = "RelationalOperatorReplacement"
    mutant.node.lineno = 10
    mutants_list = [(MagicMock(), [mutant])]

    # LLM added a new boundary test test_boundary_empty()
    llm_response = (
        "import dummy_sut as module_0\n\n"
        "def test_0():\n"
        "    assert module_0.f(1) == 2\n\n"
        "def test_boundary_empty():\n"
        "    assert module_0.f(0) == 1\n"
    )
    fake_refiner.llm_client.generate_from_prompt.return_value = llm_response

    with (
        patch("pynguin.refinement.pipeline.get_surviving_mutants", return_value=mutants_list),
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, MagicMock()),
        ),
        patch("pynguin.refinement.pipeline._killed_set", side_effect=[set(), {0}]),
        patch("inspect.getsource", return_value="def f(x): return x + 1"),
    ):
        _, updated_tests, _ = fake_refiner.strengthen_module_mutations(
            preamble=preamble,
            refined_tests=tests,
            max_iterations=1,
        )

    assert len(updated_tests) == 2
    assert any("test_boundary_empty" in t for t in updated_tests)


def test_strengthen_module_mutations_gate1_discards_failing_boundary_test(fake_refiner):
    preamble = "import dummy_sut as module_0\n"
    tests = ["def test_0():\n    assert module_0.f(1) == 2\n"]

    mutant = MagicMock()
    mutant.operator.__name__ = "RelationalOperatorReplacement"
    mutant.node.lineno = 10
    mutants_list = [(MagicMock(), [mutant])]

    # LLM added a failing boundary test
    llm_response = (
        "import dummy_sut as module_0\n\n"
        "def test_0():\n"
        "    assert module_0.f(1) == 2\n\n"
        "def test_hallucinated_boundary():\n"
        "    assert module_0.f(0) == 999\n"
    )
    fake_refiner.llm_client.generate_from_prompt.return_value = llm_response

    def fake_run_test(code, _mod):
        if "test_hallucinated_boundary" in code:
            return False, "AssertionError: assert 1 == 999"
        return True, "Test passed."

    with (
        patch("pynguin.refinement.pipeline.get_surviving_mutants", return_value=mutants_list),
        patch("pynguin.refinement.pipeline.run_test", side_effect=fake_run_test),
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(True, MagicMock()),
        ),
        patch("pynguin.refinement.pipeline._killed_set", side_effect=[set(), {0}]),
        patch("inspect.getsource", return_value="def f(x): return x + 1"),
    ):
        _, updated_tests, _ = fake_refiner.strengthen_module_mutations(
            preamble=preamble,
            refined_tests=tests,
            max_iterations=1,
        )

    # Failing new test was discarded! Only test_0 remains.
    assert len(updated_tests) == 1
    assert "test_hallucinated_boundary" not in updated_tests[0]


def test_strengthen_module_mutations_gate2_rejects_coverage_drop(fake_refiner):
    preamble = "import dummy_sut as module_0\n"
    tests = ["def test_0():\n    assert module_0.f(1) == 2\n"]

    mutant = MagicMock()
    mutant.operator.__name__ = "ArithmeticOperatorReplacement"
    mutant.node.lineno = 5
    mutants_list = [(MagicMock(), [mutant])]

    llm_response = "import dummy_sut as module_0\n\ndef test_0():\n    pass\n"
    fake_refiner.llm_client.generate_from_prompt.return_value = llm_response

    with (
        patch("pynguin.refinement.pipeline.get_surviving_mutants", return_value=mutants_list),
        patch("pynguin.refinement.pipeline.run_test", return_value=(True, "Test passed.")),
        # Coverage drops -> returns False
        patch(
            "pynguin.refinement.pipeline.check_coverage_preservation",
            return_value=(False, MagicMock()),
        ),
        patch("inspect.getsource", return_value="def f(x): return x + 1"),
    ):
        _, updated_tests, stats = fake_refiner.strengthen_module_mutations(
            preamble=preamble,
            refined_tests=tests,
            max_iterations=1,
        )

    # Rejected due to coverage drop, tests unchanged
    assert updated_tests == tests
    assert stats["mutants_killed_total"] == 0


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
