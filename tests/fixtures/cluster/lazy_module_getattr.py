#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import sys


_this = sys.modules[__name__]


def __getattr__(name):
    # PEP 562 module-level lazy loader that caches its result back into the
    # module globals (mimicking litellm's ``__getattr__``).  Accessing a missing
    # attribute inserts a new key into this module's ``__dict__``.
    value = len(_this.__dict__)
    _this.__dict__[name] = value
    return value


class _Meta(type):
    def __getattribute__(cls, name):
        if name == "__module__":
            # Reading ``__module__`` (as ``inspect.getsource`` does) triggers the
            # module-level lazy loader, which mutates the module globals.
            getattr(_this, "_lazy_%d" % len(_this.__dict__))
        return super().__getattribute__(name)


class Trigger(metaclass=_Meta):
    def run(self):
        return 1
