.. _quickstart:

Quickstart
==========

Eager to start?  Make sure that Pynguin is :ref:`installed <install>` properly.

.. warning::
  Pynguin actually executes the code of the module under test.  That
  means, if the code you want to generate tests for does something bad, for example
  wipes your disk, there is nothing that prevents it from doing so!
  This also includes code that is transitively imported by the module under test.

  To mitigate this issue, we recommend running Pynguin in a Docker container with
  appropriate mounts from the host system's file system.
  See the ``pynguin-docker.sh`` script in Pynguin's source repository for documentation
  on the necessary mounts.

  To help prevent harming the system that runs Pynguin, its CLI will immediately abort
  unless the environment variable ``PYNGUIN_DANGER_AWARE`` is set. In setting this
  variable, you acknowledge that you are aware of the possible dangers of executing code
  with random inputs.  The assigned value can be arbitrary; Pynguin solely checks
  whether the variable is defined.

  We do not provide any support and are not responsible if you break your computer by
  executing Pynguin on some random code from the internet!
  Be careful and check the code before actually executing it—which is good advice anyway.

  *Developers:* If you know of a similar technique to Java's security manager mechanism
  in Python, which we can use to mitigate this issue, please let us know.

A Simple Example
----------------

For a first impression, we use the bundled example file and generate tests for it.
Note that this assumes that you have the source code checked out, installed Pynguin
properly—as mentioned before, we recommend a virtual environment, which needs to be
sourced manually—and that your shell is pointing to the root directory of Pynguin's
source repository.
We run all commands on a command-line shell where we assume that the environment variable
``PYNGUIN_DANGER_AWARE`` is set.

.. note::
  We don't use docker in our examples, because we know that our examples
  do not contain or use code that might harm our system.
  But for unknown code we highly recommend using some form of isolation.

First, let's look at the code of the example file (which is located in
``docs/source/_static/example.py``):

.. literalinclude:: ../source/_static/example.py
    :linenos:
    :language: python
    :lines: 9-

The example is the classical ``triangle`` example from courses on Software Testing,
which yields for three given integers—assumed to be the lengths of the triangle's
edges—what type of triangle it is.
Note that we have annotated all parameter and return types, according to
:pep:`484`.

Before we can start, we create a directory for the output (this assumes you are on a
Linux or macOS machine, but similar can be done on Windows) using the command line::

   $ mkdir -p /tmp/pynguin-results

We will now invoke Pynguin (using its default test-generation algorithm) to let
it generate test cases (we use ``\`` and the line breaks for better readability here,
you can just omit them and type everything in one line)::

   $ pynguin \
       --project-path ./docs/source/_static \
       --output-path /tmp/pynguin-results \
       --module-name example

This runs for a moment without showing any output.  Thus, to have some more verbose
output we add the ``-v`` parameter::

   $ pynguin \
       --project-path ./docs/source/_static \
       --output-path /tmp/pynguin-results \
       --module-name example \
       -v

The output on the command line might be something like the following:

.. literalinclude:: ../source/_static/example-stdout.txt

The first few lines show that Pynguin starts using a master-worker
architecture, which allows automatic restarting the test generation
in case of unexpected errors. Then, we see that Pynguin tries collecting
constants from the module under test, but none were found in this case.
Pynguin analyzes the module and finds one function, namely ``triangle``,
which it will try to cover with generated test cases.
The ``11`` found classes are the built-in types that are always present.
Pynguin has not gotten any seed for its (pseudo) random-number generator,
so it generates one itself. We see some information about the
(default) configuration options used. We use, for example, the *DYNAMOSA*
algorithm. Pynguin ran zero iterations of that algorithm, i.e.,
the initial random test cases were sufficient to cover all branches.
This was to be expected, since the triangle example can be trivially covered with tests.
Pynguin minimizes the test suite and then generates assertions
using :ref:`Mutation Analysis <mutation_analysis>`.
Before stopping the master-worker system, the results are printed:
Three test cases were written to ``/tmp/pynguin/results/test_example.py``, which look
like the following (the result can differ on your machine):

.. literalinclude:: ../source/_static/test_example.py
    :linenos:
    :language: python
    :lines: 8-

We can see that each test case consists of one or more invocations of the ``triangle`` function
and that there are assertions that check for the correct return value.
We can now run the generated test cases using ``pytest`` with coverage enabled
to see that indeed all code is covered::

   $ pytest \
       --cov=example \
       --cov-branch docs/source/_static/test_example.py

.. note::
  Pynguin uses `ruff-format <https://docs.astral.sh/ruff/formatter/>`_ for formatting.


A more complex example
----------------------

The above ``triangle`` example is really simple and could also be covered by a simple fuzzing tool.
Thus, we now look at a more complex example: An implementation of a ``Queue`` for ``int`` elements.
(located in ``docs/source/_static/queue_example.py``):

.. literalinclude:: ../source/_static/queue_example.py
    :linenos:
    :language: python
    :lines: 7-

Testing this queue is more complex. One needs to instantiate it, add items, etc.
Similar to the ``triangle`` example, we start Pynguin with the following command::

    $ pynguin \
        --project-path ./docs/source/_static/ \
        --output-path /tmp/pynguin-results \
        --module-name queue_example \
        -v \
        --seed 1629381673714481067

.. note::
  We used a predefined seed here, because we know that Pynguin requires less iterations with this seed in this specific example and version.
  This was done to get a clearer log.

The command yields the following output:

.. literalinclude:: ../source/_static/queue-example-stdout.txt

We can see that the *DYNAMOSA* algorithm had to perform eight iterations to fully cover
the ``Queue`` example with the given seed.
We can also see that Pynguin generated eight test cases:

.. literalinclude:: ../source/_static/test_queue_example.py
    :linenos:
    :language: python
    :lines: 8-

We can now run the generated test cases using ``pytest`` with coverage enabled
to see that all code is covered:

    $ pytest \
        --cov=queue_example \
        --cov-branch docs/source/_static/test_queue_example.py

.. note::
  Generated test cases may contain a lot of superfluous statements.
  Future versions of Pynguin will try minimize test cases as much as possible
  while retaining their coverage.

  Also many generated assertions might be redundant.  Minimising these is open for a
  future release of Pynguin, too.

Logging
-------

Pynguin provides the ability to write logging output to a log file in addition to STDOUT.
This can be configured using the ``--log-file`` parameter::

    $ pynguin \
        --project-path ./docs/source/_static/ \
        --output-path /tmp/pynguin-results \
        --module-name example \
        -v \
        --log-file /tmp/pynguin-log.txt

This will write all log messages to the specified file, making it easier to analyze the test generation process
or troubleshoot issues without cluttering the console output.
