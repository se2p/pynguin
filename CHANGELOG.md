<!--
SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Pynguin Changelog

Please also check the [GitHub Releases Page](https://github.com/se2p/pynguin/releases)
for the source-code artifacts of each version.

## Pynguin 0.17.0

## Pynguin 0.16.0

- Refactor the assertion generation.  This unifies the `SIMPLE` and the 
  `MUTATION_ANALYSIS` approaches.  Furthermore, Pynguin now uses the 
  `MUTATION_ANALYSIS` approach again as the default.
- Update the type annotations in Pynguin's code to the simplified, future versions 
  (e.g. instead of `Dict[str, Set[int]]` we can now write `dict[str, set[int]]`) and do
  not need any imports from Python's `typing` module.
- Fix a crash of the seeding when native modules are present.  Fixes #20.
- Provide a hint in the documentation that PyCharm 2021.3 now integrates `poetry` 
  support, thus no plugin is required for this (and newer) versions (thanks to 
  @labrenz).

## Pynguin 0.15.0

- Fix a bug for mutating a statement that is not in the current test case (see #17).
- Set default assertion generation to `SIMPLE` due to issues with the experimental 
  new generation strategy.
- Add GitHub Actions that also runs our CI chain on GitHub.

## Pynguin 0.14.0

- *Breaking:* Simplify the logging such that Pynguin uses different log levels also 
  for the log file.  This removes the `-q` option to make all outputs quiet.
- Pynguin now also supports field accesses during test generation.  This is a 
  preliminary feature.
- Fix a deadlock in the executor
- Pynguin now uses Python 3.10 as its default version for the provided Docker 
  container as well as our CI.  Still, Pynguin supports Python 3.8 and 3.9.  Up to now,
  Python 3.11 is not yet supported.
- Refactor the state-trace implementation
- Remove the module-loader singleton
- Fix loading of mutated module for assertion generation.  Caused that no assertion 
  was generated because the mutants were not loaded properly.  This is a regression 
  from merging the assertion-generation strategy in Pynguin 0.13.0.

## Pynguin 0.13.2

- Add the reference to the preprint of our EMSE journal submission to documentation.
- Clarify on the value of the `PYNGUIN_DANGER_AWARE` environment variable.  One can 
  set an arbitrary value for the variable, Pynguin only checks whether its defined.

## Pynguin 0.13.1

- Fix documentation generation by adding our MutPy fork as a dependency

## Pynguin 0.13.0

- Add an assertion-generation strategy based on mutation (thanks to @f-str).

  The new strategy is enabled by default (can be configured using the 
  `--assertion-generation` parameter).  It uses a custom
  [fork](https://github.com/se2p/mutpy-pynguin) of the mutation-testing framework
  [MutPy](https://github.com/mutpy/mutpy), which mutates the subject under test and for
  each mutant traces the values of fields and returned by method calls.  If these values
  differ between mutant and original code, an assertion is generated based on the result
  on the original subject under test.  One can also control whether the strategy shall
  also generate assertions for unchanged values by the `--generate-all-assertions` flag.

  The release also updates the documentation accordingly.

  *Note:* This feature is an early prototype of such an assertion generation, which 
  might cause unexpected behaviour.  You can switch back to the previous strategy for
  assertion generation by setting `--assertion-generation SIMPLE`.

## Pynguin 0.12.0

- Generate more reasonable variable names in tests.
  Before this release, Pynguin only generated variables named `var0`, `var1`, etc.
  A simple heuristics now attempts to generate more reasonable names depending on the
  type of the variable, such as `int_0`, `bool_1`, or `str_2`.
  We also adjusted the documentation to match this change.
- We updated all provided PyCharm run configurations the use the more sophisticated
  queue example instead of the simple example module to see an improved output.
- Prevent a potential regression when updating the dependencies to version 0.0.17 of the
  [simple-parsing](https://pypi.org/project/simple-parsing) library for CLI argument
  parsing, which changed its API.

## Pynguin 0.11.0

- Fix a control-dependency bug in DynaMOSA.  Loops in the control-dependence graph 
  caused DynaMOSA to not consider certain targets because they were control 
  dependent on goals that had not yet been covered due to the loop.
- Improve documentation
- Split and extend `FitnessValues` to avoid expensive re-computations.  This also 
  extends the API of the `FitnessValues` and refactors large parts of the fitness 
  handling.
- Fix for bumpiness of flaky tests.  Whenever Pynguin generates a test that behaves 
  flaky result could be that coverage over time looks like ventricular fibrillation 
  especially for the MIO algorithm.  The fix prevents this by carefully revisiting 
  the equality of chromosomes.
- Improve handling of entry/exit nodes in the CFG; this fixes issues with Python 3.10

## Pynguin 0.10.0

- Provide support for Python 3.10
- Pynguin now set `typing.TYPE_CHECKING = True` explicitly before parsing the 
  subject under test in order to be able to collect also information about types 
  that are only imported due to type checking/providing type annotations.
- Improved generation of collection statements
- Cleanup the implementation of the algorithms
- Add supports for enums in the test-generation process
- Cleanup the implementation of the dynamic value seeding
- Make Pynguin executions as deterministic as we possibly can
- Make DynaMOSA the default algorithm
- Allow the generation of an HTML coverage report similar to the one generated by 
  Coverage.py.  This allows to show the subject under test and the coverage achieved 
  by the test cases generated by Pynguin in the web browser.
- Add a [CITATION.cff](https://citation-file-format.github.io/) file
- Improve the internal control-flow graph
- Improve the documentation
- Cleanup and remove unused code
- Fix a bug in post-processing
- Fix a bug in branch coverage instrumentation on `for` loops
- Add a variant of the whole-suite algorithm that uses an archive
- Guard imports that are only necessary for type checking in Pynguin's modules by 
  `if typing.TYPE_CHECKING` conditions

## Pynguin 0.9.2

- Add explicit code-execution prevention (thanks to @Wooza).

  Pynguin now requires you to set the `PYNGUIN_DANGER_AWARE` environment
  variable before it actually does test generation.  This was added due to the
  fact that Pynguin executes the module under test, including its dependencies,
  which could potentially cause harm on the user's system.  By requiring the
  variable to be set explicitly, a user confirms that they are aware of this
  issue.  Inside the Docker container, the variable is set automatically; we
  highly recommend this way of executing Pynguin!

## Pynguin 0.9.1

- Fix spelling errors in README

## Pynguin 0.9.0

- Proper support for Python 3.9
- Improve branch-distance calculations for `byte` values
- Cleanup algorithm implementations

## Pynguin 0.8.1

- Regroup configuration options
- Improve branch-distance calculations for data containers
- Save *import coverage* to a separate output variable
- Delete some unused code
- Add warning notice to read-me file

## Pynguin 0.8.0

- *Breaking:* Renamed `RANDOM_SEARCH` to `RANDOM_TEST_SUITE_SEARCH` to select the 
  random-sampling algorithm based on test suites introduced in Pynguin 0.7.0.
 

- Improve input generation for collection types.
- Add an implementation of tournament selection for the use with DynaMOSA, MOSA, and 
  Whole Suite.
  
  For Whole Suite, on can choose the selection algorithm (either rank or tournament 
  selection) by setting the value of the `--selection` parameter.
- Add [DynaMOSA](https://doi.org/10.1109/TSE.2017.2663435) test-generation algorithm.
  
  It can be selected via `--algorithm DYNAMOSA`.
- Add [MIO](https://doi.org/10.1007/978-3-319-66299-2_1) test-generation algorithm.
  
  It can be selected via `--algorithm MIO`.
- Add a random sampling algorithm based on test cases.
  
  The algorithm is available by setting `--algorithm RANDOM_TEST_CASE_SEARCH`.  It 
  randomly picks one test case, adds all available fitness functions to it and adds 
  it to the MOSA archive.  If the test case is covering one fitness target it is 
  retrieved by the archive.  If it covers an already covered target but is shorter 
  than the currently covering test case for that target, it replaces the latter.
- Fix `OSError` from executors queue.
  
  The queue was kept open until the garbage collector delete the object.  This 
  caused an `OSError` because it reached the OS's limit of open resource handles.  
  We now close the queue in the test-case executor manually to mitigate this.
- Fix `__eq__` and `__hash__` of parameterised statements.
  
  Before this, functions such as `foo(a)` and `bar(a)` had been considered 
  equivalent from their equals and hash-code implementation, which only compared the 
  parameters and returns but not the actual function's name.
- Fix logging to work properly again.

## Pynguin 0.7.2

- Fixes to seeding strategies

## Pynguin 0.7.1

- Fix readme file

## Pynguin 0.7.0

- *Breaking:* Renamed algorithms in configuration options.
  Use `RANDOM` instead of `RANDOOPY` for feedback-directed random test generation 
  and `WHOLE_SUITE` instead of `WSPY` for whole-suite test generation.
- Add [MOSA](https://doi.org/10.1109/ICST.2015.7102604) test-generation algorithm.  
  It can be selected via `--algorithm MOSA`.
- Add simple random-search test-generation algorithm.
  It can be selected via `--algorithm RANDOM_SEARCH`.
- Pynguin now supports the usage of a configuration file (based on Python's 
  [argparse](https://docs.python.org/3/library/argparse.html)) module.
  Use `@<path/to/file>` in the command-line options of Pynguin to specify a 
  configuration file.
  See the `argparse` documentation for details on the file structure.
- Add further seeding strategies to extract dynamic values from execution and to use 
  existing test cases as a seeded initial population (thanks to 
  [@Luki42](https://github.com/luki42))

## Pynguin 0.6.3

- Resolve some weird merging issue

## Pynguin 0.6.2

- Refactor chromosome representation to make the subtypes more interchangeable
- Update logo art
- Fix for test fixture that caused changes with every new fixture file

## Pynguin 0.6.1

- Add attention note to documentation on executing arbitrary code
- Fix URL of logo in read me
- Fix build issues

## Pynguin 0.6.0

- Add support for simple assertion generation (thanks to [@Wooza](https://github.com/Wooza)).
  For now, assertions can only be generated for simple types (`int`, `float`, `str`,
  `bool`).  All other assertions can only check whether or not a result of a method
  call is `None`.
  The generated assertions are regression assertions, i.e., they record the return
  values of methods during execution and assume them to be correct.
- Provide a version-independent DOI on Zenodo in the read me
- Several bug fixes
- Provide this changelog

## Pynguin 0.5.3

- Extends the documentation with a more appropriate example
- Removes outdated code
- Make artifact available via Zenodo

## Pynguin 0.5.2

- Extends public documentation

## Pynguin 0.5.1

- Provides documentation on [readthedocs](https://pynguin.readthedocs.io/)

## Pynguin 0.5.0

- First public release of Pynguin

## Pynguin 0.1.0

Internal release that was used in the evaluation of our paper “Automated Unit Test
Generation for Python” for the
[12th Symposium on Search-Based Software Engineering](http://ssbse2020.di.uniba.it/)
