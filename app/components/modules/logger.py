# Standard Library
import os
import logging
from datetime import datetime

# Logging directory
LOG_DIR= "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"log_{datetime.now().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(name)s - %(module)s - %(funcName)s - %(message)s",
)

def get_logger(name: str):
    """Returns a logger object with the specified name."""
    return logging.getLogger(name)