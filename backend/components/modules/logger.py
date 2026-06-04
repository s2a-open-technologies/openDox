# Standard Library
import os
import logging
from datetime import datetime

# Logging directory
LOG_DIR= "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"log_{datetime.now().strftime('%Y-%m-%d')}.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

def initialize_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=LOG_LEVEL,
        format="%(name)s - %(module)s - %(funcName)s - %(message)s",
        force=True
    )

def get_logger(name: str=__name__):
    """Returns a logger object with the specified name."""
    return logging.getLogger(name)