<!--
SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Pynguin Changelog

Please also check the [GitHub Releases Page](https://github.com/se2p/pynguin/releases)
for the source-code artifacts of each version.

## Unreleased

## Pynguin 0.41.0

- Fix `subject_properties` aren't registered when running Pynguin on an imported module
- Update documentation (Codestyle, Code Overview)
- Add LLM-Agent guidelines
- Add PynguinML mode: Parsing and test generation for libraries which require tensor
  inputs based on API constraints
- Add LLM capabilities: Prompting, parsing, and the LLMOSAAlgorithm
- Add subprocess execution (cf. GitHub Issue #82): Executing test cases in subprocess
  adds an overhead but makes Pynguin more crash resistant
- Refactor TestCaseExecutor and Observer (cf. GitHub Issue #90): Restructuring observers
  into main-thread and remote variants to support safe subprocess execution, better
  performance, and introducing batch test execution and improved error handling for
  unexposed modules and timeouts
- Refactor Tracer (cf. GitHub Issue #89): Proxy tracer to allow for subprocess
  instrumentation without costly reinstrumentation
- Add MaxMemoryStoppingCondition: Graceful termination in case of exceeding a memory
  threshold
- Add probabilistic TypeTracing
- Add minimal LLM mode: Minimal LLM test generator using GPT-4o
- Improve configuration export
- Improve crash-resistance for `getmembers`, importing the SUT, SystemExit in the SUT,
  loggers of the SUT, and crashes in SUT
- Fix bugs related to UnionTypes, lambda parsing, yield statements, getmembers of SUT,
  import of SUT, and SystemExit in SUT
- Improve string distance using left-aligned character distance

## Pynguin 0.40.0

- Provide a (normalised) area under curve for timeline output variables.

  Variables for statistics that produce a timeline, e.g., coverage development over time
  imply in interesting property: while the final coverage of two distinct
  runs/configurations might be equal, one might have a faster coverage increase than the
  other, thus could be considered better.  The area under curve, i.e., the integral over
  the development function allows to access this property easily.
- Add the ability to write the logging to a log file and not only STDOUT.
- Add an auto-deploy action to GitHub to push releases to PyPI.
- Fix a typo in the documentation (cf. GitHub issue #75).
- Switch to `ruff-format`.

## Pynguin 0.39.0

- Fix a bug in the handling of infinite loops in global scope (thanks to @BergLucas in
  #65)

## Pynguin 0.38.0

- Remove the dependency to our custom [MutPy fork](https://github.com/se2p/MutPy-Pynguin)
  by integrating the relevant code into Pynguin directly (thanks to @BergLucas in #64)

## Pynguin 0.37.0

- Add possibility to control number of mutations in MOSA.
- Compute the area under curve if Pynguin traces the overage over time; area under curve
  can be interpreted as the integral over the coverage function, which is computed via
  trapezoidal approximation.
- Fix the assertion generation for `float`s (thanks to @BergLucas in #70)
- Fix assertion and invalid function call (thanks to @BergLucas in #72)

## Pynguin 0.36.0

- Remove unused code
- Fix `ruff` warnings
- Add sequence variable for type-evolution tracking
- Add CLI options to ignore methods and modules from analysis (see #62)

## Pynguin 0.35.0

- Fix `TypeError` bug in instrumentation of bytecode (see GitHub PR #51)
- Add a dump method for type-information statistics
- Fix handling of aliased modules (see GitHub issue #57)
- Fix method-signature handling for C extensions (see GitHub issue #59)

## Pynguin 0.34.0

- Activate a larger selection of checkers for [ruff](https://github.com/astral-sh/ruff)
- Implement various stopping conditions

## Pynguin 0.33.0

- Fix an issue with type-information retrieval (see GitHub issue #35)

## Pynguin 0.32.0

- *Breaking:* Restructure the code

  Most of the code related to the generation algorithms has been moved.  The code now
  resides in the `ga` package, where it fits much better.  All accompanying modules have
  also been moved to different places.  This might cause breakage if you have developed
  extensions for Pynguin that rely on the structure of the modules.
- Update the [`bytecode`](https://github.com/MatthieuDartiailh/bytecode) library to its
  latest GitHub version.

  Necessary to include a fix for a regression in that library, which was pointed out to
  us in GitHub issue #42 (hopefully fixed by this library upgrade).
- Adjust the header of generated test files; we now refer to Pynguin's
  [website](https://www.pynguin.eu).
- Extend the usage of the `ruff` tool for code analysis.

## Pynguin 0.31.0

- Update literature references in documentation
- Add issue templates for GitHub

## Pynguin 0.30.0

- Re-license Pynguin to MIT License

## Pynguin 0.29.0

- Move code to `src`-based layout
- Make configuration of `mypy` more strict
- Remove an accidentally committed file

## Pynguin 0.28.0

- Fix distance computations for `<=` and always convert values to `float`.
- Improve method blacklist for module analysis.
- Improve type handling.
- Allow Pynguin to run on itself.  This can be achieved by the `pynguin_self.py` script
  from the `utils` package.
- Improve warning in documentation that Pynguin actually executes the code under test.
- Various refactorings and improvements.
- Update copyright notices in all files.

## Pynguin 0.27.0

- Write Pynguin version number to Cobertura XML report
- Fix the computation of coverage values

  Pynguin 0.26.0 added the possibility to optimise for, e.g., branch coverage while
  yielding the line coverage of the resulting test suite in the end.  This had some
  unintentional implications, such as the value of the `Coverage` output variable
  having weird values.  We fix this by providing additional output variables
  `FinalBranchCoverage` and `FinalLineCoverage` that contain the final coverage
  values *after* all generation and postprocessing.  See the
  [runtimevariable.py](pynguin/utils/statistics/runtimevariable.py) module for details.
- Rewrite the internal type handling in Pynguin

  This is a huge internal change that improves the internal type system and adds the
  possibility to trace types during test execution.  Some highlights:
  - we got rid of our internal abstraction of `type | None` to mark whether type
    information exists
  - we allow to retrieve additional or new type information from the test execution
  - enhance our internal type representation to make it more flexible
  - add the missing primitive type `complex`
  - a more suitable subtyping check for `Union`s

## Pynguin 0.26.0

- Allow the calculation of coverage values regardless of optimisation.

  Allows to yield, for example, the resulting line coverage of the test suite, while
  the optimisation during test generation was done for branch coverage.  Add the
  required coverage values to your `--output-variables` list to activate this feature.

  *Note:* when doing this, the `Coverage` output variable will contain the average
  value of the incorporated coverage values!
- Provide a Cobertura-like coverage report

  Pynguin already provides an HTML report that can be activated by setting
  `--create-coverage-report True`.  This report is nice for human users but not very
  usable if one wants to automatically reason about the achieved coverage using
  tools.  We thus also emit an XML report in the style of the
  [Cobertura](https://cobertura.github.io/cobertura/) tool that can be used for
  further automated tools.
- Fix typo on `test_parameterizedstatements.py` (see #27, thanks to @stavares843)
- Fix typo on `testcase.py` (see #26, thanks to @stavares843)
- Improve mutation-based assertion generation

  The assertion generation now does not more compare the recorded assertion traces
  but actually executes the assertions to make the whole process more reliable.
  Besides, we do not check for `is not None` as a fallback for object checks any
  more, but use an `isinstance` check on the object's type to have a more precise
  assertion.
- Make statistics tests debuggable

  Some accidental circular import made it impossible to run a debugger on tests in
  `pynguin.utils`.  We resolved this by moving tests to another package.
- Partial rework of internal type system

  We added an abstraction layer over the existing type hints from a module to make
  handling and reasoning with types easier.  This abstraction is based on the one
  used by [`mypy`](http://mypy-lang.org), however, we only cover a small part of
  what [PEP-484](https://peps.python.org/pep-0484/) actually defines.
- Make assertion generation more strict

## Pynguin 0.25.2

- Fix bugs in mutation analysis and assertion generation

## Pynguin 0.25.1

- Fix documentation build on read the docs

## Pynguin 0.25.0

- Fix further issues with test-case isolation during execution.
- Fix some bugs regarding type information.
- Use [astroid](https://github.com/PyCQA/astroid) instead of Python's
  [ast](https://docs.python.org/3/library/ast.html) module for our module analysis due
  to its enhanced features.

## Pynguin 0.24.1

- Update Pynguin's documentation to match fixes from Pynguin 0.24.0

## Pynguin 0.24.0

- Fix killing mutant reporting
- Use [black](https://github.com/psf/black) to format the generated test cases.

  Pynguin now requires `black` as a run-time dependency to use its code formatting.

## Pynguin 0.23.0

- Provide a naive inheritance graph to improve input generation.
- Improve killing of long-running test-case executions
- Add computation of mutation scores for `MUTATION_ANALYSIS` assertion generation.

  The output variables `NumberOfCreatedMutants`, `NumberOfKilledMutants`,
  `NumberOfTimedOutMutants`, and `MutationScore` allow to export those values.
- Do not enable `typing.TYPE_CHECKING` for SUT analysis as this may cause circular
  imports.
- Improve the black list of modules that shall not be incorporated into the test
  cluster.
- Annotate failing tests with `@pytest.mark.xfail(strict=True)`.
- Improve log output of mutation-based assertion generation.
- Add instrumentation to mutated modules to easier kill them.

  This change is relevant only to the `MUTATION_ANALYSIS` assertion-generation strategy.
- Write errors in execution threads to the log instead of STDERR to avoid cluttering
  log output.
- Add limits for amount and size of constants in the constant pool.

  The configuration options `max_dynamic_length` and `max_dynamic_pool_size` allow
  to set sizes for the maximum length of strings/bytes that shall be stored in the
  dynamic constant pool and the maximum numbers of constants of a type, respectively.
  This prevents the constant pool from growing unreasonably large.
- Improve handling of type annotations.
- Fix computation of cyclomatic complexity.

  Computing cyclomatic complexity does not work for functions that are not present
  in the AST, e.g., default constructors.  We now omit those from the computation of
  the cyclomatic-complexity output variables.

## Pynguin 0.22.0

- Fix selection of type-inference strategy.
- Fix a bug in the type inference regarding cases where not type information is present.
- Add a PyLint checker for calls to `print()`.
- Extend the blacklist of modules that shall not be analysed.
- Raise `RuntimeError` from tracer when called from another thread.
- Provide better exception messages for critical failures.
- Apply a further limit to the execution time of a single generated test case to at
  most 10 seconds.
- Exclude empty enum classes from test cluster to fix test generation.

  Parsing included modules raised an issue when the `enum` module is used: the test
  cluster then had a reference to the `enum.Enum` class, which obviously does not
  contain any fields.  In the following, generating tests failed, as soon as this
  class was selected to fulfil parameter values because there was no field to select
  from, e.g., `MyEnum.MY_FIELD`.  We now exclude empty enums from the test cluster.

## Pynguin 0.21.0

- Fix a bug in the module analysis regarding nested functions

  Nested functions/closures caused Pynguin's module analysis to crash with an
  failing assertion.
- Improve the branch-distance computation for `bool` values
- Allow for more statistics variables regarding number of lines and cyclomatic
  complexity

## Pynguin 0.20.1

- Fix a bug in terminating Pynguin due to threading

## Pynguin 0.20.0

### Breaking Changes

- Remove splitting into passing and failing test suite.

  Previously, we consider a test case passing if it did not raise any exception
  during its execution; it was considered failing otherwise.  Pynguin did a split of
  the test cases into two test suites before exporting them.  This was mainly an
  artefact from implementing the random algorithm in the very beginning of the
  project.  Due to the improved assertion export for exception assertions we can now
  get rid of the split and export only one test module containing all generated test
  cases.
- Remove the option to use a log file (`--log_file` or `--log-file`).

  Pynguin writes its output to STDOUT/STDERR now, if requested by the `-v`/`-vv` switch.
  This output is formatted by @willmcgugan's amazing
  [rich](https://github.com/Textualize/rich) library.  A user can disable the output
  formatting by setting the `--no-rich` flag.  Of course, because we believe that `rich`
  is such an awesome library, we also provide an alias for this flag, called `--poor`😉

### Further Changes

- Distinguish between expected and unexpected exceptions.

  We consider an exception to be expected if it is explicitly raised in the code
  under test or is documented in the code's docstring.  For those exceptions we
  build an `with pytest.raises` block around the exception-raising statement.  All
  other exceptions are considered to be unexpected.  We decorate the test method
  with the `@pytest.mark.xfail` decorator and let the exception happen.  It is up to
  the user to decide whether such an exception is expected.  An exception here is
  the `AssertionError`: it is considered to be expected as soon as there is an
  `assert` statement in the code under test.
- Improve installation description to explicitly point to using a virtual environment
  (see GitHub issue #23, thanks to @tuckcodes).
- Improve variable names and exception assertions

  The assertion generation got an improved handling for asserting on exceptions,
  which creates more meaningful and (hopefully) better understandable assertions for
  exceptions.
- Enhance the module analysis

  This is basically a rewrite of our previously existing test cluster, which keeps
  track of all the callables from the subject under test as well as the subject's
  dependencies.  It also incorporates an analysis of the subject's AST (if present)
  and allows for more and more precise information about the subject which can then
  improve the quality of the generated tests.
- To distinguish bytecode instructions during instrumentation we add an
  `ArtificialInstr` for our own added instructions.
- Fix a bug in the tracing of runtime types.

  During assertion generation Pynguin tracks the variable types to decide for which
  values it actually is able to generate assertions.  Creating an assertion on a
  generator function does not work, as the type is not exposed by Python but only
  present during runtime—thus generating an object of this type always fail.  We
  mitigate this by ignoring objects of type `builtins.generator` from the assertion
  generation.
- Improve documentation regarding coverage measurement and the coverage report

## Pynguin 0.19.0

### Breaking Change

- One can now use multiple stopping conditions at a time.

  *This breaks the CLI in two ways:*
  - The parameter `--stopping-condition` has been removed.
  - The parameter `--budget` was renamed to `--maximum-search-time`.

  Users have to change their run configurations accordingly!

  To specify stopping conditions, add one or many from `--maximum-search-time`,
  `--maximum-test-executions`, `--maximum-statement-executions`, and
  `--maximum-iterations` to your command line.

### Further Changes

- Clarify log output for search phases
- Pynguin now uses the `ast.unparse` function from Python's AST library instead of
  the third-party `astor` library to generate the source code of the test cases.

## Pynguin 0.18.0

### Breaking Change
- *We drop the support for Python 3.8 and Python 3.9 with this version!*

  You need Python 3.10 to run Pynguin!  We recommend using our Docker container,
  which is already based on Python 3.10, to run Pynguin.

### Further Changes
- Add line coverage visualisation to the coverage report.
- Add a citation reference to our freshly accepted ICSE'22 tool demo paper “Pynguin:
  Automated Unit Test Generation for Python.
- Unify the modules for the analysis of the module under test.

## Pynguin 0.17.0

- Add line coverage as another coverage type (thanks to @labrenz).
  The user can now choose between using either line or branch coverage or both by
  setting the parameter `--coverage-metrics` to `LINE`, `BRANCH`, or `LINE,BRANCH`.
  Default value is `BRANCH`.

## Pynguin 0.16.1

- Update `CITATION.cff` information

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
  randomly picks one test case, adds all available fitness functions to it, and adds
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
