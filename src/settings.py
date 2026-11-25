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

DEFECT_DOJO_PRODUCT_TYPE_NAME: str = os.getenv("DEFECT_DOJO_PRODUCT_TYPE_NAME", "")
DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME: bool = get_env_var_bool(
    "DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME"
)

DEFECT_DOJO_SERVICE_NAME: str = os.getenv("DEFECT_DOJO_SERVICE_NAME", "")
DEFECT_DOJO_EVAL_SERVICE_NAME: bool = get_env_var_bool("DEFECT_DOJO_EVAL_SERVICE_NAME")

DEFECT_DOJO_ENV_NAME: str = os.getenv("DEFECT_DOJO_ENV_NAME", "Development")
DEFECT_DOJO_EVAL_ENV_NAME: bool = get_env_var_bool("DEFECT_DOJO_EVAL_ENV_NAME")

DEFECT_DOJO_TEST_TITLE: str = os.getenv("DEFECT_DOJO_TEST_TITLE", "Kubernetes")
DEFECT_DOJO_EVAL_TEST_TITLE: bool = get_env_var_bool("DEFECT_DOJO_EVAL_TEST_TITLE")

DEFECT_DOJO_TAGS: str = os.getenv("DEFECT_DOJO_TAGS", "")
DEFECT_DOJO_EVAL_TAGS: bool = get_env_var_bool("DEFECT_DOJO_EVAL_TAGS")
DEFECT_DOJO_APPLY_TAGS_TO_FINDINGS: bool = get_env_var_bool(
    "DEFECT_DOJO_APPLY_TAGS_TO_FINDINGS"
)
DEFECT_DOJO_APPLY_TAGS_TO_ENDPOINTS: bool = get_env_var_bool(
    "DEFECT_DOJO_APPLY_TAGS_TO_ENDPOINTS"
)
DEFECT_DOJO_VERSION: str = os.getenv("DEFECT_DOJO_VERSION", "")
DEFECT_DOJO_EVAL_VERSION: bool = get_env_var_bool("DEFECT_DOJO_EVAL_VERSION")
DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT: bool = get_env_var_bool(
    "DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT"
)
DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE: bool = get_env_var_bool(
    "DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE"
)

DEFECT_DOJO_ENGAGEMENT_NAME: str | None = os.getenv("DEFECT_DOJO_ENGAGEMENT_NAME")
DEFECT_DOJO_EVAL_ENGAGEMENT_NAME: bool = get_env_var_bool(
    "DEFECT_DOJO_EVAL_ENGAGEMENT_NAME"
)

DEFECT_DOJO_PRODUCT_NAME: str = os.getenv("DEFECT_DOJO_PRODUCT_NAME", "product")
DEFECT_DOJO_PRODUCT_DESCRIPTION: str = os.getenv(
    "DEFECT_DOJO_PRODUCT_DESCRIPTION", "Created by trivy-dojo-report-operator"
)
DEFECT_DOJO_EVAL_PRODUCT_NAME: bool = get_env_var_bool("DEFECT_DOJO_EVAL_PRODUCT_NAME")
DEFECT_DOJO_EVAL_PRODUCT_DESCRIPTION: bool = get_env_var_bool(
    "DEFECT_DOJO_EVAL_PRODUCT_DESCRIPTION"
)

DEFECT_DOJO_DO_NOT_REACTIVATE: bool = get_env_var_bool("DEFECT_DOJO_DO_NOT_REACTIVATE")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Only "false" (any case) disables it, so a missing env (image run without the chart) keeps it on.
DEFECT_DOJO_REPORTS_ENABLED: bool = (
    os.getenv("DEFECT_DOJO_REPORTS_ENABLED", "true").lower() != "false"
)
REPORTS: list = (
    os.getenv("REPORTS", "vulnerabilityreports").split(",")
    if DEFECT_DOJO_REPORTS_ENABLED
    else []
)

HTTP_PROXY: str = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
HTTPS_PROXY: str = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

TRANSFORMATION_ENABLED: bool = get_env_var_bool("TRANSFORMATION_ENABLED")
TRANSFORMATION_SCRIPT_PATH: str = os.getenv(
    "TRANSFORMATION_SCRIPT_PATH", "/scripts/transform.py"
)
TRANSFORMATION_INTERPRETER: str = os.getenv("TRANSFORMATION_INTERPRETER", "python3")
DEFECT_DOJO_SCAN_TYPE_OVERRIDE: str = os.getenv(
    "DEFECT_DOJO_SCAN_TYPE_OVERRIDE", "Generic Findings Import"
)

# Dependency-Track is opt-in: nothing below is required or validated unless it is enabled
# (dependency_track.py validates the values when it is imported).
DEPENDENCY_TRACK_REPORTS_ENABLED: bool = (
    os.getenv("DEPENDENCY_TRACK_REPORTS_ENABLED", "false").lower() == "true"
)
DEPENDENCY_TRACK_STATE_ANNOTATION = "dependency-track.trivy-dojo-report-operator/state"
DEPENDENCY_TRACK_URL: str = ""
DEPENDENCY_TRACK_API_KEY: str = ""
DEPENDENCY_TRACK_PROJECT_NAME: str = ""
DEPENDENCY_TRACK_PROJECT_VERSION: str = ""
if DEPENDENCY_TRACK_REPORTS_ENABLED:
    DEPENDENCY_TRACK_URL = get_required_env_var("DEPENDENCY_TRACK_URL")
    DEPENDENCY_TRACK_API_KEY = get_required_env_var("DEPENDENCY_TRACK_API_KEY")
    DEPENDENCY_TRACK_PROJECT_NAME = get_required_env_var(
        "DEPENDENCY_TRACK_PROJECT_NAME"
    )
    DEPENDENCY_TRACK_PROJECT_VERSION = get_required_env_var(
        "DEPENDENCY_TRACK_PROJECT_VERSION"
    )

# Like the DEFECT_DOJO_* names: used as is, or eval-ed per SbomReport (body, meta) when the
# matching EVAL flag is "true". An empty result skips the report.
DEPENDENCY_TRACK_EVAL_PROJECT_NAME: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_EVAL_PROJECT_NAME"
)
DEPENDENCY_TRACK_EVAL_PROJECT_VERSION: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_EVAL_PROJECT_VERSION"
)

DEPENDENCY_TRACK_PROJECT_TAGS: str = os.getenv("DEPENDENCY_TRACK_PROJECT_TAGS", "")
DEPENDENCY_TRACK_EVAL_PROJECT_TAGS: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_EVAL_PROJECT_TAGS"
)

DEPENDENCY_TRACK_ACL_TEAM: str = os.getenv("DEPENDENCY_TRACK_ACL_TEAM", "")
DEPENDENCY_TRACK_EVAL_ACL_TEAM: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_EVAL_ACL_TEAM"
)

DEPENDENCY_TRACK_GROUP_BY: str = os.getenv("DEPENDENCY_TRACK_GROUP_BY", "")
DEPENDENCY_TRACK_EVAL_GROUP_BY: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_EVAL_GROUP_BY"
)

DEPENDENCY_TRACK_DEFECT_DOJO_PRODUCT_NAME: str = os.getenv(
    "DEPENDENCY_TRACK_DEFECT_DOJO_PRODUCT_NAME", "product"
)
DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_PRODUCT_NAME: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_PRODUCT_NAME"
)

DEPENDENCY_TRACK_DEFECT_DOJO_PRODUCT_TYPE_NAME: str = os.getenv(
    "DEPENDENCY_TRACK_DEFECT_DOJO_PRODUCT_TYPE_NAME", "Research and Development"
)
DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME"
)

DEPENDENCY_TRACK_DEFECT_DOJO_ENGAGEMENT_NAME: str = os.getenv(
    "DEPENDENCY_TRACK_DEFECT_DOJO_ENGAGEMENT_NAME", "engagement"
)
DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_ENGAGEMENT_NAME: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_ENGAGEMENT_NAME"
)

DEPENDENCY_TRACK_DEFECT_DOJO_ENV_NAME: str = os.getenv(
    "DEPENDENCY_TRACK_DEFECT_DOJO_ENV_NAME", "Development"
)
DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_ENV_NAME: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_ENV_NAME"
)

DEPENDENCY_TRACK_DEFECT_DOJO_TEST_TITLE: str = os.getenv(
    "DEPENDENCY_TRACK_DEFECT_DOJO_TEST_TITLE", "Kubernetes"
)
DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_TEST_TITLE: bool = get_env_var_bool(
    "DEPENDENCY_TRACK_DEFECT_DOJO_EVAL_TEST_TITLE"
)
