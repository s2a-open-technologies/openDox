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

# Logging directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"log_{datetime.now().strftime('%Y-%m-%d')}.log")

# Ensure project root is on sys.path for config import
import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from config import env_or_file  # noqa: E402

LOG_LEVEL = env_or_file("LOG_LEVEL", "INFO")


def initialize_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=LOG_LEVEL,
        format="%(name)s - %(module)s - %(funcName)s - %(message)s",
        force=True,
    )


def get_logger(name: str = __name__):
    """Returns a logger object with the specified name."""
    return logging.getLogger(name)
