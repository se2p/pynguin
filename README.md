# Pynguin

[![Build Status](https://gitlab.infosun.fim.uni-passau.de/lukasczy/pynguin/badges/master/pipeline.svg)](https://gitlab.infosun.fim.uni-passau.de/lukasczy/pynguin/pipelines)
[![Coverage](https://gitlab.infosun.fim.uni-passau.de/lukasczy/pynguin/badges/master/coverage.svg)](https://gitlab.infosun.fim.uni-passau.de/lukasczy/pynguin/pipelines)
[![License LGPL v3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org)

Pynguin,
the
PYthoN
General
UnIt
test
geNerator,
is a tool that allows developers to generate unit tests automatically.

It provides different algorithms to generate sequences that can be used to test your
code.
It currently does not generate any assertions though.

## Prerequisites

Before you begin, ensure you have met the following requirements:
- You have installed Python 3.8
- You have a recent Linux/macOS machine.  We have not tested the tool on Windows
  machines although it might work.
 
## Installing Pynguin

Pynguin can be easily installed using the `pip` tool by typing:
```bash
pip install pynguin
```

Make sure that your version of `pip` is the one of the Python 3.8 interpreted or a
virtual environment that uses Python 3.8 as its interpreter as any older version is
not supported by Pynguin!

## Using Pynguin

TODO: Write this section!

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
[GNU Lesser General Public License](LICENSE).
