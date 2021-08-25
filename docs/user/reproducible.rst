.. _reproducible:

Reproducible runs
=================

According to the `Python documentation <https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED>`_
it is necessary to set the environment variable ``PYTHONHASHSEED=0`` in order to
achieve a truly deterministic behaviour and computation.
Furthermore, it is necessary to set the ``--seed`` command-line option to a fixed value.
If no ``--seed`` option was set, Pynguin chooses a seed at random and logs its value.

.. note::
  Using a certain amount of wall-clock time as the stopping condition (``MAX_TIME``) for Pynguin's executions
  can make achieving deterministic results difficult, because Pynguin might achieve slightly different amounts of iterations in each execution.
  To solve this problem, take note of the amount of achieved iterations in the first execution and
  use them as the new stopping condition (``MAX_ITERATIONS``) in a reproduction run, together with the previously used seed.
  The amount of iterations can be obtained from stdout (when using ``-v`` for verbose output) or from the tracked statistics,
  when tracking the variable ``AlgorithmIterations``.
