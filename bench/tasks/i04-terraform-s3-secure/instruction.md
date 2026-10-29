`s3.tf` defines a bucket that holds customer exports. Make it secure, using the AWS provider v5
style (separate resources, not inline blocks on the bucket):
- block all public access (all four settings true);
- enable versioning;
- default encryption with SSE-KMS using the existing key `aws_kms_key.exports` (add that key resource with key
  rotation enabled if it is not defined);
- deny any request that is not over TLS with a bucket policy (`aws:SecureTransport` = false).
Checked statically; no cloud calls.
