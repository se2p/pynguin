.. _test_generation_extensions_overview:

Test Generation Extensions
==========================

This document provides an overview of extensions that can be enabled for Pynguin's test generation.

Fandango-Faker
--------------

The Fandango-Faker extensions helps to generate realistic string inputs for Pynguin.
It requires installing the fandango-faker extra: ``poetry install --extras "fandango-faker"``.
This extension implements additional string generators in addition to the default random generation:

- **Faker**: Semantically meaningful string generation using `Faker <https://faker.readthedocs.io>`_
- **Fandango**: Syntactically correct string generation and mutation using `Fandango <https://fandango-fuzzer.github.io>`_ with grammars in `src/pynguin/resources/fans`
- **Fandango-Faker**: A combination of the above two generators

The probability of each string generator can be weighted with the parameters specified in :class:`pynguin.configuration.StringStatementConfiguration`.
