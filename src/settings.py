import kopf
import logging
import os
from env_vars import get_required_env_var, get_env_var_bool

# Here we use Kopf's logging macro to setup the logging format and level for all modules
DEBUG = get_env_var_bool("DEBUG")
kopf.configure(
    debug=DEBUG
)

logger = logging.getLogger(__name__)

if DEBUG:
    logger.info("DEBUG mode is activated!")

LABEL = os.getenv('LABEL')
LABEL_VALUE = os.getenv('LABEL_VALUE')
if LABEL_VALUE:
    logger.info("Looking for resources with LABEL '%s' and LABEL_VALUE '%s'", LABEL, LABEL_VALUE)
else:
    logger.info("Looking for resources with LABEL '%s'", LABEL)

NAMESPACE = os.getenv('NAMESPACE', 'ALL')
if NAMESPACE == 'ALL':
    logger.info("Looking for resources in the entire cluster")
else:
    NAMESPACE = NAMESPACE.replace(" ", "").split(',')
    logger.info(f"Looking for resources only in the {NAMESPACE} namespaces")

DEFECT_DOJO_API_KEY = get_required_env_var('DEFECT_DOJO_API_KEY')
DEFECT_DOJO_URL = get_required_env_var('DEFECT_DOJO_URL')
