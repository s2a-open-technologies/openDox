"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# Standard Library
import logging

# Third-party
from uvicorn.logging import DefaultFormatter

# Custom
from backend.components.modules.env import env_or_file

LOG_LEVEL = env_or_file("LOG_LEVEL", "INFO")


def initialize_logging():
    """Attach a stdout handler to the root logger.

    Must not depend on uvicorn having already configured its own
    "uvicorn.error"/"uvicorn.access" handlers: create_app() runs during app
    import, which can happen before uvicorn sets those up. The previous
    implementation tried to borrow uvicorn's handlers at that point, found
    none yet configured, and left the root logger with zero handlers —
    every application log line was silently dropped, with no error, ever.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Remove existing handlers to avoid duplicates on repeated calls.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    # Same look as uvicorn's own lines ("INFO:     message", coloured on a
    # TTY), but our own handler: uvicorn's are not configured yet at import.
    formatter = DefaultFormatter("%(levelprefix)s %(message)s")
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # Do NOT set propagate=False on uvicorn.error/uvicorn.access here:
    # uvicorn.error has no handlers of its own — its records (including the
    # "Uvicorn running on ..." banner) reach a handler only by propagating
    # to the parent "uvicorn" logger. uvicorn's own config already stops
    # propagation at "uvicorn"/"uvicorn.access", so nothing is doubled.
    for name in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(LOG_LEVEL)


def get_logger(name: str | None = None):
    """Return a logger; pass ``__name__`` so records name their module.

    Without a name the root logger is used, so no record is attributed to this
    helper module.
    """
    return logging.getLogger(name)
