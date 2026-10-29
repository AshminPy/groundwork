In the Terraform in `main.tf`:
1. Every resource must carry tags: `tags = merge(local.common_tags, { environment = var.environment })`.
2. `var.environment` must only accept `dev`, `staging` or `prod`: add a `validation` block with a clear error
   message.
3. Add a `description` to the variable.
Do not rename resources or change their other arguments. No cloud calls: the change is checked statically.
