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
    -   **Type:** `@kopf.on.create(...)` (Dynamic Registration)
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

## Configuration

The agents are configured via environment variables (loaded in `src/settings.py` and `src/env_vars.py`), controlling:

-   **Connectivity:** DefectDojo URL (`DEFECT_DOJO_URL`) and API Key (`DEFECT_DOJO_API_KEY`).
-   **Scope:** optional filtering by Kubernetes Label (`LABEL`, `LABEL_VALUE`).
-   **Import Logic:**
    -   `DEFECT_DOJO_ACTIVE`: Whether findings are marked as active.
    -   `DEFECT_DOJO_VERIFIED`: Whether findings are marked as verified.
    -   `DEFECT_DOJO_CLOSE_OLD_FINDINGS`: Whether to close old findings in DefectDojo.
    -   `DEFECT_DOJO_PUSH_TO_JIRA`: Whether to push findings to Jira.

## Deployment

The operator is packaged as a Docker container and deployed via a Helm chart located in the `charts/` directory.
