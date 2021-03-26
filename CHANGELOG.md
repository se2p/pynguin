<!--
SPDX-FileCopyrightText: 2019-2021 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Pynguin Changelog

Please also check the [GitHub Releases Page](https://github.com/se2p/pynguin/releases)
for the source-code artifacts of each version.

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
