#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class Settings(dict):  # noqa: FURB189
    def __getattr__(self, item):
        return self.get(item)


settings = Settings()
