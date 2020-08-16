<!--
SPDX-FileCopyrightText: 2020 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# How to contribute

## Dependencies

We use `poetry` to manage the [dependencies](https://github.com/python-poetry/poetry).
If you do not have `poetry` installed, you should run the command below.

```bash
make download-poetry
```

To install dependencies and prepare [`pre-commit`](https://pre-commit.com/) hooks you would need to run `install` command:

```bash
make install
```

To activate your `virtualenv` run `poetry shell`.

## Codestyle

After you run `make install` you can execute the automatic code formatting.

```bash
make codestyle
```

We require the [black](https://github.com/psf/black) code style,
with 88 characters per line maximum width (exceptions are only permitted for imports
and comments that disable, e.g., a `pylint` warning).
Imports are ordered using [isort](https://github.com/timothycrosley/isort).
Docstrings shall conform to the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
Except for the above-mentioned differences,
we suggest to conform to the Google Python Style Guide as much as possible.

In particular, we want to point to Sec. 2.14 of Google's style guide,
regarding `None` checks.

Imports from `__future__` are not permitted except for the `from __future__ import
 annotations` feature that allows more concise type hints.
Pynguin requires at least Python 3.8—there is not need to support older versions!

### Checks

Many checks are configured for this project.
Command `make check-style` will run black diffs,
darglint docstring style and mypy.
The `make check-safety` command will look at the security of your code.

*Note:* darglint on Windows only runs in `git bash` or the Linux subsystem.

You can also use `STRICT=1` flag to make the check be strict.

### Before submitting

Before submitting your code please do the following steps:

1. Add any changes you want
1. Add tests for the new changes
1. Edit documentation if you have changed something significant
1. Run `make codestyle` to format your changes.
1. Run `STRICT=1 make check-style` to ensure that types and docs are correct
1. Run `STRICT=1 make check-safety` to ensure that security of your code is correct

## Unit Tests

`Pynguin` uses [`pytest`](https://pytest.org) to execute the tests.
You can find the tests in the `tests` folder.
The target `make test` executes `pytest` with the appropriate parameters.

To combine all analysis tools and the test execution
we provide the target `make check`,
which executes all of them in a row.

We automatically deploy the coverage report (HTML version) from the CI chain
to [an external server](https://pagedeploy.lukasczyk.me/pynguincoverage/) (only for
the `master` branch).
It is necessary to test code!
Untested code cannot be accepted—or only under rare conditions.

## Other help

You can contribute by spreading a word about this library.
It would also be a huge contribution to write
a short article on how you are using this project.
You can also share your best practices with us.
