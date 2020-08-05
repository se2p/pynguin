# Pynguin

Pynguin,
the
PYthoN
General
UnIt
test
geNerator,
is a tool that allows developers to generate unit tests automatically.

Testing software is a tedious task.
Thus, automated generation techniques have been proposed and mature tools exist—for
statically typed languages, such as Java.
There is, however, no fully-automated tool available that produces unit tests for
general-purpose programs in a dynamically typed language.
Pynguin is, to the best of our knowledge, the first tool that fills this gap
and allows the automated generation of unit tests for Python programs.

Pynguin is developed at the
[Chair of Software Engineering II](https://www.fim.uni-passau.de/lehrstuhl-fuer-software-engineering-ii/) 
of the [University of Passau](https://www.uni-passau.de).

[![License LGPL v3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![PyPI version](https://badge.fury.io/py/pynguin.svg)](https://badge.fury.io/py/pynguin)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/pynguin.svg)](https://gitlab.com/pynguin/pynguin)
[![Documentation Status](https://readthedocs.org/projects/pynguin/badge/?version=latest)](https://pynguin.readthedocs.io/en/latest/?badge=latest)

![Pynguin Logo](docs/source/_static/pynguin-logo.png "Pynguin Logo")


## Prerequisites

Before you begin, ensure you have met the following requirements:
- You have installed Python 3.8 (we have not yet tested with Python 3.9, there might
  be some problems due to changed internals regarding the byte-code instrumentation).
- You have a recent Linux/macOS/Windows machine.
 
## Installing Pynguin

Pynguin can be easily installed using the `pip` tool by typing:
```bash
pip install pynguin
```

Make sure that your version of `pip` is the one of the Python 3.8 interpreted or a
virtual environment that uses Python 3.8 as its interpreter as any older version is
not supported by Pynguin!

## Using Pynguin

Pynguin is a command-line application.
Once you installed it to a virtual environment, you can invoke the tool by typing
`pynguin` inside this virtual environment.
Pynguin will then print a list of its command-line parameters.

A minimal full command line to invoke Pynguin could be the following,
where we assume that a project `foo` is located in `/tmp/foo`,
we want to store Pynguin's in `/tmp/testgen`,
and we want to generate tests using a whole-suite approach for the module `foo.bar`
(wrapped for better readability):
```bash
pynguin \
  --algorithm WSPY \
  --project_path /tmp/foo \
  --output_path /tmp/testgen \
  --module_name foo.bar
```

## Contributing to Pynguin

For the development of Pynguin you will need the [`poetry`](https://python-poetry.org)
dependency management and packaging tool.
To start developing, follow these steps:
1. Clone the repository
2. Change to the `pynguin` folder: `cd pynguin`
3. Create a virtual environment and install dependencies using `poetry`: `poetry install`
4. Make your changes
5. Run `poetry shell` to switch to the virtual environment in your current shell
6. Run `make check` to verify that your changes pass all checks

   Please see the `poetry` documentation for more information on this tool.

### Development using PyCharm.

If you want to use the PyCharm IDE you have to set up a few things:
1. Import pynguin into PyCharm.
2. Find the location of the virtual environment by running `poetry env info` in the project directory.
3. Go to `Settings` / `Project: pynguin` / `Project interpreter`
4. Add and use a new interpreter that points to the path of the virtual environment
5. Set the default test runner to `pytest`

## License

This project is licensed under the terms of the
[GNU Lesser General Public License](LICENSE.rst).
