The `checkout-api` rollout in `k8s/` is broken: the Deployment is rejected, the Service has no
endpoints, the autoscaler does nothing, node drains hang, and the pod would not start if it were scheduled. Fix the
manifests so they are consistent with each other and with these intentions:
- the Deployment is `checkout-api`, with 2 replicas, image `registry.example.com/checkout-api:3.4.1`, and pods
  labelled `app: checkout-api` and `tier: backend`;
- the Service sends port 80 to the container's port 8080;
- the HPA scales the Deployment between 2 and 6 replicas;
- the PodDisruptionBudget allows one pod to be evicted at a time;
- `DB_POOL_SIZE` comes from the ConfigMap's existing pool-size key.
Do not change the image, names, replica counts or the ConfigMap's data. The files must stay valid Kubernetes YAML.
Checked statically; no cluster is used.
