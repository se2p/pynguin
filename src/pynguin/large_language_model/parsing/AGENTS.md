<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# LLM Parsing

<!-- Parent: ../AGENTS.md -->

Parsing and transformation of LLM-generated code into Pynguin test cases.

**Timestamp:** 2026-07-09

## Overview

This module converts LLM-generated Python code into Pynguin's internal
libcst-backed `TestCase`/`Statement` representation (`pynguin.testcase.testcase`)
through AST-level rewriting (`rewriter.py`) followed by libcst-level parsing and
validation (`deserializer.py`). Because the internal representation stores
libcst statement nodes directly instead of a separate class hierarchy
(`IntPrimitiveStatement`, `MethodStatement`, ...) or a `VariableReference`
graph, deserialization is mostly "parse + validate + normalize" rather than
"reconstruct an object graph".

## Key Components

### deserializer.py

- **`DeserializationResult`** (dataclass): the outcome of deserializing a
  chunk of LLM-emitted source — `test_cases: list[TestCase]`,
  `total_statements`, `parsed_statements`, `uninterpreted_statements`.
- **`deserialize_code_to_testcases(test_file_contents, test_cluster, *,
  create_assertions=None) -> DeserializationResult | None`**: the main entry
  point. Runs `rewrite_tests()` first, then `cst.parse_module`s the joined
  result and hands every top-level `test_*`/`seed_test_*` `FunctionDef` to a
  `CstStatementDeserializer`. Returns `None` only if the rewritten source
  cannot be parsed as libcst at all; a test function that admits zero
  statements is simply dropped rather than causing a `None` return.
  `create_assertions` defaults to whether
  `config.configuration.test_case_output.assertion_generation ==
  AssertionGenerator.LLM`.
- **`CstStatementDeserializer(test_cluster, *, create_assertions)`**: per-test-
  function parser.
  - `deserialize_function(fn) -> (TestCase, total, parsed, uninterpreted)`
    walks the (already rewriter-normalized and SUT-alias-normalized) function
    body. Only `SimpleStatementLine` children are admitted; compound
    statements (`if`/`for`/`with`/...) are dropped outright.
  - `Assign` with a single `Name` target: the bound type is inferred either
    from a literal RHS (`ast.literal_eval`) or by resolving a `Call` against
    `test_cluster.accessible_objects_under_test`
    (`GenericConstructor`/`GenericMethod`/`GenericFunction`); an unresolved
    call is still admitted as raw CST but counted as "uninterpreted".
  - Statements that read names outside the current scope (builtins ∪
    `{"pytest"}` ∪ the SUT module alias ∪ `vars()` of the imported SUT module
    ∪ accessible-object names ∪ previously bound variables ∪ names bound by
    kept non-SUT imports) are dropped.
  - Every bound variable is renamed to a fresh `var_N` name
    (`TestCase.next_var_name()`); later references — and the binding
    statement's *own* assignment target — are renamed consistently via
    `_LocalRenamer`, so the emitted code never references a stale
    pre-rename name.
  - `import <sut_module> [as m]` / `from <sut_module> import f [as g]` lines
    are removed and rewritten to `<module_alias>.member` references
    (`_SutReferenceNormalizer`, alias from `pynguin.utils.naming.
    get_module_alias`). Non-SUT imports are kept as raw statements and bind
    their local names into scope.
  - `assert` statements are lifted into `Assertion` objects (appended to the
    statement that bound the asserted variable) via the shared
    `parse_assertion()` helper when `create_assertions` is set; unsupported
    shapes are kept as raw (renamed) statements when every referenced name is
    already known, otherwise dropped. `assert` never contributes to
    `total_statements`.
- **`parse_assertion(node: cst.Assert | str, known_vars: Mapping[str, type |
  None]) -> tuple[str, Assertion] | None`**: module-level and shared with
  `pynguin.assertion.llmassertiongenerator`. Supports `assert x` (bare name),
  `assert x == <literal>`/`assert x is <literal>`, `assert isinstance(x, T)`,
  `assert len(x) == n`, and `assert a or b` (tries each operand). Internally
  dispatches to small per-shape parser functions
  (`_parse_bare_name_assertion`, `_parse_isinstance_assertion`,
  `_parse_len_equality_assertion`, `_parse_equality_literal_assertion`) to
  keep each shape's logic isolated and easy to extend.

### rewriter.py

**StmtRewriter**: AST transformer for code normalization

- Extracts sub-expressions into variables (including hoisting list/dict/set/
  tuple literal elements into separate assignments — this means a literal
  collection assign like `e = [1, 2]` typically arrives at the deserializer
  as `var_0 = 1; var_1 = 2; e = [var_0, var_1]`, so its RHS is no longer a
  pure literal by the time `deserializer.py` sees it)
- Handles control flow (if, for, while, try statements)
- Processes comprehensions and lambda expressions
- Manages variable scoping and references

**TestClassRewriter**: Transform test classes to standalone format

- Extracts setUp method variables
- Removes `self` references
- Converts class methods to standalone functions
- Flattens class-based test structure

### helpers.py

Utility functions (the old `unparse_test_case()` was removed — rendering now
goes through `TestCase.to_code()`/`TestCase.to_test_function()` directly):

- `add_line_numbers()`: Add line numbers to code
- `has_bound_variables()`: Check variable binding
- `has_call()`: Detect function calls in AST
- `is_expr_or_stmt()`: Whether an AST node is an expression or statement
- `key_in_dict()`: Safe membership check that doesn't conflate `True`/`1`
- `_count_all_statements()`: Count non-assert AST statements (internal)

### type_str_parser.py

Type string parsing utilities for inference results.

## Transformation Pipeline

1. **LLM Output** → Extract Python code blocks
2. **Rewriting** (`rewrite_tests`) → Normalize to Pynguin format (flatten
   classes, extract sub-expressions/hoist literals)
3. **Deserialization** (`deserialize_code_to_testcases`) → Parse into
   `TestCase`/`Statement` objects, resolving calls, renaming variables to
   `var_N`, and lifting supported `assert`s into `Assertion`s
4. **Integration** → Add as chromosomes to population

## Usage Context

Called by:

- `llmtestcasehandler.py`: Main integration point
  (`get_test_case_chromosomes_from_llm_results`)
- `pynguin.assertion.llmassertiongenerator`: reuses `parse_assertion()` to
  turn LLM-generated `assert` lines (for an already-deserialized test case)
  into `Assertion` objects, without re-running the whole deserializer

## Related Modules

- Parent: `pynguin.large_language_model`
- Sibling: `helpers/`, `prompts/`
- `pynguin.testcase.testcase`: the `TestCase`/`Statement` target representation
