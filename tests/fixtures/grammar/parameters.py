#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def positional_only(param1, param2=5, /):
    pass


def all_params(param1, /, param2, *param3, param4=0, **param5):
    pass
