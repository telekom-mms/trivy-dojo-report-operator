# Codebase Overview and Agents

## Project Summary
`trivy-dojo-report-operator` is a Kubernetes operator that automates the export of security reports from the Trivy Operator to DefectDojo. It is built using Python and the Kopf (Kubernetes Operator Pythonic Framework) framework.

## Architecture

The operator acts as a bridge between the Kubernetes cluster's security state (managed by Trivy) and the vulnerability management system (DefectDojo).

### "Agents" (Handlers)

The system consists of the following event handlers (agents) defined in `src/handlers.py`:

1.  **Startup Agent (`configure`)**
    -   **Type:** `@kopf.on.startup()`
    -   **Responsibility:** Initializes the operator configuration, setting timeouts for watching resources to prevent connection drops, and configuring the persistence storage mechanism (`StatusDiffBaseStorage`) to handle large resource objects efficiently without overloading Kubernetes annotations.

2.  **Report Forwarding Agent (`send_to_dojo`)**
    -   **Type:** `@kopf.on.create(...)` (Dynamic Registration, one per entry in `REPORTS`; skipped when `DEFECT_DOJO_REPORTS_ENABLED=false`)
    -   **Trigger:** Creation of Trivy-generated Custom Resources (CRs). The specific resources watched are configurable, but typically include:
        -   `vulnerabilityreports.aquasecurity.github.io`
        -   `configauditreports.aquasecurity.github.io`
        -   `exposedsecretreports.aquasecurity.github.io`
        -   `infraassessmentreports.aquasecurity.github.io`
        -   `rbacassessmentreports.aquasecurity.github.io`
    -   **Responsibility:**
        -   **Extraction:** Extracts the full manifest of the created report.
        -   **Transformation:** Converts the Kubernetes object into a JSON-compatible dictionary.
        -   **Context Resolution:** dynamic evaluation of DefectDojo engagement parameters (Product Type, Product, Environment, Engagement Name) using the logic in `settings.py`.
        -   **Transmission:** Uploads the report to the DefectDojo API (`/api/v2/import-scan/`) using the `requests` library.
        -   **Observability:** Records Prometheus metrics, including processing time (`request_processing_seconds`) and request counters (`requests_total`).

3.  **SBOM Agent (`sbom_to_dependency_track`)**
    -   **Type:** `@kopf.on.create`, `@kopf.on.update` and `@kopf.on.resume` (registered only when `DEPENDENCY_TRACK_REPORTS_ENABLED=true`, in `src/dependency_track.py`)
    -   **Trigger:** `sbomreports.aquasecurity.github.io` (not `ClusterSbomReport`, not part of `REPORTS`). Trivy Operator updates the report on every rescan and drops its status, so all three causes share one handler.
    -   **Responsibility:**
        -   **Identity:** resolves project name, version, tags, ACL team, group-by and the DefectDojo Product, Product Type, engagement, environment and test title from the `DEPENDENCY_TRACK_*` values (used as is, or eval-ed per report with `body` and `meta` when the matching `DEPENDENCY_TRACK_EVAL_*` flag is `true`); an empty required value skips the report.
        -   **Change detection:** hashes all resolved values, URLs, image digest and scanner version and keeps `key`, `stage` and `project` in the annotation `dependency-track.trivy-dojo-report-operator/state`; nothing is sent when it is already `linked`.
        -   **Transmission:** uploads the BOM to Dependency-Track, creates the DefectDojo Product if missing, reimports an empty FPF to create engagement and test, sets the project properties and, with `DEPENDENCY_TRACK_ACL_TEAM`, maps the ACL team.
        -   **Resilience:** temporary errors retry 10 times, 60 s apart; permanent errors stop. Concurrency is limited only by the Kopf thread pool.
        -   **Observability:** `dependency_track_reports_total`.
    -   Details: [docs/DEPENDENCY-TRACK.md](docs/DEPENDENCY-TRACK.md).

## Configuration

The agents are configured via environment variables (loaded in `src/settings.py` and `src/env_vars.py`), controlling:

-   **Connectivity:** DefectDojo URL (`DEFECT_DOJO_URL`) and API Key (`DEFECT_DOJO_API_KEY`).
-   **Scope:** optional filtering by Kubernetes Label (`LABEL`, `LABEL_VALUE`); `REPORTS` and `DEFECT_DOJO_REPORTS_ENABLED` (default `true`) select the reports sent to DefectDojo.
-   **Dependency-Track (optional):** `DEPENDENCY_TRACK_REPORTS_ENABLED`, `DEPENDENCY_TRACK_URL`, `DEPENDENCY_TRACK_API_KEY`, `DEPENDENCY_TRACK_PROJECT_NAME`, `DEPENDENCY_TRACK_PROJECT_VERSION` (required), plus optional `DEPENDENCY_TRACK_PROJECT_TAGS`, `DEPENDENCY_TRACK_ACL_TEAM`, `DEPENDENCY_TRACK_GROUP_BY` and `DEPENDENCY_TRACK_DEFECT_DOJO_*`, each with an `EVAL` flag.
-   **Import Logic:**
    -   `DEFECT_DOJO_ACTIVE`: Whether findings are marked as active.
    -   `DEFECT_DOJO_VERIFIED`: Whether findings are marked as verified.
    -   `DEFECT_DOJO_CLOSE_OLD_FINDINGS`: Whether to close old findings in DefectDojo.
    -   `DEFECT_DOJO_PUSH_TO_JIRA`: Whether to push findings to Jira.

## Deployment

The operator is packaged as a Docker container and deployed via a Helm chart located in the `charts/` directory.
