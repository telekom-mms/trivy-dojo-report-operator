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
| `DEPENDENCY_TRACK_IDENTITIES` | `dependencyTrack.identities` | JSON, see below; validated at startup |
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

### `DEPENDENCY_TRACK_IDENTITIES`

```json
{
  "registries": ["registry.example.com"],
  "default": {"env": "staging", "productType": "tech-staging", "environment": "Staging", "aclTeam": "tech-staging"},
  "prefixes": {"dev-": {"env": "dev", "productType": "tech-dev", "environment": "Development", "aclTeam": "tech-dev"}},
  "namespaces": {
    "shop-staging": {
      "namespace": "shop", "env": "staging",
      "productType": "tech-staging", "environment": "Staging",
      "tags": ["{env}", "{namespace}"],
      "aclTeam": "tech-staging"
    }
  },
  "repositories": {"shop-staging/shop-api-v2": {"name": "shop-api", "namespace": "shop"}},
  "exclude": {"example.com/app": ["shop-canary"]},
  "defectDojo": {
    "engagement": "dependency-track",
    "product": "{namespace}-{env}",
    "testTitle": "{namespace}/{name}",
    "groupBy": "component_name+component_version"
  }
}
```

| Key | Required | Meaning |
|---|---|---|
| `default` | no | Entry (without `namespace`) for every Kubernetes namespace not matched by `namespaces` or `prefixes`; the project `namespace` is the Kubernetes namespace. Absent: unmatched namespaces are skipped |
| `prefixes` | no | Prefix to entry (without `namespace`): a Kubernetes namespace that starts with the prefix uses the entry and, as `namespace`, the rest of its name (`dev-shop` with `dev-` becomes `shop`). The longest prefix wins; it takes precedence over `default` |
| `namespaces` | no | Kubernetes namespace (of the `SbomReport`) to identity, merged onto the entry `prefixes` or `default` gives it, so an override only needs the keys that differ; without such an entry it must be complete. At least one of `default`, `prefixes` and `namespaces` is required. Per entry: `namespace` (project name prefix, `[A-Za-z0-9._-]`), `env` (project name suffix, any non-empty string), `productType` (DefectDojo Product Type name), `environment` (DefectDojo environment name), optional `tags` (templates, default `["{env}", "{namespace}"]`), optional `aclTeam` (Dependency-Track team name; absent skips the ACL) |
| `registries` | no | Exact values of `report.registry.server` that are eligible. Absent or `[]` means all registries |
| `repositories` | no | `"<k8s namespace>/<repository>"` of a namespace that `namespaces`, `prefixes` or `default` maps; overrides `name` and/or `namespace` |
| `exclude` | no | Label key to a non-empty list of values; a report whose label has one of the values is never sent. The label is on the report only if Trivy Operator copies it from the workload (Trivy Operator Helm value `trivyOperator.reportResourceLabels`, a comma-separated list of label keys) |
| `defectDojo` | no | `engagement` (default `dependency-track`), `product` (default `{namespace}-{env}`), `testTitle` (default `{namespace}/{name}`), `groupBy` (default unset: the property is not written) |

Templates use `str.format` with `{namespace}`, `{name}` and `{env}`; `testTitle` and
`tags` also accept `{product}`. Startup validation (the operator exits on error; the
chart only renders the JSON) checks the structure, the name patterns, that every
template formats with sample values and that tags are non-empty and contain no comma.
An empty Product or test title is only rejected at runtime (the report is skipped as an
error). Errors never echo the input.

### Which report goes where

Evaluated in this order; the first failing check skips the report and logs the reason.

1. `exclude`: skipped when a label value matches.
2. `registries`: when not empty, `report.registry.server` must be equal to one entry.
3. `metadata.namespace` is looked up in `namespaces`, then in `prefixes` (longest match),
   then `default`. Without a match the report is skipped.
4. `name` is `report.artifact.repository`, `namespace` is the entry's `namespace`;
   `repositories["<k8s namespace>/<repository>"]` overrides either. The result is
   validated (`name` also allows `/`); an invalid or empty result is an error.
5. A report owned by a ReplicaSet is ignored when the ReplicaSet no longer exists or has
   `spec.replicas` 0 (an old rollout must not overwrite the current SBOM). Reports that
   Trivy Operator marked as historical (annotation
   `trivy-operator.aquasecurity.github.io/report-ttl: 0s`, set on inactive revisions) are
   ignored too: Trivy rewrites all their annotations on every change, so the state would
   never stick.

### Example for a typical scheme

One cluster per environment of one team, one Product Type and one Dependency-Track team
per team and environment, the project named after the namespace and environment of the
workload; `dev-*` namespaces belong to the `dev` environment and `legacy` is an exception:

```yaml
dependencyTrack:
  reportsEnabled: true
  url: https://dependency-track.example.com
  apiCredentials:
    createSecret: false
    secretName: dependency-track-api
  identities:
    registries: [registry.example.com]
    default: {env: staging, productType: tech-staging, environment: Staging, aclTeam: tech-staging}
    prefixes:
      dev-: {env: dev, productType: tech-dev, environment: Development, aclTeam: tech-dev}
    namespaces:
      legacy: {namespace: shop}
```

## What is sent

Order: BOM upload, DefectDojo Product (only if missing), DefectDojo reimport (empty
FPF, to create engagement and test), integration properties, optional ACL mapping.
Every step is idempotent. `<name>`, `<namespace>` and `<env>` are the resolved values.

| Target | Field | Value |
|---|---|---|
| Dependency-Track `POST /api/v1/bom` | `autoCreate` | `true` |
| | `projectName` | `<namespace>-<env>` |
| | `projectVersion` | `<name>` (the repository, not the image tag) |
| | `projectTags` | the `tags` templates, comma separated |
| | `bom` | the BOM as stored in the report, minus repeated `dependsOn` refs |
| DefectDojo Product (create only) | name | `defectDojo.product` template |
| | `prod_type` | id of the Product Type named `productType` (exact name; must exist) |
| | `description` | `DEFECT_DOJO_PRODUCT_DESCRIPTION` (default `Created by trivy-dojo-report-operator`; when `DEFECT_DOJO_EVAL_PRODUCT_DESCRIPTION` is `true` the default text is used) |
| | `enable_product_tag_inheritance` | `DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE` |
| | `tags` | fixed `[<env>, <namespace>]`, only when `DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT=true` (the `tags` templates only feed the Dependency-Track project tags) |
| DefectDojo `POST /api/v2/reimport-scan/` | `scan_type` | `Dependency Track Finding Packaging Format (FPF) Export`, with an empty `{"findings": []}` file |
| | `product_name` / `engagement_name` / `test_title` | `defectDojo.product` / `engagement` / `testTitle` templates |
| | `environment` | `environment` of the namespace entry |
| | flags | `auto_create_context=true`, `deduplication_on_engagement=true`, `close_old_findings=false` |
| Dependency-Track project properties (group `integrations`) | `defectdojo.engagementId` | engagement id returned by the reimport (STRING) |
| | `defectdojo.reimport` | `true` (BOOLEAN) |
| | `defectdojo.doNotReactivate` | `false` (BOOLEAN) |
| | `defectdojo.testTitle` | the resolved test title (STRING) |
| | `defectdojo.groupBy` | `defectDojo.groupBy`, only when set (STRING) |
| Dependency-Track `PUT /api/v1/acl/mapping` | `project`, `team` | only with `aclTeam`: UUID of the team named exactly `aclTeam` (paginated lookup; missing or ambiguous is an error) |

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
- `key` is a SHA-256 of the resolved identity (including the `defectDojo` block), the
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

- The Product Types named in `productType` must already exist.
- Simplest: a staff user. Otherwise a non-staff user listed in `authorized_users` of
  each used Product Type can list Product Types, create Products and reimport with
  `auto_create_context`. Deleting is not needed and not available to it.

## Sharing a project with other uploaders

Another uploader (for example a CI pipeline) that sends BOMs to the same project name
(`<namespace>-<env>`) and version (`<name>`) writes to the same Dependency-Track project, and with
the same DefectDojo settings to the same Product, engagement and test. Dependency-Track
5.2.1 reconciles components on every BOM: the project ends up with the components of the
last BOM processed, not the union, and processing is asynchronous, so the order is not
guaranteed.

Effect: if CI scans a feature or release-candidate image while the cluster runs another,
the project flips between the two component sets, and the findings follow it.
Recommendation: let only one source feed a given project. Either upload from CI only the
artifact that is actually deployed to that environment, or give the operator a separate
identity (a `repositories` override with another `name` or `namespace`, or another
`env`).

## Activation checklist

1. Release the operator image and chart that include this feature.
2. Create the API key Secret (or ExternalSecret) in the operator namespace.
3. Provision Dependency-Track and DefectDojo as above, including Product Types and, if
   used, teams.
4. Prepare values: URL, Secret, `identities` (start with one namespace).
5. Enable on one cluster at a time.
6. Watch `dependency_track_reports_total` and the operator logs; confirm the project,
   properties and ACL in Dependency-Track and the Product, engagement and test in
   DefectDojo.
7. Extend the mapping gradually.
