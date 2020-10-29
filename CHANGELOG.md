# Pynguin Changelog

Please also check the [GitHub Releases Page](https://github.com/se2p/pynguin/releases)
for the source-code artifacts of each version.

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
