"""
Send Trivy Operator SbomReports to Dependency-Track and link the project to DefectDojo.

For every eligible SbomReport the handler uploads the CycloneDX BOM, makes sure the
DefectDojo Product exists, creates the engagement and test with an empty FPF reimport,
sets the Dependency-Track integration properties and, optionally, maps the project to
a Dependency-Track team. Dependency-Track itself analyzes the BOM and exports the
findings to DefectDojo asynchronously, so the handler never waits for the analysis.

Imported (and its handlers registered) only when DEPENDENCY_TRACK_REPORTS_ENABLED=true.
"""

import hashlib
import json
import logging
import re
import sys
import threading
import uuid
from urllib.parse import urlparse

import kopf
import prometheus_client
import requests

import settings

logger = logging.getLogger(__name__)

RESOURCE = "sbomreports.aquasecurity.github.io"
STATE_ANNOTATION = settings.DEPENDENCY_TRACK_STATE_ANNOTATION
TIMEOUT = (10, 120)  # connect, read
RETRIES = 10
RETRY_DELAY = 60
PAGE_SIZE = 100
MAX_PAGES = 50

DD_SCAN_TYPE = "Dependency Track Finding Packaging Format (FPF) Export"
EMPTY_FPF = b'{"findings": []}\n'
# The eval-ed description is written for the DefectDojo flow's report context, which does not fit an SbomReport.
DEFAULT_PRODUCT_DESCRIPTION = "Created by trivy-dojo-report-operator"

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
_TOP_LEVEL_KEYS = {
    "registries",
    "default",
    "prefixes",
    "namespaces",
    "repositories",
    "exclude",
    "defectDojo",
}
_ENTRY_KEYS = {"env", "productType", "environment", "tags", "aclTeam"}
_NAMESPACE_KEYS = _ENTRY_KEYS | {"namespace"}
_DEFECT_DOJO_DEFAULTS = {
    "engagement": "dependency-track",
    "product": "{namespace}-{env}",
    "testTitle": "{namespace}/{name}",
    "groupBy": None,
}
DEFAULT_TAGS = ["{env}", "{namespace}"]
# Fictional identity used to check templates at startup.
_SAMPLE = {"namespace": "ns", "name": "name", "env": "env"}


def validate_identity(namespace: str, name: str | None) -> None:
    """Raise ValueError unless namespace (and name, unless None) can be used in project and product names."""
    if not isinstance(namespace, str) or not _TOKEN.fullmatch(namespace):
        raise ValueError("namespace must be non-empty and contain only [A-Za-z0-9._-]")
    if name is not None and (not isinstance(name, str) or not _NAME.fullmatch(name)):
        raise ValueError("name must be non-empty and contain only [A-Za-z0-9._/-]")


def parse_url(name: str, raw: str) -> str:
    """Return the http(s) URL without trailing slash; raise ValueError for anything else."""
    url = urlparse(raw.strip())
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username
        or url.query
        or url.fragment
    ):
        raise ValueError(
            f"{name} must be an http(s) URL without credentials, query or fragment"
        )
    return raw.strip().rstrip("/")


def format_template(template: str, **values: str) -> str:
    """str.format with the identity fields; a bad placeholder raises ValueError (never echoes the template)."""
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError, AttributeError):
        raise ValueError("invalid placeholder or brace in template") from None


def _non_empty_str(value) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def base_entry(k8s_ns: str, default: dict | None, prefixes: dict) -> dict | None:
    """The entry of the longest matching prefix (namespace = k8s ns minus it), else default (namespace = k8s ns)."""
    for p in sorted(prefixes, key=len, reverse=True):
        if k8s_ns.startswith(p) and len(k8s_ns) > len(p):
            return {**prefixes[p], "namespace": k8s_ns[len(p) :]}
    return {**default, "namespace": k8s_ns} if default else None


def parse_dependency_track_identities(raw: str) -> dict:
    """
    Validate DEPENDENCY_TRACK_IDENTITIES and fill the defaults:
    {
      "registries": ["<registry>"],                       # optional; absent or [] means all
      "default": {<entry without namespace>},             # optional; any other k8s ns, as is
      "prefixes": {"<prefix>": {<entry without namespace>}},  # optional; k8s ns minus the prefix
      "namespaces": {"<k8s ns>": {                        # optional overrides, merged onto the
          "namespace": "...", "env": "...",               # matching prefix or default entry;
          "productType": "...", "environment": "...",     # complete without one
          "tags": ["{env}", "{namespace}"],               # optional templates
          "aclTeam": "..."}},                             # optional; absent skips the ACL
      # at least one of default, prefixes or namespaces is required
      "repositories": {"<k8s ns>/<repository>": {"name": "...", "namespace": "..."}},  # optional
      "exclude": {"<label key>": ["<value>"]},            # optional
      "defectDojo": {"engagement": "...", "product": "...", "testTitle": "...", "groupBy": "..."}
    }
    Templates use {namespace}, {name}, {env} and, except in "product", {product}.
    Errors never echo the input.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("DEPENDENCY_TRACK_IDENTITIES is not valid JSON") from None
    if (
        not isinstance(data, dict)
        or not data.keys() & {"default", "prefixes", "namespaces"}
        or not data.keys() <= _TOP_LEVEL_KEYS
    ):
        raise ValueError(
            "DEPENDENCY_TRACK_IDENTITIES must be an object with default, prefixes and/or "
            "namespaces and optionally registries, repositories, exclude and defectDojo"
        )
    prefix = "DEPENDENCY_TRACK_IDENTITIES"

    registries = data.get("registries", [])
    if not isinstance(registries, list) or not all(
        _non_empty_str(r) for r in registries
    ):
        raise ValueError(f"{prefix}.registries must be a list of non-empty strings")

    defect_dojo = data.get("defectDojo", {})
    if (
        not isinstance(defect_dojo, dict)
        or not defect_dojo.keys() <= _DEFECT_DOJO_DEFAULTS.keys()
    ):
        raise ValueError(
            f"{prefix}.defectDojo must be an object with only engagement, product, testTitle and/or groupBy"
        )
    defect_dojo = {**_DEFECT_DOJO_DEFAULTS, **defect_dojo}
    for key, value in defect_dojo.items():
        if value is None and key == "groupBy":
            continue
        if not _non_empty_str(value):
            raise ValueError(f"{prefix}.defectDojo.{key} must be a non-empty string")
    try:
        product = format_template(defect_dojo["product"], **_SAMPLE)
        format_template(defect_dojo["testTitle"], **_SAMPLE, product=product)
    except ValueError as err:
        raise ValueError(f"{prefix}.defectDojo: {err}") from None

    def check_entry(where: str, entry, keys: set) -> dict:
        """Validate one complete identity entry (with namespace when it is in keys)."""
        required = {"env", "productType", "environment"} | (keys - _ENTRY_KEYS)
        if (
            not isinstance(entry, dict)
            or not required <= entry.keys()
            or not entry.keys() <= keys
        ):
            raise ValueError(
                f"{where} needs {', '.join(sorted(required))} and optionally tags, aclTeam"
            )
        if "namespace" in entry:
            try:
                validate_identity(entry["namespace"], None)
            except ValueError as err:
                raise ValueError(f"{where}: {err}") from None
        for key in ("env", "productType", "environment", "aclTeam"):
            if key in entry and not _non_empty_str(entry[key]):
                raise ValueError(f"{where}.{key} must be a non-empty string")
        entry = {"tags": list(DEFAULT_TAGS), **entry}
        if (
            not isinstance(entry["tags"], list)
            or not entry["tags"]
            or not all(isinstance(t, str) for t in entry["tags"])
        ):
            raise ValueError(f"{where}.tags must be a non-empty list of strings")
        for template in entry["tags"]:
            try:
                tag = format_template(template, **_SAMPLE, product=product)
            except ValueError as err:
                raise ValueError(f"{where}.tags: {err}") from None
            if not tag or "," in tag:
                raise ValueError(
                    f"{where}.tags must produce non-empty tags without commas"
                )
        return entry

    default = data.get("default")
    if default is not None:
        default = check_entry(f"{prefix}.default", default, _ENTRY_KEYS)
    prefixes = data.get("prefixes", {})
    if not isinstance(prefixes, dict) or not all(_non_empty_str(k) for k in prefixes):
        raise ValueError(f"{prefix}.prefixes must map non-empty prefixes to entries")
    prefixes = {
        k: check_entry(f"{prefix}.prefixes['{k}']", v, _ENTRY_KEYS)
        for k, v in prefixes.items()
    }
    namespaces = data.get("namespaces", {})
    if not isinstance(namespaces, dict):
        raise ValueError(f"{prefix}.namespaces must be an object")
    namespaces = {
        k8s_ns: check_entry(
            f"{prefix}.namespaces['{k8s_ns}']",
            (
                {**(base_entry(k8s_ns, default, prefixes) or {}), **entry}
                if isinstance(entry, dict)
                else entry
            ),
            _NAMESPACE_KEYS,
        )
        for k8s_ns, entry in namespaces.items()
    }
    if not (default or prefixes or namespaces):
        raise ValueError(
            f"{prefix} must map at least one namespace (default, prefixes or namespaces)"
        )

    repositories = data.get("repositories", {})
    if not isinstance(repositories, dict):
        raise ValueError(f"{prefix}.repositories must be an object")
    for key, override in repositories.items():
        k8s_ns, _, repository = key.partition("/")
        if not repository or not (
            k8s_ns in namespaces or base_entry(k8s_ns, default, prefixes)
        ):
            raise ValueError(
                f"{prefix}.repositories key '{key}' must be '<k8s namespace>/<repository>' of a mapped namespace"
            )
        if not isinstance(override, dict) or not override.keys() <= {
            "name",
            "namespace",
        }:
            raise ValueError(
                f"{prefix}.repositories['{key}'] must be an object with only name and/or namespace"
            )
        try:
            validate_identity(override.get("namespace", "x"), override.get("name", "x"))
        except ValueError as err:
            raise ValueError(f"{prefix}.repositories['{key}']: {err}") from None

    exclude = data.get("exclude", {})
    if not isinstance(exclude, dict) or not all(
        _non_empty_str(k)
        and isinstance(v, list)
        and v
        and all(_non_empty_str(x) for x in v)
        for k, v in exclude.items()
    ):
        raise ValueError(
            f"{prefix}.exclude must map label keys to non-empty lists of values"
        )

    return {
        "registries": registries,
        "default": default,
        "prefixes": prefixes,
        "namespaces": namespaces,
        "repositories": repositories,
        "exclude": exclude,
        "defectDojo": defect_dojo,
    }


try:
    DT_URL = parse_url("DEPENDENCY_TRACK_URL", settings.DEPENDENCY_TRACK_URL)
    if not settings.DEPENDENCY_TRACK_API_KEY.strip():
        raise ValueError("DEPENDENCY_TRACK_API_KEY must not be empty")
    IDENTITIES = parse_dependency_track_identities(settings.DEPENDENCY_TRACK_IDENTITIES)
except ValueError as err:
    logger.error(f"Invalid Dependency-Track configuration: {err} Exiting.")
    sys.exit(1)
if DT_URL.startswith("http://"):
    logger.warning("DEPENDENCY_TRACK_URL uses http: the API key is sent unencrypted")

c = prometheus_client.Counter(
    "dependency_track_reports_total", "SbomReports handled", ["status"]
)

_apps_api = None


class NotEligible(Exception):
    """The report is not sent to Dependency-Track; `level` is the log level of the reason."""

    def __init__(self, message: str, level: int = logging.INFO):
        super().__init__(message)
        self.level = level


def resolve_identity(body) -> dict:
    """
    Where the report goes: namespace, name, env, productType, environment, tags, aclTeam
    and the resolved "dojo" block. Raises NotEligible. No I/O.
    """
    cfg = IDENTITIES
    meta = body.get("metadata") or {}
    labels = meta.get("labels") or {}
    report = body.get("report") or {}

    for key, values in cfg["exclude"].items():
        if labels.get(key) in values:
            raise NotEligible(f"label {key}={labels[key]} is excluded")
    server = (report.get("registry") or {}).get("server")
    if cfg["registries"] and server not in cfg["registries"]:
        raise NotEligible(f"registry '{server}' is out of scope")
    k8s_ns = meta.get("namespace")
    mapped = cfg["namespaces"].get(k8s_ns) or base_entry(
        k8s_ns, cfg["default"], cfg["prefixes"]
    )
    if mapped is None:
        raise NotEligible(f"namespace '{k8s_ns}' is not mapped")

    repository = (report.get("artifact") or {}).get("repository")
    override = cfg["repositories"].get(f"{k8s_ns}/{repository}", {})
    namespace = override.get("namespace") or mapped["namespace"]
    name = override.get("name") or repository
    try:
        validate_identity(namespace, name)
    except ValueError as err:
        raise NotEligible(f"invalid identity: {err}", logging.ERROR) from None

    values = {"namespace": namespace, "name": name, "env": mapped["env"]}
    dojo = dict(cfg["defectDojo"])
    values["product"] = dojo["product"] = format_template(dojo["product"], **values)
    dojo["testTitle"] = format_template(dojo["testTitle"], **values)
    if not dojo["product"] or not dojo["testTitle"]:
        raise NotEligible("empty DefectDojo product or test title", logging.ERROR)
    return {
        "namespace": namespace,
        "name": name,
        "env": mapped["env"],
        "productType": mapped["productType"],
        "environment": mapped["environment"],
        "tags": [format_template(t, **values) for t in mapped["tags"]],
        "aclTeam": mapped.get("aclTeam"),
        "dojo": dojo,
    }


def state_key(identity: dict, report: dict) -> str:
    """
    Changes with the destination, the servers and the scanned content. The image digest
    stands for the content; without one the whole BOM does (and then every rescan resends).
    """
    digest = (report.get("artifact") or {}).get("digest")
    if not digest:
        bom = json.dumps(report.get("components"), sort_keys=True)
        digest = "bom:" + hashlib.sha256(bom.encode()).hexdigest()
    key = {
        "identity": identity,
        "dependencyTrack": DT_URL,
        "defectDojo": settings.DEFECT_DOJO_URL.rstrip("/"),
        "digest": digest,
        "scanner": (report.get("scanner") or {}).get("version"),
    }
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def read_state(body) -> dict:
    raw = ((body.get("metadata") or {}).get("annotations") or {}).get(STATE_ANNOTATION)
    try:
        state = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return state if isinstance(state, dict) else {}


def write_state(patch, state: dict) -> None:
    patch.metadata.annotations[STATE_ANNOTATION] = json.dumps(
        state, sort_keys=True, separators=(",", ":")
    )


def _request(method: str, url: str, headers: dict, what: str, accept=(), **kwargs):
    """
    One HTTP call. 2xx and the statuses in `accept` are returned; 5xx/429/408/network errors
    become TemporaryError, anything else PermanentError. Messages carry the status only:
    never a body, URL query or key.
    """
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=TIMEOUT,
            verify=True,
            allow_redirects=False,
            **kwargs,
        )
    except requests.RequestException as err:
        raise kopf.TemporaryError(
            f"{what}: request failed ({type(err).__name__})", delay=RETRY_DELAY
        ) from None
    status = response.status_code
    if 200 <= status < 300 or status in accept:
        return response
    if status >= 500 or status in (408, 429):
        raise kopf.TemporaryError(f"{what}: HTTP {status}", delay=RETRY_DELAY)
    raise kopf.PermanentError(f"{what}: HTTP {status}")


def _json(response, what: str):
    try:
        return response.json()
    except ValueError:
        raise kopf.PermanentError(f"{what}: response is not JSON") from None


def _dt(method: str, path: str, what: str, **kwargs):
    headers = {
        "X-Api-Key": settings.DEPENDENCY_TRACK_API_KEY,
        "Accept": "application/json",
    }
    url = f"{DT_URL}/api/v1/{path}"
    return _request(method, url, headers, what, **kwargs)


def _dd(method: str, path: str, what: str, **kwargs):
    headers = {
        "Authorization": "Token " + settings.DEFECT_DOJO_API_KEY,
        "Accept": "application/json",
    }
    url = f"{settings.DEFECT_DOJO_URL.rstrip('/')}/api/v2/{path}"
    return _request(method, url, headers, what, **kwargs)


def dedupe_depends_on(bom: dict) -> dict:
    """Copy of the BOM without repeated `dependsOn` refs. Trivy repeats them for some embedded SPDX documents (e.g. Bitnami's `.spdx-<app>.spdx`) and Dependency-Track rejects the BOM because the CycloneDX schema requires `uniqueItems`.
    """
    deps = bom.get("dependencies")
    if not isinstance(deps, list):
        return bom
    return {
        **bom,
        "dependencies": [
            (
                {**d, "dependsOn": list(dict.fromkeys(d["dependsOn"]))}
                if isinstance(d, dict) and isinstance(d.get("dependsOn"), list)
                else d
            )
            for d in deps
        ],
    }


def upload_bom(identity: dict, bom: dict) -> tuple[str, str | None]:
    """POST the BOM, minus repeated dependsOn refs; return (projectUuid, token)."""
    what = "Dependency-Track BOM upload"
    response = _dt(
        "POST",
        "bom",
        what,
        data={
            "autoCreate": "true",
            "projectName": f"{identity['namespace']}-{identity['env']}",
            "projectVersion": identity["name"],
            "projectTags": ",".join(identity["tags"]),
        },
        files={
            "bom": (
                "sbom.cdx.json",
                json.dumps(dedupe_depends_on(bom)).encode(),
                "application/json",
            )
        },
        accept=(409,),
    )
    if response.status_code == 409:  # project created concurrently by another uploader
        raise kopf.TemporaryError(f"{what}: HTTP 409", delay=RETRY_DELAY)
    data = _json(response, what)
    try:
        project = str(uuid.UUID(str(data["projectUuid"])))
    except (KeyError, TypeError, ValueError):
        raise kopf.PermanentError(
            f"{what}: response has no valid projectUuid"
        ) from None
    token = data.get("token")
    return project, token if isinstance(token, str) else None


def _first_exact(response, what: str, field: str, value: str) -> dict | None:
    """First result whose `field` equals `value`; the lookups filter by equality already."""
    data = _json(response, what)
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise kopf.PermanentError(f"{what}: unexpected response")
    return next(
        (r for r in results if isinstance(r, dict) and r.get(field) == value), None
    )


def ensure_product(identity: dict, logger) -> None:
    """Create the Product when it does not exist yet; an existing one is never changed."""
    name = identity["dojo"]["product"]
    what = "DefectDojo product lookup"

    def lookup():
        response = _dd("GET", "products/", what, params={"name_exact": name})
        return _first_exact(response, what, "name", name)

    if lookup():
        return
    type_name = identity["productType"]
    what_type = "DefectDojo product type lookup"
    response = _dd("GET", "product_types/", what_type, params={"name": type_name})
    product_type = _first_exact(response, what_type, "name", type_name)
    if product_type is None or "id" not in product_type:
        raise kopf.PermanentError(
            f"DefectDojo product type '{type_name}' does not exist"
        )

    description = (
        DEFAULT_PRODUCT_DESCRIPTION
        if settings.DEFECT_DOJO_EVAL_PRODUCT_DESCRIPTION
        else settings.DEFECT_DOJO_PRODUCT_DESCRIPTION
    )
    payload = {
        "name": name,
        "description": description,
        "enable_product_tag_inheritance": settings.DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE,
        "prod_type": product_type["id"],
    }
    if settings.DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT:
        payload["tags"] = [identity["env"], identity["namespace"]]
    response = _dd(
        "POST",
        "products/",
        "DefectDojo product creation",
        accept=(400, 409),
        json=payload,
    )
    if response.status_code < 300:
        logger.info(f"Created DefectDojo product '{name}'")
    elif not lookup():  # created concurrently?
        message = f"DefectDojo product creation: HTTP {response.status_code}"
        if response.status_code == 400:
            raise kopf.PermanentError(message)
        raise kopf.TemporaryError(message, delay=RETRY_DELAY)


def reimport_empty_fpf(identity: dict) -> str:
    """Create the engagement and test now (Dependency-Track only sends findings later); return the engagement id."""
    what = "DefectDojo reimport"
    dojo = identity["dojo"]
    response = _dd(
        "POST",
        "reimport-scan/",
        what,
        data={
            "scan_type": DD_SCAN_TYPE,
            "product_name": dojo["product"],
            "engagement_name": dojo["engagement"],
            "test_title": dojo["testTitle"],
            "environment": identity["environment"],
            "auto_create_context": "true",
            "deduplication_on_engagement": "true",
            "close_old_findings": "false",
        },
        files={"file": ("empty.json", EMPTY_FPF, "application/json")},
    )
    engagement_id = _json(response, what).get("engagement_id")
    if (
        isinstance(engagement_id, bool)
        or not isinstance(engagement_id, (int, str))
        or not str(engagement_id).isdigit()
    ):
        raise kopf.PermanentError(f"{what}: response has no valid engagement_id")
    return str(engagement_id)


def set_properties(project: str, identity: dict, engagement_id: str) -> None:
    dojo = identity["dojo"]
    properties = [
        ("defectdojo.engagementId", "STRING", engagement_id),
        ("defectdojo.reimport", "BOOLEAN", "true"),
        ("defectdojo.doNotReactivate", "BOOLEAN", "false"),
        ("defectdojo.testTitle", "STRING", dojo["testTitle"]),
    ]
    if dojo["groupBy"]:
        properties.append(("defectdojo.groupBy", "STRING", dojo["groupBy"]))
    for prop_name, prop_type, value in properties:
        body = {
            "groupName": "integrations",
            "propertyName": prop_name,
            "propertyValue": value,
        }
        what = f"Dependency-Track property {prop_name}"
        path = f"project/{project}/property"
        # PUT creates; 409 means it exists, then POST updates the value (the type is fixed at creation).
        response = _dt(
            "PUT", path, what, accept=(409,), json={**body, "propertyType": prop_type}
        )
        if response.status_code == 409:
            _dt("POST", path, what, json=body)


def find_team_uuid(name: str) -> str:
    """UUID of the team named exactly `name`; searchText only narrows the list."""
    what = "Dependency-Track team lookup"
    found: set[str] = set()
    seen: set[str] = set()
    for page in range(1, MAX_PAGES + 1):
        response = _dt(
            "GET",
            "team/visible",
            what,
            params={"searchText": name, "pageNumber": page, "pageSize": PAGE_SIZE},
        )
        teams = _json(response, what)
        if not isinstance(teams, list):
            raise kopf.PermanentError(f"{what}: unexpected response")
        teams = [t for t in teams if isinstance(t, dict) and t.get("uuid")]
        found |= {t["uuid"] for t in teams if t.get("name") == name}
        new = {t["uuid"] for t in teams} - seen
        seen |= new
        # A server that ignores pagination repeats the same page: stop when nothing is new.
        if len(teams) < PAGE_SIZE or not new:
            break
    if not found:
        raise kopf.PermanentError(f"Dependency-Track team '{name}' does not exist")
    if len(found) > 1:
        raise kopf.PermanentError(f"Dependency-Track team '{name}' is ambiguous")
    return next(iter(found))


def map_acl(project: str, team_uuid: str) -> None:
    _dt(
        "PUT",
        "acl/mapping",
        "Dependency-Track ACL mapping",
        accept=(409,),
        json={"project": project, "team": team_uuid},
    )


def link_project(project: str, identity: dict, logger) -> None:
    """Every step is idempotent, so the whole link can be retried."""
    ensure_product(identity, logger)
    engagement_id = reimport_empty_fpf(identity)
    set_properties(project, identity, engagement_id)
    if identity["aclTeam"]:
        map_acl(project, find_team_uuid(identity["aclTeam"]))


def replicaset_replicas(namespace: str, name: str) -> int | None:
    """spec.replicas of a ReplicaSet; None when it no longer exists."""
    global _apps_api
    from kubernetes import client, config
    from kubernetes.client.exceptions import ApiException

    try:
        if _apps_api is None:
            config.load_config()  # in-cluster, or the local kubeconfig
            _apps_api = client.AppsV1Api()
        rs = _apps_api.read_namespaced_replica_set(
            name, namespace, _request_timeout=(10, 30)
        )
    except ApiException as err:
        if err.status == 404:
            return None
        if err.status in (401, 403):
            raise kopf.PermanentError(
                f"ReplicaSet read: HTTP {err.status} (check RBAC for replicasets)"
            ) from None
        raise kopf.TemporaryError(
            f"ReplicaSet read: HTTP {err.status}", delay=RETRY_DELAY
        ) from None
    except Exception as err:
        raise kopf.TemporaryError(
            f"ReplicaSet read failed ({type(err).__name__})", delay=RETRY_DELAY
        ) from None
    return 1 if rs.spec.replicas is None else rs.spec.replicas


def is_obsolete(body, logger) -> bool:
    """An old ReplicaSet scaled to zero is a past rollout: its SBOM must not overwrite the current one."""
    annotations = body["metadata"].get("annotations") or {}
    # Trivy marks reports of inactive revisions this way and rewrites all their annotations
    # whenever the report changes, so uploading them would loop.
    if annotations.get("trivy-operator.aquasecurity.github.io/report-ttl") == "0s":
        logger.info("Trivy marked the report as historical, skipping")
        return True
    labels = body["metadata"].get("labels") or {}
    if labels.get("trivy-operator.resource.kind") != "ReplicaSet":
        return False
    replicas = replicaset_replicas(
        body["metadata"]["namespace"], labels.get("trivy-operator.resource.name")
    )
    if replicas:
        return False
    logger.info("ReplicaSet is gone or scaled to zero, skipping")
    return True


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def destination_lock(identity: dict) -> threading.Lock:
    """One lock per DefectDojo Product: reports sharing it must not create the Product, engagement or test twice."""
    with _locks_guard:
        return _locks.setdefault(identity["dojo"]["product"], threading.Lock())


def sbom_to_dependency_track(body, patch, logger, **_):
    """Upload the SbomReport BOM to Dependency-Track and link it to DefectDojo, at least once."""
    try:
        identity = resolve_identity(body)
    except NotEligible as err:
        logger.log(
            err.level,
            f"SbomReport {body['metadata']['name']} not sent to Dependency-Track: {err}",
        )
        c.labels("skipped").inc()
        return
    report = body.get("report") or {}
    bom = report.get("components")
    if not isinstance(bom, dict):
        logger.error("SbomReport has no report.components, nothing to send")
        c.labels("skipped").inc()
        return

    key = state_key(identity, report)
    state = read_state(body)
    same = state.get("key") == key
    if same and state.get("stage") == "linked":
        logger.info("Dependency-Track already up to date for this SBOM")
        c.labels("skipped").inc()
        return

    try:
        if is_obsolete(body, logger):
            c.labels("skipped").inc()
            return
        project = (
            state.get("project") if same and state.get("stage") == "uploaded" else None
        )
        try:
            project = str(uuid.UUID(project)) if project else None
        except (TypeError, ValueError):
            project = None
        with destination_lock(identity):
            if project:
                logger.info("Resuming DefectDojo link of the already uploaded SBOM")
            else:
                project, token = upload_bom(identity, bom)
                # Kopf applies this patch even if the handler raises later (checked on 1.44.5).
                write_state(
                    patch, {"key": key, "stage": "uploaded", "project": project}
                )
                logger.info(
                    f"SBOM accepted by Dependency-Track, project {project}, token {token}"
                )
            link_project(project, identity, logger)
        write_state(patch, {"key": key, "stage": "linked", "project": project})
    except (kopf.TemporaryError, kopf.PermanentError):
        c.labels("failed").inc()
        raise
    c.labels("success").inc()
    logger.info(
        f"Linked {identity['namespace']}-{identity['env']}:{identity['name']} to DefectDojo"
    )


def register(labels: dict) -> None:
    """Register the handler for create, update and resume; Kopf runs it once per cause."""
    for decorator in (kopf.on.create, kopf.on.update, kopf.on.resume):
        decorator(RESOURCE, labels=labels, retries=RETRIES)(sbom_to_dependency_track)
