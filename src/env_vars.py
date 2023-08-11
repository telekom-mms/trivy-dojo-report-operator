import os
import logging

logger = logging.getLogger(__name__)

def get_required_env_var(name):
    """Returns value of a required environment variable. Fails if not found"""
    try:
        return os.environ[name]
    except KeyError:
        logger.error(f"{name} environment variable is required! Exiting.")
        exit(1)

def get_env_var_bool(name):
    """Gets value of environment variable as a boolean. If not 'true', returns False"""
    return os.getenv(name) == 'true'
