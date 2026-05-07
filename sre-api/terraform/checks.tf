check "alb_name_length" {
  assert {
    condition     = length(local.alb_name) <= 32
    error_message = "ALB name must be at most 32 characters. Shorten terraform.workspace, product, or environment, or set alb_name explicitly."
  }
}
