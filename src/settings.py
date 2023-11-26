import logging
import os
from env_vars import get_required_env_var, get_env_var_bool

logger = logging.getLogger(__name__)

LABEL = os.getenv("LABEL", None)
LABEL_VALUE = os.getenv("LABEL_VALUE", None)
if LABEL and LABEL_VALUE:
    logger.info(
        "Looking for resources with LABEL '%s' and LABEL_VALUE '%s'", LABEL, LABEL_VALUE
    )
elif LABEL:
    logger.info("Looking for resources with LABEL '%s'", LABEL)
else:
    logger.info("Looking for all resources")

DEFECT_DOJO_API_KEY: str = get_required_env_var("DEFECT_DOJO_API_KEY")
DEFECT_DOJO_URL: str = get_required_env_var("DEFECT_DOJO_URL")

DEFECT_DOJO_ACTIVE: bool = get_env_var_bool("DEFECT_DOJO_ACTIVE")
DEFECT_DOJO_VERIFIED: bool = get_env_var_bool("DEFECT_DOJO_VERIFIED")
DEFECT_DOJO_CLOSE_OLD_FINDINGS: bool = get_env_var_bool(
    "DEFECT_DOJO_CLOSE_OLD_FINDINGS"
)
DEFECT_DOJO_CLOSE_OLD_FINDINGS_PRODUCT_SCOPE: bool = get_env_var_bool(
    "DEFECT_DOJO_CLOSE_OLD_FINDINGS_PRODUCT_SCOPE"
)
DEFECT_DOJO_PUSH_TO_JIRA: bool = get_env_var_bool("DEFECT_DOJO_PUSH_TO_JIRA")
DEFECT_DOJO_MINIMUM_SEVERITY: str = os.getenv("DEFECT_DOJO_MINIMUM_SEVERITY", "Info")
DEFECT_DOJO_AUTO_CREATE_CONTEXT: bool = get_env_var_bool(
    "DEFECT_DOJO_AUTO_CREATE_CONTEXT"
)
DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT: bool = get_env_var_bool(
    "DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT"
)

DEFECT_DOJO_PRODUCT_TYPE_NAME: str = os.getenv(
    "DEFECT_DOJO_PRODUCT_TYPE_NAME", "Research and Development"
)
DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME: bool = get_env_var_bool(
    "DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME"
)

DEFECT_DOJO_TEST_TITLE: str = os.getenv("DEFECT_DOJO_TEST_TITLE", "Kubernetes")
DEFECT_DOJO_EVAL_TEST_TITLE: bool = get_env_var_bool("DEFECT_DOJO_EVAL_TEST_TITLE")

DEFECT_DOJO_ENGAGEMENT_NAME: str | None = os.getenv("DEFECT_DOJO_ENGAGEMENT_NAME")
DEFECT_DOJO_EVAL_ENGAGEMENT_NAME: bool = get_env_var_bool(
    "DEFECT_DOJO_EVAL_ENGAGEMENT_NAME"
)

DEFECT_DOJO_PRODUCT_NAME: str = os.getenv(
    "DEFECT_DOJO_PRODUCT_NAME", "Research and Development"
)
DEFECT_DOJO_EVAL_PRODUCT_NAME: bool = get_env_var_bool("DEFECT_DOJO_EVAL_PRODUCT_NAME")

DEFECT_DOJO_DO_NOT_REACTIVATE: bool = get_env_var_bool("DEFECT_DOJO_DO_NOT_REACTIVATE")
