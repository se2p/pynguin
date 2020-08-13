.. quickstart:

Quickstart
==========

Eager to start?  Make sure that Pynguin is :ref:`installed <install>` properly.

Use the Bundled Example
-----------------------

For a first impression, we use the bundled example file and generate tests for it.
Note that this assumes that you have the source code checked out, installed Pynguin
properly—as mentioned before, we recommend a virtual environment, which needs to be
sourced manually—and that your shell is pointing to the root directory of Pynguin's
source repository.
We run all commands on a command-line shell.

First, let's look at the code of the example file (which is located in
``docs/source/_static/example.py``):

.. literalinclude:: ../source/_static/example.py
    :linenos:
    :language: python
    :lines: 16-

The example consists of a couple of classes in one module file, with some methods in
each class.  Note that we have annotated all parameter and return types, according to
:pep:`484`.

Before we can start, we create a directory for the output (this assumes you are on a
Linux or macOS machine, but similar can be done on Windows) using the command line::

   $ mkdir -p /tmp/pynguin-results

We will now invoke Pynguin (using its whole-suite test-generation algorithm) to let
it generate test cases (we use ``\`` and the line breaks for better readability here,
you can just omit them and type everything in one line)::

   $ pynguin \
       --algorithm WSPY \
       --project_path ./docs/source/_static \
       --output_path /tmp/pynguin-results \
       --module_name example

This runs for quite a while without showing any output.  Thus, to have some output as
well as a more limited time (10 seconds here), we add some more parameters::

   $ pynguin \
       --algorithm WSPY \
       --project_path ./docs/source/_static \
       --output_path /tmp/pynguin-results \
       --module_name example \
       -v
       --budget 10

The output on the command line might be something like the following:

.. literalinclude:: ../source/_static/example-stdout.txt
    :emphasize-lines: 1-3,104-108

The first three line show that Pynguin starts, that it has not gotten any seed—that
is a fixed start number of its (pseudo) random-number generator, and that it starts
sequence generation using the *WSPY* algorithm.
It then yields that it generated 100 generations, and concludes with its results:
one test case was written to ``/tmp/pynguin/results/test_example.py``, which looks
like the following (the result can differ on your machine):

.. literalinclude:: ../source/_static/test_example.py
