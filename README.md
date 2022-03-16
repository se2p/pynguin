<!--
SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Pynguin

Pynguin (IPA: ˈpɪŋɡuiːn),
the
PYthoN
General
UnIt
test
geNerator,
is a tool that allows developers to generate unit tests automatically.

Testing software is often considered to be a tedious task.
Thus, automated generation techniques have been proposed and mature tools exist—for
statically typed languages, such as Java.
There is, however, no fully-automated tool available that produces unit tests for
general-purpose programs in a dynamically typed language.
Pynguin is, to the best of our knowledge, the first tool that fills this gap
and allows the automated generation of unit tests for Python programs.

Pynguin is developed at the
[Chair of Software Engineering II](https://www.fim.uni-passau.de/lehrstuhl-fuer-software-engineering-ii/) 
of the [University of Passau](https://www.uni-passau.de).

<details>
<summary>Internal Pipeline Status</summary>

[![pipeline status](https://gitlab.infosun.fim.uni-passau.de/se2/pynguin/pynguin/badges/main/pipeline.svg)](https://gitlab.infosun.fim.uni-passau.de/se2/pynguin/pynguin/-/commits/main)
[![coverage report](https://gitlab.infosun.fim.uni-passau.de/se2/pynguin/pynguin/badges/main/coverage.svg)](https://gitlab.infosun.fim.uni-passau.de/se2/pynguin/pynguin/-/commits/main)  

</details>

[![License LGPL v3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![PyPI version](https://badge.fury.io/py/pynguin.svg)](https://badge.fury.io/py/pynguin)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/pynguin.svg)](https://github.com/se2p/pynguin)
[![Documentation Status](https://readthedocs.org/projects/pynguin/badge/?version=latest)](https://pynguin.readthedocs.io/en/latest/?badge=latest)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3989840.svg)](https://doi.org/10.5281/zenodo.3989840)
[![REUSE status](https://api.reuse.software/badge/github.com/se2p/pynguin)](https://api.reuse.software/info/github.com/se2p/pynguin)
[![Downloads](https://static.pepy.tech/personalized-badge/pynguin?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/pynguin)


![Pynguin Logo](https://raw.githubusercontent.com/se2p/pynguin/master/docs/source/_static/pynguin-logo.png "Pynguin Logo")

## Attention

Pynguin executes the module under test!
As a consequence, depending on what code is in that module,
running Pynguin can cause serious harm to your computer,
for example, wipe your entire hard disk!
We recommend running Pynguin in an isolated environment;
use, for example, a Docker container to minimize the risk of damaging
your system.


## Prerequisites

Before you begin, ensure you have met the following requirements:
- You have installed Python 3.10 (we have not yet tested with Python
  3.11, there might be some problems due to changed internals regarding the byte-code
  instrumentation).

  **Attention:** Pynguin now requires Python 3.10!  Older versions are no longer 
  supported!
- You have a recent Linux/macOS/Windows machine.

Please consider reading the [online documentation](https://pynguin.readthedocs.io)
to start your Pynguin adventure.
 
## Installing Pynguin

Pynguin can be easily installed using the `pip` tool by typing:
```bash
pip install pynguin
```

Make sure that your version of `pip` is that of a supported Python version, as any 
older version is not supported by Pynguin!

## Using Pynguin

Before you continue, please read the [quick start guide](https://pynguin.readthedocs.io/en/latest/user/quickstart.html)

Pynguin is a command-line application.
Once you installed it to a virtual environment, you can invoke the tool by typing
`pynguin` inside this virtual environment.
Pynguin will then print a list of its command-line parameters.

A minimal full command line to invoke Pynguin could be the following,
where we assume that a project `foo` is located in `/tmp/foo`,
we want to store Pynguin's generated tests in `/tmp/testgen`,
and we want to generate tests using a whole-suite approach for the module `foo.bar`
(wrapped for better readability):
```bash
pynguin \
  --project-path /tmp/foo \
  --output-path /tmp/testgen \
  --module-name foo.bar
```
Please find a more detailed example in the [quick start guide](https://pynguin.readthedocs.io/en/latest/user/quickstart.html).


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

   Please see the [`poetry` documentation](https://python-poetry.org/docs/) for more information on this tool.

### Development using PyCharm.

If you want to use the PyCharm IDE you have to set up a few things:
1. Import pynguin into PyCharm.
2. Let the poetry support configure a virtual environment.

   If you use a PyCharm version before `2021.3`, you have to install the poetry support as a [plugin](https://plugins.jetbrains.com/plugin/14307-poetry).
3. Set the default test runner to `pytest`
4. Set the DocString format to `Google`


## License

This project is licensed under the terms of the
[GNU Lesser General Public License](LICENSE.rst).
