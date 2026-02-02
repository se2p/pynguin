<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# LLM Parsing

<!-- Parent: ../AGENTS.md -->

Parsing and transformation of LLM-generated code into Pynguin test cases.

**Timestamp:** 2026-01-30

## Overview

This module converts LLM-generated Python code into Pynguin's internal TestCase representation through AST parsing, rewriting, and deserialization.

## Key Components

### deserializer.py

**StatementDeserializer**: Converts AST nodes to Pynguin statements
- Handles assignments, function calls, collections, and assertions
- Maintains variable reference dictionary
- Tracks uninterpreted statements
- Supports partial parsing fallback

**AstToTestCaseTransformer**: AST visitor for test functions
- Extracts test functions (naming pattern: `test_*`)
- Converts test function bodies to TestCase objects
- Tracks parsing statistics
- Supports partial parsing with partial results

### rewriter.py

**StmtRewriter**: AST transformer for code normalization
- Extracts sub-expressions into variables
- Handles control flow (if, for, while, try statements)
- Processes comprehensions and lambda expressions
- Manages variable scoping and references

**TestClassRewriter**: Transform test classes to standalone format
- Extracts setUp method variables
- Removes `self` references
- Converts class methods to standalone functions
- Flattens class-based test structure

### helpers.py

Utility functions:
- `unparse_test_case()`: Convert TestCase to Python code
- `add_line_numbers()`: Add line numbers to code
- `has_bound_variables()`: Check variable binding
- `has_call()`: Detect function calls in AST

### type_str_parser.py

Type string parsing utilities for inference results.

### astscoping.py

AST scope analysis for variable tracking.

## Transformation Pipeline

1. **LLM Output** → Extract Python code blocks
2. **Rewriting** → Normalize to Pynguin format (flatten classes, extract expressions)
3. **Deserialization** → Convert AST to TestCase objects
4. **Integration** → Add as chromosomes to population

## Usage Context

Called by:
- `llmtestcasehandler.py`: Main integration point
- `llmagent.py`: After receiving LLM response

## Related Modules

- Parent: `pynguin.large_language_model`
- Sibling: `helpers/`, `prompts/`
