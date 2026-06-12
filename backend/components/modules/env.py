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

import os

from dotenv import load_dotenv

load_dotenv(override=True)


def env_or_file(env_name: str, default: str | None = None) -> str | None:
    """Fetch an environment variable or the contents of a file specified by it.

    This is necessary for deploying with docker swarm.
    If the environment variable ``{env_name}_FILE`` is set and points to a file,
    read from the file. Otherwise, return the value of the environment variable
    named ``env_name``.

    Args:
        env_name: The name of the environment variable.
        default: The value to return if the environment variable is not set.

    Returns:
        The environment variable value, file contents, or default.
    """
    file_var = os.getenv(f"{env_name}_FILE")
    if file_var and os.path.isfile(file_var):
        with open(file_var, "r") as f:
            return f.read().strip()
    return os.getenv(env_name, default)