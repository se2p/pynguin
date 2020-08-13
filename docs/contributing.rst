Contributing
============

All contributions are welcome!

In order to ease the start for you to contribute,
please follow these guidelines.

*Please note:* Pynguin development currently takes place on a private repository.
Our public GitHub repository just serves as a mirror of released versions.
If you are interested in contributing to Pynguin please contact use beforehand.

Dependencies
------------

We use ``poetry`` to manage the `dependencies`_
If you do not have ``poetry`` installed,
you should run the command below::

    make download-poetry

To install dependencies and prepare `pre-commit`_ hooks
you would need to run the ``install`` command::

    make install

To activate your ``virtualenv`` run ``poetry shell``.
We refer you to the documentation of ``poetry`` for further details on the tool.

Code Style
----------

After you run ``make install`` you can execute the automatic code formating::

    make codestyle

We require the `black`_ code style, with 88 characters per line maximum width
(exceptions are only permitted for imports and comments that disable, e.g., a
``pylint`` warning).  Imports are ordered using `isort`_.  Docstrings shall conform
to the `Google Python Style Guide`_.  Except from the above-mentioned differences, we
suggest to conform the the Google Python Style Guide as much as possible.

In particular, we want to point to Sec. 2.14 of Google's style guide, regarding
``None`` checks.

Import from ``__future__`` are not permitted except for the ``from __future__ import
annotations`` feature that allows more concise type hints.  Pynguin requires at least
Python 3.8—there is not need to support older versions here!

Checks
^^^^^^

Many checks are configured for this project.
The command ``make check-style`` will run black diffs, darglint docstring style and
mypy.
The ``make check-safety`` command will look at the security of our code.

*Note:* darglint on Windows only runs in ``git bash`` or the Linux subsystem.

You can also use the ``STRICT=1`` flag to make the check be strict.

Before Submitting
^^^^^^^^^^^^^^^^^

Before submitting your code please do the following steps:

1. Add any changes you want
2. Add tests for the new changes (can be done vice versa of course, if you follow the
   TDD principles, which we highly recommend to do)
3. Edit documentation if you have changed something significant
4. Run ``make codestyle`` to format your changes
5. Run ``STRICT=1 make check-style`` to ensure that types and docs are correct
6. Run ``STRICT=1 make check-safety`` to ensure that security of your code is correct

Unit Tests
----------

Pynguin uses `pytest`_ to execute the tests.
You can find the tests in the ``tests`` folder.
The target ``make test`` executes ``pytest`` with the appropriate parameters.

We prefer a test-driven development style, which allows us to have tests in a natural
way when developing some new functionality.

To combine all analysis tools and the test execution we provide the target ``make
check``, which executes all of them in a row.

Development using PyCharm
-------------------------

If you want to use the PyCharm IDE you have to set up a few things:

1. Import Pynguin into PyCharm.
2. Find the location of the virtual environment by running ``poetry env info`` in the
   project directory.
3. Go to ``Settings``/``Project: pynguin``/``Project interpreter``
4. Add and use an existing interpreter that points to the path of the virtual
   environment
5. Set the default test runner to ``pytest``
6. Set the docstrings format to ``Google``


.. _dependencies: https://github.com/python-poetry/poetry
.. _pre-commit: https://pre-commit.com
.. _black: https://github.com/psf/black
.. _isort: https://github.com/timothycrosley/isort
.. _`Google Python Style Guide`: https://google.github.io/styleguide/pyguide.html
.. _pytest: https://pytest.org/
