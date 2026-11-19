#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import logging
import threading

release = threading.Event()


class RedirectingHandler(logging.Handler):
    def emit(self, record):
        pass


def redirect_root_logging_and_block():
    """Installs a root logger handler, then blocks where no exception reaches it."""
    logging.root.addHandler(RedirectingHandler())
    release.wait()
