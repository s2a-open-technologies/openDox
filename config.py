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

# Standard library
import os

# Third Party
from dotenv import load_dotenv

# Getting environment variables
load_dotenv()


def env_or_file(env_name, default=None):
    """Fetches an environment variable or the contents of a file specified by the environment variable.

    If the environment variable ``{env_name}_FILE`` is set and points to a file,
    read from the file. Otherwise, return the value of the environment variable
    named ``env_name``.

    Args:
        env_name (str): The name of the environment variable.
        default (str, optional): The value to return if the environment variable is not set. Defaults to None.
    """
    file_var = os.getenv(f"{env_name}_FILE")
    if file_var and os.path.isfile(file_var):
        with open(file_var, "r") as file:
            return file.read().strip()
    return os.getenv(env_name, default)


class Config:
    """Configuration class for application settings."""

    SECRET_KEY = env_or_file("SECRET_KEY", "12345678")
    SQLALCHEMY_URI = env_or_file("DATABASE_URI", "sqlite3:///test.sqlite3")
