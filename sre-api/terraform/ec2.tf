data "aws_ami" "al2023" {
  owners      = ["amazon"]
  most_recent = true
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "api" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile          = var.create_iam ? aws_iam_instance_profile.ec2[0].name : var.existing_instance_profile_name
  subnet_id                     = aws_subnet.public[0].id
  user_data = base64encode(templatefile("${path.module}/user-data.sh.tpl", {
    region            = var.aws_region
    ecr_registry      = split("/", aws_ecr_repository.api.repository_url)[0]
    repository_uri    = aws_ecr_repository.api.repository_url
    image_tag         = var.container_tag
    basic_user_b64    = base64encode(var.api_basic_user)
    basic_pass_b64    = base64encode(var.api_basic_password)
    aws_access_key_id = var.ecr_aws_access_key_id != null ? var.ecr_aws_access_key_id : ""
    aws_secret_key    = var.ecr_aws_secret_access_key != null ? var.ecr_aws_secret_access_key : ""
  }))

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-api"
  })

  depends_on = [
    aws_lb_listener.http,
    aws_route_table_association.public,
  ]
}

resource "aws_lb_target_group_attachment" "api" {
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = aws_instance.api.id
  port             = 80
}
