.. quickstart:

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
  with random inputs.

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

The first few lines show that Pynguin starts, that it has not gotten any seed for its
(pseudo) random-number generator, followed by the configuration
options that are used for its *DYNAMOSA* algorithm.
We can also see that it ran zero iterations of that algorithm, i.e.,
the initial random test cases were sufficient to cover all branches.
This was to be expected, since the triangle example can be trivially covered with tests.
The output then concludes with its results:
Five test cases were written to ``/tmp/pynguin/results/test_example.py``, which look
like the following (the result can differ on your machine):

.. literalinclude:: ../source/_static/test_example.py
    :linenos:
    :language: python
    :lines: 8-

We can see that each test case consists of one or more invocations of the ``triangle`` function
and that there are assertions that check for the correct return value.

.. note::
  As of version 0.6.0, Pynguin is able to generate assertions for simple data
  types (``int``, ``float``, ``str``, ``bytes`` and ``bool``), as well as checks for ``None``
  return values.

.. note::
  As of version 0.13.0, Pynguin also provides a better assertion generation based on
  mutation.  This allows to generate assertions also for more complex data types.


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

We can see that the *DYNAMOSA* algorithm had to perform nine iterations to fully cover
the ``Queue`` example with the given seed.
We can also see that Pynguin generated three successful testcases:

.. literalinclude:: ../source/_static/test_queue_example.py
    :linenos:
    :language: python
    :lines: 8-


And that it also generated four failing test cases, one of which looks this:

.. literalinclude:: ../source/_static/test_queue_example_failing.py
    :linenos:
    :language: python
    :lines: 20-32

Failing test cases hereby are test cases that raised an exception during their execution.
For now, Pynguin cannot know if an exception is expected program behavior,
caused by an invalid input or an actual fault.
Thus, these test cases are wrapped in ``try-except`` blocks and should be manually inspected.

.. note::
  Generated test cases may contain a lot of superfluous statements.
  Future versions of Pynguin will try minimize test cases as much as possible
  while retaining their coverage.

  Also many generated assertions might be redundant.  Minimising these is open for a
  future release of Pynguin, too.

