<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Large Language Model Integration

<!-- Parent: ../AGENTS.md -->

This directory contains the optional LLM integration for Pynguin, which enhances test generation using OpenAI's language models. This feature requires the `openai` extra to be installed.

**Timestamp:** 2026-07-09

## Overview

The LLM integration provides AI-assisted test generation capabilities:
- Test case generation from module source code
- Assertion generation for existing test cases
- Type inference for function parameters
- Local search for improving branch coverage
- Targeting uncovered callables

### Core Components

- **LLMClient & OpenAIClient** (`client.py`): Unified API interfaces
  - `LLMClient`: Abstract base client defining request and response tracking interfaces.
  - `OpenAIClient`: Concrete implementation that communicates with OpenAI via the official SDK, implementing unified retries, backoff, timeout limits, and token tracking.

- **RenderedRequest** (`request.py`): Request value object
  - Encapsulates the messages array, model, temperature, max_tokens, and stop parameters.
  - Generates reproducible cache key hashes representing the request.

- **LLMAgent** (`llmagent.py`): High-level task wrapper
  - Orchestrates API queries for test generation, uncovered targets, and assertion extraction.
  - Extracts Python code from responses, increments stats, and records debug logs.

- **LLMTestCaseHandler** (`llmtestcasehandler.py`): Test case processing
  - Extracts test cases from LLM output.
  - Converts LLM-generated code to TestCase chromosomes.
  - Integrates with deserializer and rewriter.
  - Saves intermediate results for debugging.

- **LLMCache** (`cache.py`): Hashed caching system
  - Correct, reproducible file-based caching under `~/.cache/pynguin/llm/`.
  - Keys on hashes computed from `RenderedRequest` values.
  - Enabled/disabled via `enable_response_caching` config.

## Subdirectories

### prompts/

Jinja2 prompt templates configured via YAML files:

- **Prompt** (`prompt.py`): Base prompt class loading YAML resources
  - Automatically loads configs from `resources/<prompt_name>.yaml`.
  - Performs runtime validation asserting that templates only use declared variables.
  - Renders strict Jinja2 messages (system and user prompt).

- **Prompt Configurations** (`resources/*.yaml`): YAML templates specifying:
  - `system_message_template`: System role prompt template.
  - `user_message_template`: User request prompt template.
  - `temperature` / `max_tokens` / `stop` / `model` overrides.

- **Prompt Subclasses**:
  - `TestCaseGenerationPrompt`
  - `AssertionGenerationPrompt`
  - `UncoveredTargetsPrompt`
  - `LocalSearchPrompt`
  - `BaseInferencePrompt` -> `TypeInferencePrompt` and `TypeAndSubtypeInferencePrompt`

### parsing/

Parsing and transformation of LLM-generated code. The internal representation
is libcst-backed (`pynguin.testcase.testcase.TestCase`/`Statement`), so
deserialization is "parse + validate + normalize" rather than reconstructing a
separate statement class hierarchy or `VariableReference` graph.

- **deserializer.py**: Convert LLM-emitted source to Pynguin `TestCase` objects
  - `Disposition` (enum): how a single statement was handled; every statement
    is tagged with exactly one member (see `parsing/AGENTS.md`)
  - `ParseStatus` (enum): `OK` or `UNPARSEABLE`
  - `DeserializationResult` (dataclass): `test_cases`, `status: ParseStatus`,
    `counts: Counter[Disposition]`
  - `deserialize_code_to_testcases(test_file_contents, test_cluster, *,
    create_assertions=None) -> DeserializationResult`: runs `rewrite_tests()`,
    then libcst-parses the result and deserializes every top-level
    `test_*`/`seed_test_*` function; returns a result with `status=UNPARSEABLE`
    only if the rewritten source cannot be parsed as libcst at all
  - `CstStatementDeserializer(test_cluster, *, create_assertions)`: per-test-
    function parser (`deserialize_function`)
    - Resolves calls against `test_cluster.accessible_objects_under_test`
      (`GenericConstructor`/`GenericMethod`/`GenericFunction`)
    - Renames bound variables to fresh `var_N` names, consistently across
      both the binding statement's own target and all later references
    - Normalizes SUT imports/references to the canonical
      `<module_alias>.member` form; drops the import lines
    - Lifts supported `assert` shapes into `Assertion` objects via
      `parse_assertion()`
  - `parse_assertion(node, known_vars)`: module-level, shared with
    `pynguin.assertion.llmassertiongenerator`; supports bare-name,
    equality/`is`-with-literal, `isinstance`, `len(...) ==`, and `or`-split
    assert shapes

- **rewriter.py**: Rewrite LLM code to Pynguin format
  - `StmtRewriter`: AST transformer for code normalization
    - Extracts sub-expressions into variables (including hoisting literal
      list/dict/set/tuple elements into separate assignments)
    - Handles control flow (if, for, while, try)
    - Processes comprehensions and lambdas
    - Manages variable scoping
  - `TestClassRewriter`: Transform test classes
    - Extracts setUp variables
    - Removes `self` references
    - Converts class methods to standalone functions

- **helpers.py**: Utility functions (`unparse_test_case()` was removed;
  rendering now goes through `TestCase.to_code()`/`to_test_function()`)
  - `add_line_numbers()`: Add line numbers to code
  - `has_bound_variables()`: Check variable binding
  - `has_call()`: Detect function calls in AST

- **type_str_parser.py**: Parse type strings

## Key Features

### Caching System

The file-based cache reduces API costs and provides deterministic results:
- Cache location: `~/.cache/pynguin/llm/`
- Key hashing based on SHA-256 hash of `RenderedRequest` values
- Automatic cache hit detection
- Optional (configurable via `enable_response_caching`)

### Statistics Tracking

Comprehensive LLM usage tracking:
- Total API calls
- Input/output token counts
- Query time (nanoseconds)
- Responses without Python code
- Per-`Disposition` statement counts (admitted/dropped/assertion buckets)

### Code Transformation Pipeline

1. **LLM Output** → Extract Python code blocks
2. **Rewriting** → Normalize to Pynguin format
3. **Deserialization** → Convert to TestCase objects
4. **Integration** → Add to population as chromosomes

### Prompt Engineering

All prompts use TestGenAI persona:
- "Senior test automation engineer with ISTQB certificate"
- Focuses on boundary value analysis and corner cases
- Aims for high coverage

## Integration Points

### Configuration

Uses `config.configuration.large_language_model.*`:
- `model_name`: OpenAI model to use
- `temperature`: Sampling temperature
- `enable_response_caching`: Cache responses

### Test Cluster

Requires `TestCluster` for deserialization:
- Provides accessible objects under test
- Type system for inference
- Module context

### Statistics

Tracks to `RuntimeVariable`:
- `TotalLLMCalls`
- `LLMQueryTime`
- `TotalLLMInputTokens`
- `TotalLLMOutputTokens`
- `TotalCodelessLLMResponses`
- `LLMAdmitted`
- `LLMAdmittedUnresolvedCall`
- `LLMAdmittedImport`
- `LLMAdmittedCompound`
- `LLMDroppedUnknownNames`
- `LLMDroppedUnsupportedShape`
- `LLMAssertionLifted`
- `LLMAssertionKeptRaw`
- `LLMAssertionDropped`

## Debugging Support

Multiple output files for debugging:
- `llm_query_results.txt`: Raw LLM responses
- `rewritten_llm_test_cases.py`: After rewriting
- `deserializer_llm_test_cases.py`: After deserialization
- `prompt_info.txt`: Prompt-response log with timestamps

## Error Handling

- Graceful handling of parsing failures
- Partial test case extraction
- Fallback for missing objects
- Logging at multiple levels (debug, info, error)

## Dependencies

- `openai`: OpenAI Python client (optional)
- `ast`: Python AST manipulation
- `inspect`: Source code introspection
- Pynguin core: testcase, assertion, analyses modules

## Usage Flow

1. **Generate**: LLMAgent queries OpenAI with prompt
2. **Extract**: Extract Python code from markdown
3. **Rewrite**: Transform to Pynguin-compatible format
4. **Deserialize**: Parse into TestCase objects
5. **Integrate**: Add as chromosomes to population
6. **Evolve**: Use in evolutionary algorithm

## Related Modules

- `pynguin.ga`: Genetic algorithm integration
- `pynguin.testcase`: Test case representation
- `pynguin.assertion`: Assertion framework
- `pynguin.analyses.module`: Module analysis and TestCluster
