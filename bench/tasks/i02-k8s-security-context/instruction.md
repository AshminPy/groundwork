Harden `k8s/deployment.yaml` to meet the restricted Pod Security Standard. Set, at pod level,
`runAsNonRoot: true`, `runAsUser: 10001` and the `RuntimeDefault` seccomp profile. For every container, set
`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` and drop all Linux capabilities. Do not change
images, names, replicas or ports. The file must stay valid Kubernetes YAML.
