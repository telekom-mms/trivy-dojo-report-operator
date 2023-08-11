import json
from io import BytesIO
import requests
from requests.exceptions import HTTPError
import kopf

import settings

# we cannot use annotations-based diffbase_storage
# because kopf creates a annotation that contains the last applied
# state. this anootation will be too large too handle for k8s and cannot
# be added to the object.
@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.persistence.diffbase_storage = kopf.MultiDiffBaseStorage(
        [
            kopf.StatusDiffBaseStorage(field="status.diff-base"),
        ]
    )

if settings.LABEL and settings.LABEL_VALUE:
    labels={settings.LABEL: settings.LABEL_VALUE}
else:
    labels={}

@kopf.on.create(
    "vulnerabilityreports.aquasecurity.github.io",
    labels=labels
)
def send_to_dojo(body, meta, logger, **_):

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
        "active": "true",
        "verified": "false",
        "close_old_findings": "false",
        "close_old_findings_product_scope": "false",
        "push_to_jira": "false",
        "minimum_severity": "Info",
        "auto_create_context": "true",
        "deduplication_on_engagement": "true",
        "scan_type": "Trivy Operator Scan",
        "engagement_name": meta["creationTimestamp"],
        "product_name": body["report"]["artifact"]["repository"],
        #"product_type_name": "Research and Development",
        "test_title": "kubernetes",
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
        raise kopf.PermanentError(f"HTTP error occurred: {http_err} - {response.content}")
    except Exception as err:
        raise kopf.PermanentError(f"Other error occurred: {err}")
    else:
        logger.info(f"Finished {meta['name']}")
        logger.debug(response.content)
