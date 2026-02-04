import json
import kopf
import prometheus_client
import requests
import settings
import subprocess
import os

from requests.exceptions import HTTPError
from io import BytesIO

prometheus_client.start_http_server(9090)
REQUEST_TIME = prometheus_client.Summary(
    "request_processing_seconds", "Time spent processing request"
)
PROMETHEUS_DISABLE_CREATED_SERIES = True

c = prometheus_client.Counter("requests_total", "HTTP Requests", ["status"])

proxies = {
    "http": settings.HTTP_PROXY,
    "https": settings.HTTPS_PROXY,
} if settings.HTTP_PROXY or settings.HTTPS_PROXY else None

def check_allowed_reports(report: str):
    allowed_reports: list[str] = [
        "configauditreports",
        "vulnerabilityreports",
        "exposedsecretreports",
        "infraassessmentreports",
        "rbacassessmentreports",
    ]

    if report not in allowed_reports:
        print(
            f"[ERROR] report {report} is not allowed. Allowed reports: {allowed_reports}"
        )
        exit(1)


def run_transformation(raw_report: dict, logger) -> dict | None:
    """
    Runs the transformation script on the raw report using piping (stdin/stdout).
    Returns the transformed report as a dict or None if transformation failed.
    """
    try:
        # 1. Serialize Input
        input_data = json.dumps(raw_report)

        # 2. Execute Script via pipe
        cmd = [
            settings.TRANSFORMATION_INTERPRETER,
            settings.TRANSFORMATION_SCRIPT_PATH,
        ]
        logger.info(f"Executing transformation: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            env=os.environ,
            check=True,
        )

        # 3. Parse Output
        if not result.stdout.strip():
            logger.error("Transformation script returned empty stdout")
            return None

        transformed_data = json.loads(result.stdout)
        return transformed_data

    except subprocess.CalledProcessError as e:
        logger.error(f"Transformation script failed with exit code {e.returncode}")
        logger.error(f"Stderr: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse transformation output as JSON: {e}")
        logger.error(f"Raw output: {result.stdout[:500]}...")
        return None
    except Exception as e:
        logger.error(f"Error during transformation: {e}")
        return None


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """
    Configure kopf
    """

    # kopf randomly stops watching resources. setting timeouts is supposed to help.
    # see these issue for more info:
    # https://github.com/nolar/kopf/issues/957
    # https://github.com/nolar/kopf/issues/585
    # https://github.com/nolar/kopf/issues/955
    # see https://kopf.readthedocs.io/en/latest/configuration/#api-timeouts
    settings.watching.connect_timeout = 60
    settings.watching.server_timeout = 600
    settings.watching.client_timeout = 610

    # This function tells kopf to use the StatusDiffBaseStorage instead
    # of the annotations-based storage, because the annotation will get too large
    # for k8s to handle. see: https://github.com/kubernetes-sigs/kubebuilder/issues/2556
    settings.persistence.diffbase_storage = kopf.MultiDiffBaseStorage(
        [
            kopf.StatusDiffBaseStorage(
                field="status.diff-base",
                ignored_fields=["report.vulnerabilities"]
            ),
        ]
    )


labels: dict = {}
if settings.LABEL and settings.LABEL_VALUE:
    labels = {settings.LABEL: settings.LABEL_VALUE}
else:
    labels = {}

for report in settings.REPORTS:
    # check if reports are allowed
    check_allowed_reports(report)

    @REQUEST_TIME.time()
    @kopf.on.create(report.lower() + ".aquasecurity.github.io", labels=labels)
    def send_to_dojo(body, meta, logger, **_):
        """
        The main function that creates a report-file from the trivy-operator vulnerabilityreport
        and sends it to the defectdojo instance.
        """

        logger.info(f"Working on {body['kind']} {meta['name']}")

        # body is the whole kubernetes manifest of a vulnerabilityreport
        # body is a Python-Object that is not json-serializable,
        # but body[kind], body[metadata] and so on are
        # so we create a new json-object here, since kopf does not provide this
        full_object: dict = {}
        for i in body:
            full_object[i] = body[i]

        logger.debug(full_object)

        _DEFECT_DOJO_ENGAGEMENT_NAME = (
            eval(settings.DEFECT_DOJO_ENGAGEMENT_NAME)
            if settings.DEFECT_DOJO_EVAL_ENGAGEMENT_NAME
            else settings.DEFECT_DOJO_ENGAGEMENT_NAME
        )

        _DEFECT_DOJO_PRODUCT_NAME = (
            eval(settings.DEFECT_DOJO_PRODUCT_NAME)
            if settings.DEFECT_DOJO_EVAL_PRODUCT_NAME
            else settings.DEFECT_DOJO_PRODUCT_NAME
        )

        _DEFECT_DOJO_PRODUCT_TYPE_NAME = (
            eval(settings.DEFECT_DOJO_PRODUCT_TYPE_NAME)
            if settings.DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME
            else settings.DEFECT_DOJO_PRODUCT_TYPE_NAME
        )
        _DEFECT_DOJO_SERVICE_NAME = (
            eval(settings.DEFECT_DOJO_SERVICE_NAME)
            if settings.DEFECT_DOJO_EVAL_SERVICE_NAME
            else settings.DEFECT_DOJO_SERVICE_NAME
        )

        _DEFECT_DOJO_ENV_NAME = (
            eval(settings.DEFECT_DOJO_ENV_NAME)
            if settings.DEFECT_DOJO_EVAL_ENV_NAME
            else settings.DEFECT_DOJO_ENV_NAME
        )

        _DEFECT_DOJO_TEST_TITLE = (
            eval(settings.DEFECT_DOJO_TEST_TITLE)
            if settings.DEFECT_DOJO_EVAL_TEST_TITLE
            else settings.DEFECT_DOJO_TEST_TITLE
        )

        scan_type = "Trivy Operator Scan"
        if settings.TRANSFORMATION_ENABLED:
            logger.info("Transformation Hook is enabled")
            transformed_object = run_transformation(full_object, logger)
            if transformed_object:
                logger.info("Transformation successful")
                full_object = transformed_object
                scan_type = settings.DEFECT_DOJO_SCAN_TYPE_OVERRIDE
            else:
                logger.warning("Transformation failed, falling back to raw report")

        # define the vulnerabilityreport as a json-file so DD accepts it
        json_string: str = json.dumps(full_object)
        json_file: BytesIO = BytesIO(json_string.encode("utf-8"))
        report_file: dict = {"file": ("report.json", json_file)}

        headers: dict = {
            "Authorization": "Token " + settings.DEFECT_DOJO_API_KEY,
            "Accept": "application/json",
        }

        data: dict = {
            "active": settings.DEFECT_DOJO_ACTIVE,
            "verified": settings.DEFECT_DOJO_VERIFIED,
            "close_old_findings": settings.DEFECT_DOJO_CLOSE_OLD_FINDINGS,
            "close_old_findings_product_scope": settings.DEFECT_DOJO_CLOSE_OLD_FINDINGS_PRODUCT_SCOPE,
            "push_to_jira": settings.DEFECT_DOJO_PUSH_TO_JIRA,
            "minimum_severity": settings.DEFECT_DOJO_MINIMUM_SEVERITY,
            "auto_create_context": settings.DEFECT_DOJO_AUTO_CREATE_CONTEXT,
            "deduplication_on_engagement": settings.DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT,
            "scan_type": scan_type,
            "engagement_name": _DEFECT_DOJO_ENGAGEMENT_NAME,
            "product_name": _DEFECT_DOJO_PRODUCT_NAME,
            "product_type_name": _DEFECT_DOJO_PRODUCT_TYPE_NAME,
            "service": _DEFECT_DOJO_SERVICE_NAME,
            "environment": _DEFECT_DOJO_ENV_NAME,
            "test_title": _DEFECT_DOJO_TEST_TITLE,
            "do_not_reactivate": settings.DEFECT_DOJO_DO_NOT_REACTIVATE,
        }

        logger.debug(data)

        try:
            response: requests.Response = requests.post(
                settings.DEFECT_DOJO_URL + "/api/v2/reimport-scan/",
                headers=headers,
                data=data,
                files=report_file,
                verify=True,
                proxies=proxies,
            )
            response.raise_for_status()
        except HTTPError as http_err:
            c.labels("failed").inc()
            raise kopf.TemporaryError(
                f"HTTP error occurred: {http_err} - {response.content}. Retrying in 60 seconds",
                delay=60,
            )
        except Exception as err:
            c.labels("failed").inc()
            raise kopf.TemporaryError(
                f"Other error occurred: {err}. Retrying in 60 seconds", delay=60
            )
        else:
            c.labels("success").inc()
            logger.info(f"Finished {body['kind']} {meta['name']}")
            logger.debug(response.content)
