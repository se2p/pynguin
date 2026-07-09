<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# LLM Helpers

<!-- Parent: ../AGENTS.md -->

Helper utilities for LLM integration test case manipulation.

**Timestamp:** 2026-07-09

## Overview

This package is currently empty apart from `__init__.py`. It previously held
`testcasereferencecopier.py` (`TestCaseReferenceCopier`), which copied
`VariableReference`-graph references between `DefaultTestCase` instances. That
class-based test-case representation was replaced by the libcst-backed
`pynguin.testcase.testcase.TestCase`/`Statement` model, whose statements
reference each other purely by variable-name string (`Statement.bound_variable`,
`Statement.used_variables()`), so no separate reference-graph copying step is
needed any more: copying/renaming statements between test cases is handled
directly by `TestCase.append_test_case`/`append_test_case_from` (see
`pynguin.testcase.testcase`), and `TestCase.clone()` deep-copies statements
(including their `assertions`) without any reference rewriting.

## Related Modules

- Parent: `pynguin.large_language_model`
- Sibling: `parsing/`, `prompts/`
