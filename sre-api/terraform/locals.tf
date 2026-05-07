locals {
  # terraform.workspace is the first segment (e.g. development). Use:
  #   terraform workspace new development && terraform workspace select development
  workspace_slug = lower(replace(terraform.workspace, "_", "-"))
  # Product is fixed; workspace selects the deployment/state (and effectively the environment).
  product_slug = "challenge"
  # Kept as a separate field so tags/modules can still reference "Environment".
  environment_slug = local.workspace_slug

  # Naming: <workspace>-<product>[-suffix]
  name_prefix = "${local.workspace_slug}-${local.product_slug}"

  # ALB names max 32 chars. Override with var.alb_name (e.g. "default-alb" for the challenge).
  alb_name = var.alb_name == null ? "${local.name_prefix}-alb" : var.alb_name

  # Target group name max 32 chars.
  target_group_name = substr("${local.name_prefix}-tg", 0, 32)

  standard_tags = {
    Product     = local.product_slug
    Environment = local.environment_slug
  }
}
