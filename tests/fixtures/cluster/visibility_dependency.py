#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.cluster.visibility import PublicClass


def uses_public_class(obj: PublicClass) -> int:
    return obj.public_method(1)
