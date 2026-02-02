<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# LLM Helpers

<!-- Parent: ../AGENTS.md -->

Helper utilities for LLM integration test case manipulation.

**Timestamp:** 2026-01-30

## Overview

This module provides utility functions for copying and manipulating test case references during LLM-based test generation.

## Key Components

### testcasereferencecopier.py

**TestCaseReferenceCopier**: Handles reference updates between test cases
- Copies return values, callees, and arguments
- Updates assertion references
- Maintains reference replacement dictionary
- Used when cloning or modifying test cases from LLM output

## Usage Context

Referenced by:
- `llmtestcasehandler.py`: When integrating LLM-generated test cases
- Deserialization pipeline: During test case transformation

## Related Modules

- Parent: `pynguin.large_language_model`
- Sibling: `parsing/`, `prompts/`
