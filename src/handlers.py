import json
import kopf
import prometheus_client
import settings
import asyncio
import httpx
import copy
from io import BytesIO

# --- Prometheus Metrics Setup ---
prometheus_client.start_http_server(9090)
REQUEST_TIME = prometheus_client.Summary(
    "request_processing_seconds", "Time spent processing request"
)
PROMETHEUS_DISABLE_CREATED_SERIES = True
c = prometheus_client.Counter("requests_total", "HTTP Requests", ["status"])

# --- Proxy Configuration ---
proxies = {
    "http://": settings.HTTP_PROXY,
    "https://": settings.HTTPS_PROXY,
} if settings.HTTP_PROXY or settings.HTTPS_PROXY else None

# --- Global Lock for Sequential Processing ---
report_processing_lock = asyncio.Lock()

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


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.watching.connect_timeout = 60
    settings.watching.server_timeout = 600
    settings.watching.client_timeout = 610
    settings.persistence.diffbase_storage = kopf.MultiDiffBaseStorage(
        [kopf.StatusDiffBaseStorage(field="status.diff-base")]
    )

# --- Label Configuration ---
labels: dict = {}
if settings.LABEL and settings.LABEL_VALUE:
    labels = {settings.LABEL: settings.LABEL_VALUE}

def get_defectdojo_payload(body, meta):
    """Helper function to generate the DefectDojo API payload."""
    engagement_name = eval(settings.DEFECT_DOJO_ENGAGEMENT_NAME) if settings.DEFECT_DOJO_EVAL_ENGAGEMENT_NAME else settings.DEFECT_DOJO_ENGAGEMENT_NAME
    product_name = eval(settings.DEFECT_DOJO_PRODUCT_NAME) if settings.DEFECT_DOJO_EVAL_PRODUCT_NAME else settings.DEFECT_DOJO_PRODUCT_NAME
    product_type_name = eval(settings.DEFECT_DOJO_PRODUCT_TYPE_NAME) if settings.DEFECT_DOJO_EVAL_PRODUCT_TYPE_NAME else settings.DEFECT_DOJO_PRODUCT_TYPE_NAME
    service_name = eval(settings.DEFECT_DOJO_SERVICE_NAME) if settings.DEFECT_DOJO_EVAL_SERVICE_NAME else settings.DEFECT_DOJO_SERVICE_NAME
    env_name = eval(settings.DEFECT_DOJO_ENV_NAME) if settings.DEFECT_DOJO_EVAL_ENV_NAME else settings.DEFECT_DOJO_ENV_NAME
    test_title = eval(settings.DEFECT_DOJO_TEST_TITLE) if settings.DEFECT_DOJO_EVAL_TEST_TITLE else settings.DEFECT_DOJO_TEST_TITLE

    return {
        "active": settings.DEFECT_DOJO_ACTIVE,
        "verified": settings.DEFECT_DOJO_VERIFIED,
        "close_old_findings": settings.DEFECT_DOJO_CLOSE_OLD_FINDINGS,
        "close_old_findings_product_scope": settings.DEFECT_DOJO_CLOSE_OLD_FINDINGS_PRODUCT_SCOPE,
        "push_to_jira": settings.DEFECT_DOJO_PUSH_TO_JIRA,
        "minimum_severity": settings.DEFECT_DOJO_MINIMUM_SEVERITY,
        "auto_create_context": settings.DEFECT_DOJO_AUTO_CREATE_CONTEXT,
        "deduplication_on_engagement": settings.DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT,
        "scan_type": "Trivy Scan",
        "engagement_name": engagement_name,
        "product_name": product_name,
        "product_type_name": product_type_name,
        "service": service_name,
        "environment": env_name,
        "test_title": test_title,
        "do_not_reactivate": settings.DEFECT_DOJO_DO_NOT_REACTIVATE,
    }

# --- Asynchronous Handler for Vulnerability Reports (with batching) ---
@REQUEST_TIME.time()
@kopf.on.create("vulnerabilityreports.aquasecurity.github.io", labels=labels)
async def send_vulns_to_dojo_async(body, meta, logger, **_):
    """
    Asynchronously processes vulnerability reports one at a time,
    and sends vulnerabilities to DefectDojo in batches.
    """
    async with report_processing_lock:
        logger.info(f"Acquired lock for VulnerabilityReport {meta['name']}. Processing...")

        # FIX: Convert the kopf.Body object to a standard Python dict
        plain_body = dict(body)

        headers = {"Authorization": f"Token {settings.DEFECT_DOJO_API_KEY}"}
        data = get_defectdojo_payload(plain_body, meta)
        
        vulnerabilities = plain_body.get("report", {}).get("vulnerabilities", [])
        total_vulnerabilities = len(vulnerabilities)
        batch_size = getattr(settings, 'VULNERABILITY_BATCH_SIZE', 100)
        
        if total_vulnerabilities == 0:
            logger.info(f"Report {meta['name']} has no vulnerabilities. Skipping API call.")
            return

        logger.info(f"Found {total_vulnerabilities} vulnerabilities in {meta['name']}. Processing in batches of {batch_size}.")

        async with httpx.AsyncClient(proxies=proxies, verify=True) as client:
            for i in range(0, total_vulnerabilities, batch_size):
                batch_vulnerabilities = vulnerabilities[i:i + batch_size]
                batch_body = copy.deepcopy(plain_body)
                batch_body["report"]["vulnerabilities"] = batch_vulnerabilities
                
                json_string = json.dumps(batch_body)
                report_file = {"file": ("report.json", json_string.encode('utf-8'), "application/json")}
                
                logger.info(f"Sending batch {i//batch_size + 1}/{(total_vulnerabilities + batch_size - 1)//batch_size} to DefectDojo...")

                try:
                    response = await client.post(
                        f"{settings.DEFECT_DOJO_URL}/api/v2/reimport-scan/",
                        headers=headers,
                        data=data,
                        files=report_file,
                        timeout=300
                    )
                    response.raise_for_status()
                    c.labels("success").inc()
                    logger.info(f"Successfully sent batch for {meta['name']}.")
                    logger.debug(response.json())
                except httpx.HTTPStatusError as http_err:
                    c.labels("failed").inc()
                    logger.error(f"HTTP error for {meta['name']}: {http_err} - {http_err.response.text}")
                    raise kopf.TemporaryError(f"HTTP error occurred: {http_err}. Retrying...", delay=60)
                except Exception as err:
                    c.labels("failed").inc()
                    logger.error(f"An unexpected error occurred for {meta['name']}: {err}")
                    raise kopf.TemporaryError(f"Other error occurred: {err}. Retrying...", delay=60)
        
        logger.info(f"Successfully processed and released lock for VulnerabilityReport {meta['name']}.")

# --- Synchronous Handler for Other Report Types ---
other_reports = [r for r in settings.REPORTS if r != "vulnerabilityreports"]
for report in other_reports:
    check_allowed_reports(report)

    @REQUEST_TIME.time()
    @kopf.on.create(f"{report.lower()}.aquasecurity.github.io", labels=labels)
    def send_other_reports_to_dojo(body, meta, logger, **_):
        logger.info(f"Working on {body['kind']} {meta['name']}")

        full_object = {i: body[i] for i in body}
        json_string = json.dumps(full_object)
        report_file = {"file": ("report.json", json_string.encode('utf-8'), "application/json")}
        
        headers = {"Authorization": f"Token {settings.DEFECT_DOJO_API_KEY}"}
        data = get_defectdojo_payload(full_object, meta)
        
        logger.debug(data)

        try:
            import requests 
            response = requests.post(
                f"{settings.DEFECT_DOJO_URL}/api/v2/reimport-scan/",
                headers=headers,
                data=data,
                files=report_file,
                verify=True,
                proxies=proxies,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            c.labels("failed").inc()
            raise kopf.TemporaryError(f"HTTP error: {http_err} - {response.text}. Retrying...", delay=60)
        except Exception as err:
            c.labels("failed").inc()
            raise kopf.TemporaryError(f"Other error: {err}. Retrying...", delay=60)
        else:
            c.labels("success").inc()
            logger.info(f"Finished {body['kind']} {meta['name']}")
            logger.debug(response.content)