#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.complexassertion as ca


def test_accept():
    visitor = MagicMock()
    assertion = ca.ComplexAssertion(MagicMock(), 1337)
    assertion.accept(visitor)
    visitor.visit_complex_assertion.assert_called_with(assertion)


def test_clone():
    source = MagicMock()
    cloned_ref = MagicMock()
    source.clone.return_value = cloned_ref
    assertion = ca.ComplexAssertion(source, 1337)
    new_test_case = MagicMock()
    cloned = assertion.clone(new_test_case, 20)
    source.clone.assert_called_with(new_test_case, 20)
    assert cloned.source == cloned_ref
    assert cloned.value == 1337
