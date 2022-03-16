.. _reproducible:

Reproducible runs
=================

According to the `Python documentation <https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED>`_
it is necessary to set the environment variable ``PYTHONHASHSEED=0`` in order to
achieve a truly deterministic behaviour and computation.
Furthermore, it is necessary to set the ``--seed`` command-line option to a fixed value.
If no ``--seed`` option was set, Pynguin chooses a seed at random and logs its value.


By default, Pynguin will search for up to ten minutes of wall clock time.
You can change this behaviour by specifying one or multiple stopping conditions to stop
after a certain amount of

* wall clock time (``--maximum-search-time``)
* executed test cases (``--maximum-test-executions``)
* executed statements (``--maximum-statement-executions``)
* algorithm iterations (``--maximum-iterations``)

Pynguin will stop, as soon as one of the stopping conditions is fulfilled or when
Pynguin was able to cover everything in the module under test w.r.t. the specified
coverage metrics.

.. note::
  Using a certain amount of wall-clock time as the stopping condition (``--maximum-search-time``) for Pynguin's executions
  can make achieving deterministic results difficult, because Pynguin might achieve slightly different amounts of iterations in each execution.
  To solve this problem, take note of the amount of achieved iterations in the first execution and
  use them as the new stopping condition (``--maximum-iterations``) in a reproduction run, together with the previously used seed.
  The amount of iterations can be obtained from stdout (when using ``-v`` for verbose output) or from the tracked statistics,
  when tracking the variable ``AlgorithmIterations``.


.. note::
  Pynguin's algorithms check the stopping condition at the beginning of each iteration,
  i.e., if the stopping condition is reached within an interation, this iteration will still be finished.
