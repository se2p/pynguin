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
"""Provides a simple implementation of a variable reference."""
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr


class VariableReferenceImpl(vr.VariableReference):
    """
    Basic implementation of a variable reference.
    """

    def clone(self, test_case: tc.TestCase) -> vr.VariableReference:
        return VariableReferenceImpl(test_case, self.variable_type)
