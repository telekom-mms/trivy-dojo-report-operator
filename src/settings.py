import logging
import os
from env_vars import get_required_env_var

logger = logging.getLogger(__name__)

LABEL = os.getenv('LABEL', None)
LABEL_VALUE = os.getenv('LABEL_VALUE', None)
if LABEL and LABEL_VALUE:
    logger.info("Looking for resources with LABEL '%s' and LABEL_VALUE '%s'", LABEL, LABEL_VALUE)
elif LABEL:
    logger.info("Looking for resources with LABEL '%s'", LABEL)
else:
    logger.info("Looking for all resources")

DEFECT_DOJO_API_KEY = get_required_env_var('DEFECT_DOJO_API_KEY')
DEFECT_DOJO_URL = get_required_env_var('DEFECT_DOJO_URL')

DEFECT_DOJO_ACTIVE = os.getenv('DEFECT_DOJO_ACTIVE', True)
DEFECT_DOJO_VERIFIED = os.getenv('DEFECT_DOJO_VERIFIED', False)
DEFECT_DOJO_CLOSE_OLD_FINDINGS = os.getenv('DEFECT_DOJO_CLOSE_OLD_FINDINGS', False)
DEFECT_DOJO_CLOSE_OLD_FINDINGS_PRODUCT_SCOPE = os.getenv('DEFECT_DOJO_CLOSE_OLD_FINDINGS_PRODUCT_SCOPE', False)
DEFECT_DOJO_PUSH_TO_JIRA = os.getenv('DEFECT_DOJO_PUSH_TO_JIRA', False)
DEFECT_DOJO_MINIMUM_SEVERITY = os.getenv('DEFECT_DOJO_MINIMUM_SEVERITY', "Info")
DEFECT_DOJO_AUTO_CREATE_CONTEXT = os.getenv('DEFECT_DOJO_AUTO_CREATE_CONTEXT', True)
DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT = os.getenv('DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT', True)
DEFECT_DOJO_PRODUCT_TYPE_NAME = os.getenv('DEFECT_DOJO_PRODUCT_TYPE_NAME', "Research and Development")
DEFECT_DOJO_TEST_TITLE = os.getenv('DEFECT_DOJO_TEST_TITLE', "Kubernetes")
