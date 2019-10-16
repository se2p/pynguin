# Contribution Guidelines

Contributions are always welcome.
This page serves as a starter with some information what is necessary to contribute.

## Development Environment

Pynguin uses [`poetry`](https://poetry.eustace.io) to manage dependencies
and for setting up the development environment.
Make sure, you have installed `poetry` on your system.
Please see `poetry`'s documentation how to install the tool.

Once you've installed `poetry` you can easily clone this project by executing
```bash
git clone git@gitlab.infosun.fim.uni-passau.de:lukasczy/pynguin.git
```
on your shell, which will clone the repository to a folder called `pynguin` in the
 current working directory.
Change to this directory, e.g., by typing `cd pynguin`.

By executing `poetry install`, `poetry` will setup a virtual environment,
and it will install all dependencies into this environment.
In order to do this successfully it is necessary to have at least Python 3.7
available in your system's `PATH`.  Please see the `poetry` documentation for more
details on its usage.

You can activate the virtual environment for your current shell session by `poetry
 shell`.

## Coding Guidelines

`Pynguin` uses several static analysis tools in its build process and continuous
 integration.
We provide a `Makefile` for convenience if you have an activate virtual environment.

`Pynguin` uses the [`black`](https://github.com/psf/black) code style.
You can invoke the formatter by the target `make black`.
Furthermore, we use the linting tools [`flake8`](https://flake8.pycqa.org) and
[`pylint`](https://www.pylint.org).
Respective make targets exist for both.
Besides that we use the static type checker [`mypy`](www.mypy-lang.org),
which can also be invoked through a make target (`make mypy`).

It is required that all these tools run without complaints
in order to have a working continuous integration build.
We really want to keep `Pynguin` clean of tool warnings or even errors.

## Unit Tests

`Pynguin` uses [`pytest`](https://pytest.org) to execute the tests.
You can find the tests in the `tests` folder.
The target `make test` executes `pytest` with the appropriate parameters.

To combine all analysis tools and the test execution
we provide the target `make check`,
which executes all of them in a row.
