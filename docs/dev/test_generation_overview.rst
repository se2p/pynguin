.. _test_generation_overview:

Test Generation Overview
=======================

This document provides a high-level overview of how Pynguin's test generation works. It covers the key components and processes involved in generating test cases for Python modules.

Genetic Algorithm
-----------------
A good reference is the `SBSE 2024 repository`_, which contains Jupyter notebooks on search-based test generation:

* `Search-Based Test Generation - Part 1`_: Introduction to search-based test generation
* `Search-Based Test Generation - Part 2`_: Advanced topics in search-based test generation

Pynguin's Test Generation Process
-----------------------

.. image:: ../source/_static/pynguin-overview.png

Function Analysis
~~~~~~~~~~~~~~~~

Before generating tests, Pynguin analyzes the code to build a test cluster containing all accessible objects:

**Module Test Cluster**: The :class:`pynguin.analyses.module.ModuleTestCluster` class maintains a collection of accessible objects under test

- Objects are added via :meth:`pynguin.analyses.module.ModuleTestCluster.add_accessible_object_under_test`

**Analysis Process**: The module analysis is performed by several functions:

- ``__analyse_class``: Analyzes a class using AST generation, including type annotations if available
- ``__analyse_included_classes``: Processes all classes in a module
- ``__resolve_dependencies``: Identifies dependencies between modules
- :func:`pynguin.analyses.module.analyse_module`: Entry point for module analysis

Goals, Coverage, and Instrumentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pynguin uses code instrumentation to track coverage and guide the test generation process:

**Ignoring Code**: The :attr:`pynguin.configuration.Configuration.ignore_methods` and :attr:`pynguin.configuration.Configuration.ignore_modules` options create a blacklist that prevents analysis and inclusion in the test cluster

- This is useful for code that should not be executed
- Not suitable for code that should be accessible but not covered

Fitness and Distance Calculation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To guide the search for test cases, Pynguin uses fitness functions and distance metrics:

- The :class:`pynguin.instrumentation.tracer.ExecutionTracer` instruments conditional jumps
- For equality comparisons, Levenshtein distance is used
- Support for other comparisons (``<``, ``>``) is limited
- String comparison uses character-based distance metrics

Assertion Generation through Mutation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pynguin generates assertions by applying mutations to the code under test:

The process involves:

- :class:`pynguin.assertion.assertiongenerator.InstrumentedMutationController` which coordinates the mutation process
- :class:`pynguin.assertion.mutation_analysis.controller.MutationController` that creates mutants
- :class:`pynguin.assertion.mutation_analysis.mutators.FirstOrderMutator` that applies mutations to the code

- This approach allows Pynguin to generate assertions for complex data types by observing how mutations affect the program's behavior

Dynamic Seeding
--------------

Dynamic seeding helps Pynguin generate effective test inputs by collecting values from the code under test:

**Instrumentation**: The :class:`pynguin.instrumentation.instrumentation.DynamicSeedingInstrumentation` class:

- Instruments comparison operations (:meth:`pynguin.instrumentation.instrumentation.DynamicSeedingInstrumentation._instrument_compare_op`)
- Adds values from both sides of equality comparisons
- Handles string operations like ``.endswith()`` and ``.startswith()``

Type Analysis
------------

Type Inference
~~~~~~~~~~~~~

Pynguin uses a sophisticated type inference system to determine the types of parameters and return values for functions and methods. This is crucial for generating appropriate test inputs.

The type inference process involves:

**Inferred Signatures**: The :class:`pynguin.analyses.typesystem.InferredSignature` class handles the inference of parameter and return types.

- :meth:`pynguin.analyses.typesystem.InferredSignature._guess_parameter_type_from` and :meth:`pynguin.analyses.typesystem.InferredSignature.get_parameter_type` methods update guesses based on usage traces
- These methods add possible type guesses to a pool where a random choice is made

**Type System**: The inference process is managed by the :class:`pynguin.analyses.typesystem.TypeSystem` class:
- :meth:`pynguin.analyses.typesystem.TypeSystem.infer_type_info` method determines type information based on the selected strategy
- :meth:`pynguin.analyses.typesystem.TypeSystem.infer_signature` method creates an inferred signature for a callable

Type Tracing
~~~~~~~~~~~

Pynguin executes each test case twice to refine parameter types:

- The :class:`pynguin.testcase.execution.TypeTracingTestCaseExecutor` class delegates to another executor
- First execution: For regular results
- Second execution: With proxies to refine parameter types
- The :class:`pynguin.testcase.execution.TypeTracingObserver` monitors execution to collect type information

When Type Tracing is enabled, the system uses :class:`pynguin.analyses.typesystem.UsageTraceNode` objects that contain information about:

- Type checks performed
- Argument types observed
- Child nodes in the execution tree

.. _SBSE 2024 repository: https://github.com/se2p/sbse2024
.. _Search-Based Test Generation - Part 1: https://github.com/se2p/sbse2024/blob/main/Search-Based%20Test%20Generation%20-%20Part%201.ipynb
.. _Search-Based Test Generation - Part 2: https://github.com/se2p/sbse2024/blob/main/Search-Based%20Test%20Generation%20-%20Part%202.ipynb
