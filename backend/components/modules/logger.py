"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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
import os
from datetime import datetime

# Ensure project root is on sys.path for config import
import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from config import env_or_file  # noqa: E402

LOG_LEVEL = env_or_file("LOG_LEVEL", "INFO")


def initialize_logging():
    """Initialize logging to use uvicorn's logging system."""
    # Configure uvicorn loggers
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.setLevel(LOG_LEVEL)

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(LOG_LEVEL)

    # Configure root logger to use uvicorn.error handler
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add uvicorn.error handler to root logger
    for handler in uvicorn_error_logger.handlers:
        root_logger.addHandler(handler)


def get_logger(name: str = __name__):
    """Returns a logger object that writes to uvicorn.error stream.

    This ensures all application logs are captured by uvicorn's
    logging system and appear in uvicorn's log output.
    """
    return logging.getLogger(name)
