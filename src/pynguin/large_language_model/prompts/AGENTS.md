<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# LLM Prompts

<!-- Parent: ../AGENTS.md -->

Prompt templates for different LLM-based test generation tasks.

**Timestamp:** 2026-01-30

## Overview

This module defines specialized prompts for various LLM tasks in test generation. All prompts inherit from a base class with a standardized system message.

## Key Components

### prompt.py

**Prompt**: Abstract base class for all LLM prompts
- System message: "You are a unit test generating AI (codename TestGenAI)..."
- Persona: Senior test automation engineer with ISTQB certificate
- Focus: Boundary value analysis, corner cases, high coverage
- All task-specific prompts inherit from this base

## Prompt Types

### TestCaseGenerationPrompt

Generates pytest-based test cases for entire modules.
- Input: Module source code and file path
- Output: Standalone pytest test cases
- Purpose: Create initial test suite from module

### AssertionGenerationPrompt

Adds assertions to existing test cases.
- Input: Test case code + module source code
- Output: Test case enhanced with assertions
- Purpose: Improve existing tests with verification

### TypeInferencePrompt

Infers parameter types for function arguments.
- Analysis: Function context, imports, docstrings
- Output: JSON mapping parameter names to types
- Features: Module context awareness, string subtype handling
- Purpose: Type-aware test data generation

### LocalSearchPrompt

Mutates test statements for branch coverage improvement.
- Input: Test case, statement position, module code, coverage info
- Output: Modified test case to hit uncovered branches
- Purpose: Targeted coverage improvement

### UncoveredTargetsPrompt

Generates tests targeting specific uncovered callables.
- Input: List of uncovered functions/methods/constructors
- Output: Tests specifically targeting those callables
- Purpose: Coverage-guided test generation

### Refinement Prompts (per-test)

Used by `pynguin.refinement.pipeline` on one test function at a time.
- **ReadabilityRefinementPrompt**: semantic naming + AAA restructuring (vars:
  `sut_context`, `focal_method`, `test_code`).
- **SemanticAssertionsPrompt**: infer behavior-based assertions (same vars).
- **RepairPrompt** / **MutationStrengthenPrompt**: fix broken tests / strengthen
  assertions against surviving mutants.

### Module-Level Refinement Prompts

Used by `pynguin.refinement.refiner` when `llm_refinement.refinement_granularity` is
`combined` or `module_separate`.  Each takes the **whole** test module in one request
(vars: `module_test_code`, `sut_context`) and has a raised `max_tokens` (8000) for
whole-module output.  All three demand that every test function keep its **exact original
name** so the refiner can split the response back and map functions by name.
- **ModuleReadabilityRefinementPrompt**: readability of all tests (readability stage of
  `module_separate`).
- **ModuleSemanticAssertionsPrompt**: assertions for all tests (assertion stage of
  `module_separate`).
- **ModuleRefinementPrompt**: readability **and** assertions in a single pass
  (`combined`, the default).

## Usage Context

Called by:
- `llmagent.py`: Main interface for sending prompts to OpenAI
- `llmtestcasehandler.py`: Integration with test case processing

## Related Modules

- Parent: `pynguin.large_language_model`
- Sibling: `parsing/`, `helpers/`
- Consumer: `llmagent.py`, `llmtestcasehandler.py`
