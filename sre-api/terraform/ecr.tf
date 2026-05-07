resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-ecr-api"
  })
}
