#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.primitiveassertion as pa


def test_accept():
    visitor = MagicMock()
    assertion = pa.PrimitiveAssertion(MagicMock(), 1337)
    assertion.accept(visitor)
    visitor.visit_primitive_assertion.assert_called_with(assertion)


def test_clone():
    source = MagicMock()
    cloned_ref = MagicMock()
    source.clone.return_value = cloned_ref
    assertion = pa.PrimitiveAssertion(source, 1337)
    new_test_case = MagicMock()
    cloned = assertion.clone(new_test_case, 20)
    source.clone.assert_called_with(new_test_case, 20)
    assert cloned.source == cloned_ref
    assert cloned.value == 1337
