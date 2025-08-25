Development Hints
=================

Deterministic behavior
----------------------
Pynguin's behavior is inherently probabilistic.
However, in order to easily reproduce an execution, e.g. for an evaluation or for debugging purposes,
it must be possible to achieve :ref:`deterministic behavior <reproducible>`.

For this purpose, whenever an implementation uses randomness, it must be done via ``pynguin.utils.randomness``.
This module contains a singleton instance of a (pseudo) random-number generator that is seeded at startup (using ``--seed``).

Furthermore, when an implementation's behavior depends on the iteration order of a data structure,
e.g., when picking a random element from it, one has to ensure that this order is deterministic:

- lists and tuples are ordered by design.
- dicts store their insertion order beginning with Python 3.7 and are therefore safe to use.
- Python's builtin sets do not guarantee any order, thus one has to use ``OrderedSet``, which is a set implementation that stores the insertion order of its elements.



Overriding ``__eq__`` and ``__hash__`` methods
----------------------------------------------

Similar to the Java world, we enforce to adhere to contracts for equals and hash
methods as described, for example, in the `Java API documentation <https://docs
.oracle.com/javase/7/docs/api/java/lang/Object.html>`_.
More information can also be found in Joshua Bloch's famous book *Effective Java*.
In particular, when you override the ``__eq__`` or the ``__hash__`` method of a class
you are also required to override its opponent.

The following contracts should hold (adopted from the Java API documentation):

1. For ``__hash__``

  * ``__hash__`` must consistently return the same integer whenever it is invoked on
    the same object more than once during one execution of the Python application,
    provided no information used in ``__eq__`` comparisons on the same object is
    modified.  The integer need not remain consistent from one application execution to
    another execution of the same application.
  * If two objects are equal according to the ``__eq__`` method then the ``__hash__``
    value of the two objects must be the same
  * It is *not* required that for two objects being unequal according to the ``__eq__``
    method, the ``__hash__`` value must be distinct, although this could improve
    performance of hash tables.

2. For ``__eq__``

  * The relation is *reflexive*: for any non-null reference value ``x``,
    ``x.__eq__(x)`` should return ``True``
  * The relation is *symmetric*: for any non-null reference values ``x`` and ``y``,
    ``x.__eq__(y)`` should return ``True`` if and only if ``y.__eq__(x)`` returns
    ``True``.
  * The relation is *transitive*: for any non-null reference values ``x``, ``y``, and
    ``z``, if ``x.__eq__(y)`` returns ``True`` and ``y.__eq__(z)`` returns ``True``,
    then also ``x.__eq__(z)`` should return ``True``.
  * The relation is *consistent*: Multiple invocations of the method on the same two
    objects should yield the same result as long as none of the objects has been
    changed.
  * For any non-null reference value ``x``, ``x.__eq__(None)`` should return ``False``

Overriding ``__str__`` and ``__repr__`` methods
-----------------------------------------------

The goal of a ``__str__`` method is to provide a string representation that is
usable and readable for a user.  The goal of the ``__repr__`` method is to be
unambiguous, see `StackOverflow <https://stackoverflow.com/a/2626364/4293396>`_.
We encourage you to provide a ``__repr__`` representation that looks like the Python
code that creates an object with the state of the object ``__repr__`` was called on.
Consider the following example:

.. code-block:: python
    :linenos:

    class Example:
        def __init__(
            self, foo: str, bar: int, baz: List[str]
        ) -> None:
            self._foo = foo
            self._bar = bar
            self._baz = baz


    example = Example("abc", 42, ["xyz", "pynguin"])

The representation, i.e., the result yielded by calling ``__repr__`` on the
``example`` object should look like

.. code-block::

    Example(foo="abc", bar=42, baz=["xyz", "pynguin"])

which can be achieved by implementing the ``__repr__`` method of the ``Example``
class as follows:

.. code-block:: python
    :linenos:

        def __repr__(self) -> str:
            return f"Example(foo=\"{self._foo}\", bar={self._bar}, "
                   f"baz={repr(self._baz)})"

Guarding imports for type checking
----------------------------------

Some imports in a module are only necessary for type checking but not at runtime.
We guard these imports by ``if typing.TYPE_CHECKING`` blocks.
The main reason for this is to prevent circular imports.
During type checking, these imports do not harm the type checker as it uses much more
sophisticated techniques to handle the circular imports (like a compiler does) in
contrast to the simple handling of the interpreter.


Debugging test case execution
-----------------------------

We execute test cases in a separate thread.
To track data on the test case execution, e.g., line or branch coverage, we use thread-local storage.
Usage of threading.local may interfere with debugging tools, such as pydevd.
In such a case, disable Cython by setting the following environment variable:
``PYDEVD_USE_CYTHON=NO``


Comments and DocStrings
-----------------------

We have no general policy regarding comments in the source code.
Use them, whenever you feel they are necessary.
Please do not explain *what* the code is doing, but *why*.

DocStrings are required for all public functions, methods, constructors, classes, and
modules.
We use the ``ruff`` linter to check for the DocStrings.
You can omit the DocString for default constructors, i.e., constructors that take no
arguments, and methods that override a method from a parent class.
In the former case, disable ``ruff``'s warning by adding ``# noqa: D107`` to the line
of the constructor declaration;
use ``# noqa: D102`` in the latter case, respectively.

Please follow the Google style for your DocString formatting.

Sometimes, the interface of a class forces you to override a method, e.g., because the
base class is abstract, but there is no need for a concrete implementation.  In such a
case put the following DocString to the overriding method to show that it is empty on
purpose.

.. code-block:: python
    :linenos:

        def overriding_method(self, a: int):
            """Not used.

            Args:
                a: not used
            """

Code Formatting
---------------

We use ``ruff-format`` for code formatting. This replaced the previously used ``black`` formatter.
The formatting is automatically applied when running ``make codestyle``.

Code formatting standards:

- Maximum line length is 100 characters (exceptions are only permitted for imports and comments that disable linter warnings)
- Imports are ordered using ``isort``
- Docstrings must conform to the Google Python Style Guide
- We follow the Google Python Style Guide as much as possible

To manually format your code, you can run:

.. code-block:: bash

    make codestyle

This will apply ``ruff-format`` to format your code and organize imports according to our standards.

In addition to formatting, we use the following tools for code quality:

- ``ruff`` for static code analysis
- ``mypy`` for type checking

You can run all checks with:

.. code-block:: bash

    make check

Pre-commit Hooks
----------------

Pynguin uses `pre-commit <https://pre-commit.com>`_ to enforce code quality standards before commits are made. Pre-commit is a framework for managing and maintaining multi-language pre-commit hooks.

Pre-commit hooks are configured in the ``.pre-commit-config.yaml`` file in the project root. When you run ``make install``, pre-commit hooks are automatically installed in your local repository.

The following pre-commit hooks are configured:

1. **pre-commit-hooks**: Various checks for code quality and formatting

   - ``check-ast``: Checks Python syntax
   - ``check-builtin-literals``: Ensures consistent use of literals for builtin types
   - ``check-case-conflict``: Checks for files with names that would conflict on a case-insensitive filesystem
   - ``check-docstring-first``: Ensures docstrings are before code
   - ``check-json``, ``check-toml``, ``check-xml``, ``check-yaml``: Validates file formats
   - ``check-merge-conflict``: Checks for merge conflict markers
   - ``check-symlinks``: Checks for symlinks that don't point to anything
   - ``debug-statements``: Checks for debugger imports and py37+ ``breakpoint()`` calls
   - ``destroyed-symlinks``: Detects symlinks that have been destroyed
   - ``end-of-file-fixer``: Ensures files end with a newline
   - ``mixed-line-ending``: Ensures consistent line endings
   - ``pretty-format-json``: Formats JSON files
   - ``trailing-whitespace``: Trims trailing whitespace

2. **poetry hooks**: Ensures Poetry configuration is valid and dependencies are up-to-date

   - ``poetry-check``: Validates the structure of the pyproject.toml file
   - ``poetry-lock``: Ensures poetry.lock is up-to-date
   - ``poetry-install``: Ensures dependencies are installed

3. **isort**: Sorts imports according to the project's standards

   - ``isort``: Configured with black profile for compatibility

4. **ruff**: Linting and formatting

   - ``ruff``: Fast Python linter with automatic fixes
   - ``ruff-format``: Code formatter (replacement for black)

5. **reuse-tool**: Ensures license compliance

   - ``reuse``: Checks for proper license headers in files

To manually run pre-commit on all files:

.. code-block:: bash

    pre-commit run --all-files

Pre-commit hooks will also run automatically when you attempt to commit changes, preventing commits that don't meet the project's quality standards.

Logging
-------

Pynguin uses Python's standard ``logging`` module for logging. The logging system is configured in the ``_setup_logging`` function in ``cli.py``.

Logging features:

- Multiple verbosity levels (controlled via command-line options):
  - Default: WARNING level
  - ``-v``: INFO level
  - ``-vv`` or higher: DEBUG level
- Rich console output with formatted tracebacks (can be disabled with ``--no-rich``)
- Optional file logging (enabled with ``--log-file`` option)
- Consistent log format including timestamp, level, module name, function name, line number, and message

When adding logging to your code:

1. Import the logging module at the top of your file:

   .. code-block:: python

       import logging

2. Create a module-level logger using:

   .. code-block:: python

       _logger = logging.getLogger(__name__)

3. Use the appropriate logging level in your code:

   .. code-block:: python

       _logger.debug("Detailed debugging information")
       _logger.info("General information about program execution")
       _logger.warning("Warning about potential issues")
       _logger.error("Error that doesn't prevent execution")
       _logger.critical("Critical error that may prevent execution")

The logging configuration can be controlled via command-line options when running Pynguin.

Add support for new Python versions
-----------------------------------

Pynguin uses bytecode instrumentation to collect data about SUT execution. This makes Pynguin
very susceptible to the changes of the CPython bytecode. Therefore, it is recommended to follow
these guidelines when adding support for new Python versions:

1. Learn about the changes of the CPython bytecode in the documentation:

  - `The dis module <https://docs.python.org/3/library/dis.html>`_
  - `The Python changelog <https://docs.python.org/3/whatsnew/>`_

2. Add support for the new version of Python in the ``pyproject.toml`` file and update the ``bytecode`` library.

3. Add a new module with the name of the new Python version in the ``pynguin.instrumentation.version`` package, temporarily include all symbols
   from the previous version and add a new case to use this module in the ``pynguin.instrumentation.version.__init__`` module.

4. Run the tests of package ``pynguin.instrumentation`` using the command below and fix the issues by adding version-specific code in
   the module created in the previous step and removing the temporary imports of the previous version:

   .. code-block:: bash

       pytest tests/instrumentation

5. Run all the tests and linters of Pynguin to ensure that everything works as expected and fix any remaining bugs:

   .. code-block:: bash

       make check
