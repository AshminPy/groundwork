resource "aws_iam_role_policy" "worker" {
  name   = "reports-worker"
  role   = aws_iam_role.worker.id
  policy = file("${path.module}/policy.json")
}
