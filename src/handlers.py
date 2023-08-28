import json
from io import BytesIO
import requests
from requests.exceptions import HTTPError
import kopf

import settings


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
            kopf.StatusDiffBaseStorage(field="status.diff-base"),
        ]
    )


labels: dict = {}
if settings.LABEL and settings.LABEL_VALUE:
    labels = {settings.LABEL: settings.LABEL_VALUE}
else:
    labels = {}


@kopf.on.create("vulnerabilityreports.aquasecurity.github.io", labels=labels)
def send_to_dojo(body, meta, logger, **_):
    """
    The main function that creates a report-file from the trivy-operator vulnerabilityreport
    and sends it to the defectdojo instance.
    """

    logger.info(f"Working on {meta['name']}")

    # body is the whole kubernetes manifest of a vulnerabilityreport
    # body is a Python-Object that is not json-serializable,
    # but body[kind], body[metadata] and so on are
    # so we create a new json-object here, since kopf does not provide this
    full_object: dict = {}
    for i in body:
        full_object[i] = body[i]

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
        "scan_type": "Trivy Operator Scan",
        "engagement_name": meta["creationTimestamp"],
        "product_name": body["report"]["artifact"]["repository"],
        "product_type_name": settings.DEFECT_DOJO_PRODUCT_TYPE_NAME,
        "test_title": settings.DEFECT_DOJO_TEST_TITLE,
    }

    try:
        response: requests.Response = requests.post(
            settings.DEFECT_DOJO_URL + "/api/v2/import-scan/",
            headers=headers,
            data=data,
            files=report_file,
            verify=False,
        )
        response.raise_for_status()
    except HTTPError as http_err:
        raise kopf.PermanentError(
            f"HTTP error occurred: {http_err} - {response.content}"
        )
    except Exception as err:
        raise kopf.PermanentError(f"Other error occurred: {err}")
    else:
        logger.info(f"Finished {meta['name']}")
        logger.debug(response.content)
