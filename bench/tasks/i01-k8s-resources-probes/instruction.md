Production readiness review for `k8s/deployment.yaml`. For the `orders` container only, add:
- resource requests of `250m` CPU and `256Mi` memory, and limits of `500m` CPU and `512Mi` memory;
- a readiness probe: HTTP GET `/healthz` on port 8080, initial delay 5 seconds, period 10 seconds;
- a liveness probe: HTTP GET `/livez` on port 8080, initial delay 15 seconds, period 20 seconds.
Leave the `log-shipper` container and everything else unchanged. The file must stay valid Kubernetes YAML.
