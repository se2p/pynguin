#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import logging


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def log_to_null():
    logger = logging.getLogger()
    logger.addHandler(NullHandler())
