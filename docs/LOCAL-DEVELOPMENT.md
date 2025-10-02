# Local Development

This is a short step-by-step documentation on how to create a local development
environment for this operator.

## Prerequisites

- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- [helm](https://helm.sh/docs/intro/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [poetry](https://python-poetry.org/docs/#installation)

## Using Minikube

- Create and start a local Cluster and enable ingress

  ```bash
  minikube start --kubernetes-version=v1.32
  minikube addons enable ingress
  ```

- Deploy the Trivy Operator

  ```bash
  helm repo add aqua https://aquasecurity.github.io/helm-charts/
  helm repo update
  helm install trivy-operator aqua/trivy-operator \
    --namespace trivy-system \
    --create-namespace
  ```

- Setup and deploy
[DefectDojo](https://github.com/DefectDojo/django-DefectDojo/blob/master/readme-docs/KUBERNETES.md)

  ```bash
  helm repo add helm-charts 'https://raw.githubusercontent.com/DefectDojo/django-DefectDojo/helm-charts'
  # Add repos for sub-charts
  helm repo add bitnami https://charts.bitnami.com/bitnami
  helm repo update

  # Clone the repository and pull dependent charts
  git clone https://github.com/DefectDojo/django-DefectDojo
  cd django-DefectDojo
  helm dependency update ./helm/defectdojo

  # Install the chart
  helm install \
    defectdojo \
    ./helm/defectdojo \
    --set django.ingress.enabled=true \
    --set django.ingress.activateTLS=false \
    --set createSecret=true \
    --set createRabbitMqSecret=true \
    --set createRedisSecret=true \
    --set createMysqlSecret=true \
    --set createPostgresqlSecret=true \
    --set host=localhost
  ```

- Retrieve DefectDojo admin password

  ```bash
  echo "DefectDojo admin password: $(kubectl \
      get secret defectdojo \
      --namespace=trivy-system \
      --output jsonpath='{.data.DD_ADMIN_PASSWORD}' \
      | base64 --decode)"
  ```

- Port forward DefectDojo service

  ```bash
  kubectl port-forward --namespace=default service/defectdojo-django 8080:80
  ```

- [Retrieve DefectDojo API-Key](http://localhost:8080/api/key-v2)
- Configure environment variables

  ```bash
  export DEFECT_DOJO_API_KEY="YOUR_API_KEY"
  export DEFECT_DOJO_URL="http://localhost:8080"
  export LABEL="trivy-operator.resource.name"; export LABEL_VALUE="your-label-value";
  export DEFECT_DOJO_ENGAGEMENT_NAME="test"
  export DEFECT_DOJO_AUTO_CREATE_CONTEXT=true
  export DEFECT_DOJO_ACTIVE=true
  export DEFECT_DOJO_PRODUCT_NAME="Research and Development"
  export DEFECT_DOJO_PRODUCT_TYPE_NAME="Research and Development"
  ```

- Install the Python dependencies

  ```bash
  poetry install --no-root
  ```

- Run Kopf

  ```bash
  poetry run kopf run src/handlers.py --all-namespaces

  [2023-11-06 15:56:49,610] settings             [INFO    ] Looking for resources with LABEL 'trivy-operator.resource.name' and LABEL_VALUE 'your-label-value'
  [2023-11-06 15:56:49,646] kopf.activities.star [INFO    ] Activity 'configure' succeeded.
  [2023-11-06 15:56:49,647] kopf._core.engines.a [INFO    ] Initial authentication has been initiated.
  [2023-11-06 15:56:49,654] kopf.activities.auth [INFO    ] Activity 'login_via_client' succeeded.
  [2023-11-06 15:56:49,654] kopf._core.engines.a [INFO    ] Initial authentication has finished.
  ```

- Create a pod, thus a VulnerabilityReport

  ```bash
  kubectl run --image debian:12 your-label-value bash
  ```

- Check the logs in kopf:

  ```bash
  [2023-11-07 08:57:36,430] kopf.objects         [INFO    ] [default/pod-your-label-value] Working on pod-your-label-value
  [2023-11-07 08:57:40,048] kopf.objects         [INFO    ] [default/pod-your-label-value] Finished pod-your-label-value
  [2023-11-07 08:57:40,050] kopf.objects         [INFO    ] [default/pod-your-label-value] Handler 'send_to_dojo' succeeded.
  [2023-11-07 08:57:40,051] kopf.objects         [INFO    ] [default/pod-your-label-value] Creation is processed: 1 succeeded; 0 failed.
  ```

## Troubleshooting

### Enabling ingress addon fails

Issue:

```bash
minikube addons enable ingress

Exiting due to MK_ADDON_ENABLE: enable failed: run callbacks: running callbacks: [waiting for app.kubernetes.io/name=ingress-nginx pods: context deadline exceeded]
```

Solution:

Completely clean up your minikube environment and start over

```bash
minikube delete --all
```
