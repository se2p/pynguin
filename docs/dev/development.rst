Development Hints
=================

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
