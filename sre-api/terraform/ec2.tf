data "aws_ami" "al2023" {
  owners      = ["amazon"]
  most_recent = true
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_launch_template" "api" {
  name_prefix   = "${local.name_prefix}-api-"
  image_id      = data.aws_ami.al2023.id
  instance_type = var.instance_type

  iam_instance_profile {
    name = var.create_iam ? aws_iam_instance_profile.ec2[0].name : var.existing_instance_profile_name
  }

  vpc_security_group_ids = [aws_security_group.app.id]

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

  # Enforce IMDSv2 — prevents SSRF attacks from reaching the metadata service.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(local.standard_tags, {
      Name = "${local.name_prefix}-api"
    })
  }

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-lt-api"
  })
}

resource "aws_autoscaling_group" "api" {
  name                      = "${local.name_prefix}-asg"
  desired_capacity          = 2
  min_size                  = 1
  max_size                  = 4
  vpc_zone_identifier       = aws_subnet.private[*].id
  target_group_arns         = [aws_lb_target_group.api.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 300

  launch_template {
    id      = aws_launch_template.api.id
    version = aws_launch_template.api.latest_version
  }

  # Rolling replacement: swap one instance at a time, keeping ≥50% healthy.
  # Triggered automatically whenever container_tag changes the launch template version.
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
      instance_warmup        = 300
    }
  }

  dynamic "tag" {
    for_each = merge(local.standard_tags, { Name = "${local.name_prefix}-api" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  depends_on = [
    aws_lb_listener.http,
    aws_route.private_nat,
  ]

  lifecycle {
    create_before_destroy = true
  }
}
