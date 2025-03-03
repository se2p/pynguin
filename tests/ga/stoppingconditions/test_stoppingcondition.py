#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pynguin.ga.stoppingcondition import StoppingCondition


class DummyStopping(StoppingCondition):
    def current_value(self) -> int:
        pass  # pragma: no cover

    def limit(self) -> int:
        pass  # pragma: no cover

    def is_fulfilled(self) -> bool:
        pass  # pragma: no cover

    def reset(self) -> None:
        pass  # pragma: no cover

    def set_limit(self, limit: int) -> None:
        pass  # pragma: no cover

    def __str__(self):
        return ""  # pragma: no cover


def test_nothing_on_after_test_case_execution():
    stopping = DummyStopping()
    stopping.after_remote_test_case_execution(None, None)
    # Nothing really to assert on


def test_nothing_on_before_search_start():
    stopping = DummyStopping()
    stopping.before_search_start(None)
    # Nothing really to assert on
