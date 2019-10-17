# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides methods for input value generation."""
import logging
import random
from enum import Enum
from functools import singledispatch, wraps
from typing import Optional, Any, List

from pynguin.utils.statements import Sequence
from pynguin.utils.string import String

LOGGER = logging.getLogger(__name__)


def value_dispatch(func):
    """See http://lukasz.langa.pl/8/single-dispatch-generic-functions/"""
    _func = singledispatch(func)

    @_func.register(Enum)
    def _enum_value_dispatch(*args, **kwargs):
        enum, value = args[0], args[0].value
        if value not in _func.registry:
            return _func.dispatch(object)(*args, **kwargs)
        dispatch = _func.registry[value]
        _func.register(enum, dispatch)
        return dispatch(*args, **kwargs)

    @wraps(func)
    def wrapper(*args, **kwargs):
        if args[0] in _func.registry:
            return _func.registry[args[0]](*args, **kwargs)
        return _func(*args, **kwargs)

    wrapper.register = _func.register
    wrapper.dispatch = _func.dispatch
    wrapper.registry = _func.registry
    return wrapper


# pylint: disable=unused-argument
@value_dispatch
def init_value(type_: Any, sequences: List[Sequence]) -> Optional[Any]:
    """A decorator for initialising generated values.

    :param type_: The type we are interested in
    :param sequences: The current list of sequences
    :return: An optional initialised value
    """
    # targets: List[Any] = []
    # for sequence in reversed(sequences):
    #     for statement in reversed(sequence):
    #         if isinstance(statement, Statement):  # was Assignment
    #             pass
    #                 assert isinstance(statement.rhs, Statement)  # was Call
    #                 if isinstance(statement.rhs.function, Statement):  # was Attribute
    #                     # call on variable
    #                     # TODO(sl) use once we record return values
    #                     LOGGER.debug("Reached: TODO(sl) use once we record return values")
    #                 elif (
    #                     hasattr(type_, "__name__")
    #                     and isinstance(statement.rhs.function, Statement)  # was Name
    #                     and type_.__name__ in statement.rhs.function.identifier
    #                 ):
    #                     # constructor or direct function call
    #                     # TODO(sl) this way we loose tuples and other builtin composita.
    #                     LOGGER.debug(
    #                         "Reached: TODO(sl) this way we loose tuples and other builtin"
    #                         " composita"
    #                     )
    #                     targets.append(statement.lhs)

    # if targets:
    #     value = random.choice(targets)
    # else:
    #     # Sometime we want None but most of the time, None will just fail with an
    #     # unusable TypeError anyways
    #     value = random.choice([1, None])
    # return value


@init_value.register(int)
def int_generator(_, __):
    """A generator for uniformly-distributed random integer values."""
    value = random.randint(-100, 100)
    return value


@init_value.register(String)
def str_generator(_, __):
    """A generator for random string values from the list of observed strings."""
    if len(String.observed) > 0:
        return String(random.choice(String.observed))
    return String("Test")


@init_value.register(bool)
def bool_generator(_, __):
    """A generator for uniformly-distributed random boolean values."""
    return bool(random.getrandbits(1))


@init_value.register(complex)
def complex_generator(_, __):
    """A generator for uniformly-distributed random complex values of integers."""
    real = random.randint(-100, 100)
    imaginary = random.randint(-100, 100)
    return complex(real, imaginary)


@init_value.register(float)
def float_generator(_, __):
    """A generator for uniformly-distributed random float values."""
    value = random.uniform(-100, 100)
    return value
