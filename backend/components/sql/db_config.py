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

# Central database configuration used by both the app and Alembic.
# Supports Docker secrets via _FILE suffix.
#
# Environment variables (in order of priority):
# 1. DATABASE_URI / DATABASE_URI_FILE  -> used directly as SQLAlchemy URI
# 2. SQL_USER, SQL_PASS, SQL_HOST, SQL_PORT, SQL_DB -> built into URI
#
# Examples:
#   DATABASE_URI=sqlite3:///test.sqlite3
#   SQL_USER_FILE=/run/secrets/db_user   SQL_PASS_FILE=/run/secrets/db_pass

from backend.components.modules.env import env_or_file

_SQL_USER = env_or_file("SQL_USER", "postgres")
_SQL_PASS = env_or_file("SQL_PASS", "postgres")
_SQL_HOST = env_or_file("SQL_HOST", "localhost")
_SQL_PORT = env_or_file("SQL_PORT", "5432")
_SQL_DB = env_or_file("SQL_DB", "aidox")

# Prefer direct DATABASE_URI, otherwise build from components
_RAW_URI = env_or_file("DATABASE_URI", None)

if _RAW_URI:
    RAW_URI = _RAW_URI
else:
    # Build PostgreSQL URI from components
    RAW_URI = f"postgresql+psycopg2://{_SQL_USER}:{_SQL_PASS}@{_SQL_HOST}:{_SQL_PORT}/{_SQL_DB}"

# Normalize for SQLAlchemy compatibility
if RAW_URI.startswith("sqlite3://"):
    SQLALCHEMY_URI = RAW_URI.replace("sqlite3://", "sqlite://", 1)
elif RAW_URI.startswith("postgresql://") and not RAW_URI.startswith(
    "postgresql+psycopg2://"
):
    SQLALCHEMY_URI = RAW_URI.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    SQLALCHEMY_URI = RAW_URI
