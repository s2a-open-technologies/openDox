
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
    
 