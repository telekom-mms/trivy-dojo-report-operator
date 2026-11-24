# Dependency-Track integration

Optional, disabled by default. When enabled, the operator uploads the CycloneDX
SBOM of each Trivy Operator `SbomReport` to
[Dependency-Track](https://dependencytrack.org/) and links the resulting project
to [DefectDojo](https://github.com/DefectDojo/django-DefectDojo). Behavior below
was checked against Dependency-Track 5.2.1 and DefectDojo 3.4.201.

## Scope

- Handled: `sbomreports.aquasecurity.github.io` (namespaced `SbomReport`).
- Not handled: `ClusterSbomReport` and KBOM.
- Disabled by default (`DEPENDENCY_TRACK_REPORTS_ENABLED` is not `true`): the module is not
  imported, nothing is validated, and Kopf does not even watch `sbomreports`.
- `sbomreports` are never part of `REPORTS` and never reach the Trivy Operator scan
  parser or DefectDojo as vulnerabilities. The `LABEL`/`LABEL_VALUE` filter applies
  to them as to the other reports.
- The operator does not poll the analysis: Dependency-Track processes the BOM
  asynchronously (the returned token is only logged) and exports findings to
  DefectDojo on its own schedule.

## Configuration

| Environment variable | Helm value | Notes |
|---|---|---|
| `DEPENDENCY_TRACK_REPORTS_ENABLED` | `dependencyTrack.reportsEnabled` | default `false` |
| `DEPENDENCY_TRACK_URL` | `dependencyTrack.url` | `http` or `https` URL without credentials, query or fragment; `http` is accepted with a startup warning (the API key travels unencrypted) |
| `DEPENDENCY_TRACK_API_KEY` | `dependencyTrack.apiCredentials.*` | from a Secret |
| `DEPENDENCY_TRACK_PROJECT_NAME`, `DEPENDENCY_TRACK_PROJECT_VERSION` | `dependencyTrack.projectName`, `projectVersion` | required when enabled, see Values |
| other `DEPENDENCY_TRACK_*` | `dependencyTrack.*` | see Values |
| `DEFECT_DOJO_URL`, `DEFECT_DOJO_API_KEY` | `defectDojoApiCredentials.*` | existing settings, reused |
| `DEFECT_DOJO_REPORTS_ENABLED` | `operator.trivyDojoReportOperator.env.defectDojoReportsEnabled` | default `true`; `false` disables the `REPORTS` flow (`REPORTS` is ignored) |

API key Secret: with `createSecret: true` the chart creates it from `apiKey` (never
commit a real key; use `--set` or a private values file). With `createSecret: false`,
set `secretName` to an existing Secret (for example from an ExternalSecret) and
`apiKeySecretKey` to the key inside it.

When enabled, the chart also adds to the ClusterRole: `sbomreports`
(`get`, `list`, `watch`, `patch`) and `apps/replicasets` (`get`). Trivy Operator must
have SBOM generation enabled so `SbomReport` objects exist. The static manifest in
`deploy/` only carries `DEPENDENCY_TRACK_REPORTS_ENABLED=false`; use Helm to enable.

Network: requests use the standard `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY`
environment variables. TLS is verified and redirects are not followed.

### Values

Every value follows the DefectDojo pattern (`DEFECT_DOJO_X` and `DEFECT_DOJO_EVAL_X`): it is used as is, or, when its `EVAL` flag is `true`, evaluated as a Python expression for each `SbomReport` with `body` (the report) and `meta` (`body["metadata"]`). Results are converted with `str()` and stripped.

| Environment variable | Helm value | Default (chart) | Notes |
|---|---|---|---|
| `DEPENDENCY_TRACK_PROJECT_NAME` / `DEPENDENCY_TRACK_EVAL_PROJECT_NAME` | `projectName` / `evalProjectName` | `project` / `false` | required env when enabled; required result |
| `DEPENDENCY_TRACK_PROJECT_VERSION` / `DEPENDENCY_TRACK_EVAL_PROJECT_VERSION` | `projectVersion` / `evalProjectVersion` | `1.0` / `false` | required env when enabled; required result |
| `DEPENDENCY_TRACK_PROJECT_TAGS` / `DEPENDENCY_TRACK_EVAL_PROJECT_TAGS` | `projectTags` / `evalProjectTags` | empty / `false` | comma-separated string, or with eval a list of strings; a tag containing a comma is an error |
| `DEPENDENCY_TRACK_ACL_TEAM` / `DEPENDENCY_TRACK_EVAL_ACL_TEAM` | `aclTeam` / `evalAclTeam` | empty / `false` | empty: no ACL mapping |
| `DEPENDENCY_TRACK_GROUP_BY` / `DEPENDENCY_TRACK_EVAL_GROUP_BY` | `groupBy` / `evalGroupBy` | empty / `false` | empty: the property `defectdojo.groupBy` is not set |
| `DEPENDENCY_TRACK_DEFECT_DOJO_PRODUCT_NAME` / `..._DEFECT_DOJO_EVAL_PRODUCT_NAME` | `defectDojo.productName` / `evalProductName` | `product` / `false` | required result |
| `DEPENDENCY_TRACK_DEFECT_DOJO_PRODUCT_TYPE_NAME` / `..._EVAL_PRODUCT_TYPE_NAME` | `defectDojo.productTypeName` / `evalProductTypeName` | `Research and Development` / `false` | required result; the Product Type must exist |
| `DEPENDENCY_TRACK_DEFECT_DOJO_ENGAGEMENT_NAME` / `..._EVAL_ENGAGEMENT_NAME` | `defectDojo.engagementName` / `evalEngagementName` | `engagement` / `false` | required result |
| `DEPENDENCY_TRACK_DEFECT_DOJO_ENV_NAME` / `..._EVAL_ENV_NAME` | `defectDojo.envName` / `evalEnvName` | `Development` / `false` | required result |
| `DEPENDENCY_TRACK_DEFECT_DOJO_TEST_TITLE` / `..._EVAL_TEST_TITLE` | `defectDojo.testTitle` / `evalTestTitle` | `Kubernetes` / `false` | required result |

(`..._` stands for `DEPENDENCY_TRACK_DEFECT_DOJO`.) Reused from the DefectDojo flow, no new keys: product description (`DEFECT_DOJO_PRODUCT_DESCRIPTION`, `DEFECT_DOJO_EVAL_PRODUCT_DESCRIPTION`), product tags (`DEFECT_DOJO_TAGS`, `DEFECT_DOJO_EVAL_TAGS`), `DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT`, `DEFECT_DOJO_AUTO_CREATE_CONTEXT`, `DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT` and `DEFECT_DOJO_DO_NOT_REACTIVATE`.

Expressions of one report run in the order of the table above (then the reused product description and tags) and share one namespace, so the first one can bind a name with `:=` for the others. This keeps a mapping in one place:

```yaml
dependencyTrack:
  evalProjectName: "true"
  projectName: '(I := {"shop": {"team": "tech"}}.get(meta["namespace"])) and meta["namespace"]'
  evalAclTeam: "true"
  aclTeam: 'I["team"]'
```

Skip rule: the required values (project name, project version, product name, product type, product description, engagement, environment, test title) must not be empty. A `None` or empty result skips the report with an INFO log; this is how reports are filtered. An eval exception skips the report with an ERROR log `<key> could not be evaluated (<ExceptionType>)`; the expression is never echoed.

Security: `eval` runs arbitrary Python. Use it only with trusted, administrator-controlled configuration, never with values that users or workloads can influence.

Examples (Helm values; each needs its `eval*` flag `true`):

```yaml
dependencyTrack:
  # only namespaces starting with "app-", prefix stripped; others are skipped
  projectName: 'meta["namespace"][4:] if meta["namespace"].startswith("app-") else None'
  # skip images from one registry
  projectVersion: 'None if body["report"]["registry"]["server"] == "docker.io" else body["report"]["artifact"]["repository"]'
  # skip reports labelled team=sandbox (the label must be on the report, see Trivy Operator reportResourceLabels)
  defectDojo:
    productName: 'None if meta.get("labels", {}).get("team") == "sandbox" else meta["namespace"]'
```

### Which report goes where

Evaluated in this order; the first failing check skips the report and logs the reason.

1. The `LABEL`/`LABEL_VALUE` filter applies as for the other reports (Kopf never calls the handler otherwise).
2. The values are resolved; an empty required result or an eval error skips the report.
3. A report owned by a ReplicaSet is ignored when the ReplicaSet no longer exists or has
   `spec.replicas` 0 (an old rollout must not overwrite the current SBOM). Reports that
   Trivy Operator marked as historical (annotation
   `trivy-operator.aquasecurity.github.io/report-ttl: 0s`, set on inactive revisions) are
   ignored too: Trivy rewrites all their annotations on every change, so the state would
   never stick.

## What is sent

Order: BOM upload, DefectDojo Product (only if missing), DefectDojo reimport (empty
FPF, to create engagement and test), integration properties, optional ACL mapping.
Every step is idempotent.

| Target | Field | Value |
|---|---|---|
| Dependency-Track `POST /api/v1/bom` | `autoCreate` | `true` |
| | `projectName` | resolved `projectName` |
| | `projectVersion` | resolved `projectVersion` |
| | `projectTags` | resolved `projectTags`, comma separated |
| | `bom` | the BOM as stored in the report, minus repeated `dependsOn` refs |
| DefectDojo Product (create only) | name | resolved `defectDojo.productName` |
| | `prod_type` | id of the Product Type named `defectDojo.productTypeName` (exact name; must exist) |
| | `description` | `DEFECT_DOJO_PRODUCT_DESCRIPTION` (`DEFECT_DOJO_EVAL_PRODUCT_DESCRIPTION` applies) |
| | `enable_product_tag_inheritance` | `DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE` |
| | `tags` | `DEFECT_DOJO_TAGS` (`DEFECT_DOJO_EVAL_TAGS` applies), only when `DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT=true`; otherwise `[]` |
| DefectDojo `POST /api/v2/reimport-scan/` | `scan_type` | `Dependency Track Finding Packaging Format (FPF) Export`, with an empty `{"findings": []}` file |
| | `product_name` / `engagement_name` / `test_title` | resolved `defectDojo.productName` / `engagementName` / `testTitle` |
| | `environment` | resolved `defectDojo.envName` |
| | `auto_create_context` | `DEFECT_DOJO_AUTO_CREATE_CONTEXT` |
| | `deduplication_on_engagement` | `DEFECT_DOJO_DEDUPLICATION_ON_ENGAGEMENT` |
| | `close_old_findings` | always `false`: the FPF file is empty, so `true` would close every finding Dependency-Track exported |
| Dependency-Track project properties (group `integrations`) | `defectdojo.engagementId` | engagement id returned by the reimport (STRING) |
| | `defectdojo.reimport` | `true` (BOOLEAN, fixed) |
| | `defectdojo.doNotReactivate` | `DEFECT_DOJO_DO_NOT_REACTIVATE` (BOOLEAN; chart default `true`) |
| | `defectdojo.testTitle` | the resolved test title (STRING) |
| | `defectdojo.groupBy` | resolved `groupBy`, only when not empty (STRING) |
| Dependency-Track `PUT /api/v1/acl/mapping` | `project`, `team` | only with `aclTeam`: UUID of the team named exactly as the resolved `aclTeam` (paginated lookup; missing or ambiguous is an error) |

Notes:

- An existing Product is never changed (type, description, tags and inheritance stay).
  A missing Product Type is a permanent error: the operator never creates Product Types.
- Properties are written with `PUT`; only an HTTP 409 (already exists) falls back to
  `POST`, which updates the value (the type is fixed at creation).

## Change detection and delivery

- Trivy Operator updates the whole `SbomReport` on every rescan and the update drops
  its `status` (annotations are kept), so Kopf may see it as create, update or resume.
  One handler is registered for all three; Kopf runs it once per event.
- State is kept in the annotation `dependency-track.trivy-dojo-report-operator/state`
  (JSON): `key`, `stage` (`uploaded` or `linked`) and `project` (UUID). The token is
  only logged.
- `key` is a SHA-256 of all resolved values (project, tags, ACL team, group-by and the DefectDojo values), the
  Dependency-Track and DefectDojo URLs, `report.artifact.digest` and
  `report.scanner.version`. Without a digest the hash of the whole BOM is used instead,
  and then every rescan produces a new BOM and resends it.
- The Kopf diff-base ignores `report.vulnerabilities`, `report.components` (the SBOM is
  too big for it) and the state annotation.
- `stage=linked` with the same key: nothing is sent, no HTTP call at all (this is the
  path taken on operator restart). `stage=uploaded` with the same key: the upload is
  skipped and only the DefectDojo/ACL link is retried. The state is patched right after
  the upload, so progress survives a later failure.
- Errors: network errors, HTTP 5xx, 408 and 429 are temporary (retried up to 10 times,
  60 s apart), and so is a 409 on the BOM upload (project created concurrently by
  another uploader, such as a CI pipeline). Other unexpected statuses (including 401 and 403), a missing Product Type
  or team, ambiguous names and invalid responses are permanent: no retry until the next
  rescan rewrites the report. Messages never contain bodies, query strings or keys.
- Concurrency has no dedicated limit: deliveries run on the Kopf thread pool (Python
  default, up to `min(32, cpu + 4)` threads). On the first activation many reports can
  be uploaded at the same time; consider enabling one namespace at a time. Reports
  sharing a DefectDojo Product are delivered one at a time within the operator process,
  so they do not create the Product, engagement or test twice; while waiting they hold
  a pool thread. Two uploads creating the same Dependency-Track project at once get a
  409, which is retried.
- Metric `dependency_track_reports_total{status="success|failed|skipped"}`.

Known limitations:

- The BOM is sent as stored in the `SbomReport`. The Trivy Operator CRD prunes some BOM
  fields (for example `$schema` and nested components), so the upload can differ from
  the BOM Trivy generated. The only change the operator makes is dropping repeated refs
  in `dependencies[].dependsOn`: Trivy repeats them for some embedded SPDX documents
  (e.g. Bitnami's `/opt/bitnami/<app>/.spdx-<app>.spdx`), and Dependency-Track rejects
  such a BOM with HTTP 400 because CycloneDX requires them to be unique.
- If a BOM changes in an `update` that preserves `status` (for example a manual edit),
  the change is not detected until the next operator restart. Real Trivy rescans drop
  the `status`, so the normal flow is unaffected.

## Required permissions

### Dependency-Track (verified on 5.2.1)

| Call | When | Permission |
|---|---|---|
| `POST /api/v1/bom` | always | `BOM_UPLOAD`; to auto-create the project also `PROJECT_CREATION_UPLOAD` (a missing creation permission returns 401). With portfolio ACL enabled, an existing project needs the principal's team in its ACL, else 403 |
| `PUT /api/v1/project/{uuid}/property` | always | `PORTFOLIO_MANAGEMENT_CREATE` |
| `POST /api/v1/project/{uuid}/property` | properties that already exist | `PORTFOLIO_MANAGEMENT_UPDATE` |
| `GET /api/v1/team/visible` | `aclTeam` set | none, but without `ACCESS_MANAGEMENT_READ` it only lists the principal's own teams, so the target team is not found |
| `PUT /api/v1/acl/mapping` | `aclTeam` set | `ACCESS_MANAGEMENT_CREATE` |

`PORTFOLIO_MANAGEMENT_UPDATE` also lets the upload replace the tags of an existing
project; without it Dependency-Track only logs a warning.

Minimal provisioning:

1. Create a dedicated service account and one dedicated team; make the service
   account a member of that team only. On auto-creation Dependency-Track gives the new
   project an ACL for the principal's first team (alphabetical), so a single team keeps
   this predictable. Verify team membership of service accounts in a test instance.
2. Give the team `BOM_UPLOAD`, `PROJECT_CREATION_UPLOAD`, `PORTFOLIO_MANAGEMENT_CREATE`
   and `PORTFOLIO_MANAGEMENT_UPDATE`. Add `ACCESS_MANAGEMENT_READ` and
   `ACCESS_MANAGEMENT_CREATE` only if you use `aclTeam`.
3. Do not grant `PORTFOLIO_ACCESS_CONTROL_BYPASS`.
4. With ACL enabled, map that team (`PUT /api/v1/acl/mapping` or the UI) to every
   existing project the operator must update; otherwise uploads return 403.
5. If you use `aclTeam`, create those teams beforehand; the operator never creates teams.

Risk of `aclTeam`: `ACCESS_MANAGEMENT_CREATE` also allows creating teams, service
accounts and API keys of any team, which is effectively administrator access, and the
ACL mapping does not require access to the project. Without `aclTeam` the operator never
needs it, so prefer mapping teams outside the operator when you can.

Native Dependency-Track to DefectDojo prerequisites (configured in Dependency-Track,
not by the operator): the DefectDojo integration enabled (`integrations.defectdojo.enabled`),
`defectdojo.url`, `defectdojo.apiKey` (in 5.2.1 the name of a Dependency-Track secret),
reimport enabled (`defectdojo.reimport.enabled`), and the scheduled upload task running.
Findings reach DefectDojo only when that task runs, not at upload time.

### DefectDojo (verified on 3.4.201)

- The Product Types named by `defectDojo.productTypeName` must already exist.
- Simplest: a staff user. Otherwise a non-staff user listed in `authorized_users` of
  each used Product Type can list Product Types, create Products and reimport with
  `auto_create_context`. Deleting is not needed and not available to it.

## Sharing a project with other uploaders

Another uploader (for example a CI pipeline) that sends BOMs to the same project name
and version as the resolved `projectName` and `projectVersion` writes to the same Dependency-Track project, and with
the same DefectDojo settings to the same Product, engagement and test. Dependency-Track
5.2.1 reconciles components on every BOM: the project ends up with the components of the
last BOM processed, not the union, and processing is asynchronous, so the order is not
guaranteed.

Effect: if CI scans a feature or release-candidate image while the cluster runs another,
the project flips between the two component sets, and the findings follow it.
Recommendation: let only one source feed a given project. Either upload from CI only the
artifact that is actually deployed to that environment, or give the operator a separate
project name or version through `projectName` or `projectVersion`.

## Activation checklist

1. Release the operator image and chart that include this feature.
2. Create the API key Secret (or ExternalSecret) in the operator namespace.
3. Provision Dependency-Track and DefectDojo as above, including Product Types and, if
   used, teams.
4. Prepare values: URL, Secret, the `projectName` and other values (filter to one namespace first, e.g. with a `None` result for the rest). The defaults are literals, like the `defectDojo*` ones: without expressions every SBOM goes to the same project (`project` / `1.0`) and the same DefectDojo Product, engagement and test, and each upload replaces the components of the previous one. Set at least `projectName`/`projectVersion` and the DefectDojo names per report, for example `meta["namespace"]` and `body["report"]["artifact"]["repository"]` with their `eval*` flags on.
5. Enable on one cluster at a time.
6. Watch `dependency_track_reports_total` and the operator logs; confirm the project,
   properties and ACL in Dependency-Track and the Product, engagement and test in
   DefectDojo.
7. Extend the mapping gradually.
