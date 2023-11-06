# Local Development

This is a short step-by-step documentation on how to create a local development
environment for this operator.

## Prerequisites

- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- [helm](https://helm.sh/docs/intro/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [kopf](https://github.com/nolar/kopf)
  - Install via [requirements.txt](../requirements.txt) using pip

## Using Minikube

- Create and start a local Cluster and enable ingress

  ```bash
  minikube start
  minikube addons enable ingress
  ```

- Deploy the Trivy Operator

  ```bash
  kubectl apply -f https://raw.githubusercontent.com/aquasecurity/trivy-operator/v0.16.4/deploy/static/trivy-operator.yaml
  ```

- Setup and deploy
[DefectDojo](https://github.com/DefectDojo/django-DefectDojo/blob/master/readme-docs/KUBERNETES.md)

  ```bash
  helm repo add helm-charts 'https://raw.githubusercontent.com/DefectDojo/django-DefectDojo/helm-charts'
  helm repo update

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
    --set createPostgresqlSecret=true
  ```

- Add to /etc/hosts file

  ```bash
  ::1       defectdojo.default.minikube.local
  127.0.0.1 defectdojo.default.minikube.local
  ```

- Retrieve DefectDojo admin password

  ```bash
  echo "DefectDojo admin password: $(kubectl \
  get secret defectdojo \
  --namespace=default \
  --output jsonpath='{.data.DD_ADMIN_PASSWORD}' \
  | base64 --decode)"
  ```

- Port forward DefectDojo service

  ```bash
  kubectl port-forward --namespace=default service/defectdojo-django 8080:80
  # Access service via http://defectdojo.default.minikube.local:8080/
  ```

- [Retrieve DefectDojo API-Key](http://defectdojo.default.minikube.local:8080/api/key-v2)
- Configure environment variables

  ```bash
  export DEFECT_DOJO_API_KEY="YOUR_API_KEY"
  export DEFECT_DOJO_URL="http://defectdojo.default.minikube.local:8080"
  export LABEL="trivy-operator.resource.name"; export LABEL_VALUE="your_label_value";
  ```

- Run Kopf

  ```bash
  $ kopf run src/handlers.py --all-namespaces

  [2023-11-06 15:56:49,610] settings             [INFO    ] Looking for resources with LABEL 'trivy-operator.resource.name' and LABEL_VALUE 'your_label_value'
  [2023-11-06 15:56:49,646] kopf.activities.star [INFO    ] Activity 'configure' succeeded.
  [2023-11-06 15:56:49,647] kopf._core.engines.a [INFO    ] Initial authentication has been initiated.
  [2023-11-06 15:56:49,654] kopf.activities.auth [INFO    ] Activity 'login_via_client' succeeded.
  [2023-11-06 15:56:49,654] kopf._core.engines.a [INFO    ] Initial authentication has finished.
  ```
