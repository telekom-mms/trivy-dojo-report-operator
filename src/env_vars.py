import logging
import os
import sys

logger = logging.getLogger(__name__)


def get_required_env_var(name: str) -> str:
    """Return the value of a required environment variable or exit if not set."""
    try:
        return os.environ[name]
    except KeyError:
        logger.error(f"{name} environment variable is required! Exiting.")
        sys.exit(1)


def get_env_var_bool(name):
    """Gets value of environment variable as a boolean. If not 'true', returns False"""
    return os.getenv(name) == "true"
