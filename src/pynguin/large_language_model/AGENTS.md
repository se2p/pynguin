<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Large Language Model Integration

<!-- Parent: ../AGENTS.md -->

This directory contains the optional LLM integration for Pynguin, which enhances test generation using OpenAI's language models. This feature requires the `openai` extra to be installed.

**Timestamp:** 2026-01-30

## Overview

The LLM integration provides AI-assisted test generation capabilities:
- Test case generation from module source code
- Assertion generation for existing test cases
- Type inference for function parameters
- Local search for improving branch coverage
- Targeting uncovered callables

## Architecture

### Core Components

- **LLMAgent** (`llmagent.py`): Main interface to OpenAI API
  - Manages API calls with caching and token tracking
  - Sends prompts and extracts Python code from responses
  - Tracks statistics (calls, tokens, timing)
  - Supports multiple prompt types

- **LLMTestCaseHandler** (`llmtestcasehandler.py`): Test case processing
  - Extracts test cases from LLM output
  - Converts LLM-generated code to TestCase chromosomes
  - Integrates with deserializer and rewriter
  - Saves intermediate results for debugging

- **Cache** (`caching.py`): Response caching system
  - File-based cache in `/tmp/pynguin/`
  - SHA-256 hashed keys for safe filenames
  - Optional response caching to reduce API calls

## Subdirectories

### prompts/

Prompt templates for different LLM tasks:

- **Prompt** (`prompt.py`): Abstract base class with system message
  - System message: "You are a unit test generating AI (codename TestGenAI)..."
  - All prompts inherit from this base

- **TestCaseGenerationPrompt**: Generate tests for entire module
  - Input: module source code and path
  - Output: pytest-based test cases

- **AssertionGenerationPrompt**: Add assertions to test cases
  - Input: test case code + module source code
  - Output: test case with assertions

- **TypeInferencePrompt**: Infer parameter types
  - Analyzes function context, imports, docstrings
  - Returns JSON mapping parameter names to types
  - Uses module context and string subtypes

- **LocalSearchPrompt**: Mutate statement for branch coverage
  - Input: test case, position, module code, coverage info
  - Output: modified test case to hit uncovered branches

- **UncoveredTargetsPrompt**: Target specific uncovered callables
  - Input: list of uncovered functions/methods/constructors
  - Output: tests specifically targeting those callables

### parsing/

Parsing and transformation of LLM-generated code:

- **deserializer.py**: Convert AST to Pynguin TestCase objects
  - `StatementDeserializer`: Converts AST nodes to statements
    - Handles assignments, calls, collections, assertions
    - Maintains variable reference dictionary
    - Tracks uninterpreted statements
  - `AstToTestCaseTransformer`: AST visitor for test functions
    - Extracts test functions (starting with `test_`)
    - Supports partial parsing of test cases
    - Tracks parsing statistics

- **rewriter.py**: Rewrite LLM code to Pynguin format
  - `StmtRewriter`: AST transformer for code normalization
    - Extracts sub-expressions into variables
    - Handles control flow (if, for, while, try)
    - Processes comprehensions and lambdas
    - Manages variable scoping
  - `TestClassRewriter`: Transform test classes
    - Extracts setUp variables
    - Removes `self` references
    - Converts class methods to standalone functions

- **helpers.py**: Utility functions
  - `unparse_test_case()`: Convert TestCase to Python code
  - `add_line_numbers()`: Add line numbers to code
  - `has_bound_variables()`: Check variable binding
  - `has_call()`: Detect function calls in AST

- **type_str_parser.py**: Parse type strings (not read but exists)

- **astscoping.py**: AST scoping analysis (not read but exists)

### helpers/

Helper utilities for test case manipulation:

- **testcasereferencecopier.py**: Copy references between test cases
  - `TestCaseReferenceCopier`: Handles reference updates
    - Copies return values, callees, arguments
    - Updates assertion references
    - Maintains reference replacement dictionary
  - Used when cloning or modifying test cases

## Key Features

### Caching System

The file-based cache reduces API costs:
- Cache location: `/tmp/pynguin/`
- Key hashing with SHA-256
- Automatic cache hit detection
- Optional (configurable via `enable_response_caching`)

### Statistics Tracking

Comprehensive LLM usage tracking:
- Total API calls
- Input/output token counts
- Query time (nanoseconds)
- Responses without Python code
- Parsed/unparsed statement counts

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
- `LLMTotalStatements`
- `LLMTotalParsedStatements`
- `LLMUninterpretedStatements`

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
