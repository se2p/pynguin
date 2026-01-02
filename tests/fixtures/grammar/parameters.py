#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def positional_only(param1, param2=5, /):
    pass


def all_params(param1, /, param2, *param3, param4=0, **param5):
    pass
