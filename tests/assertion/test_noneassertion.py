#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.noneassertion as na


def test_accept():
    visitor = MagicMock()
    assertion = na.NoneAssertion(MagicMock(), True)
    assertion.accept(visitor)
    visitor.visit_none_assertion.assert_called_with(assertion)


def test_clone():
    source = MagicMock()
    cloned_ref = MagicMock()
    source.clone.return_value = cloned_ref
    assertion = na.NoneAssertion(source, True)
    cloned = assertion.clone({})
    source.clone.assert_called_with({})
    assert cloned.source == cloned_ref
    assert cloned.value
