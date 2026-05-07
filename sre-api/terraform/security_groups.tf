resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb"
  description = "ALB ingress (${local.name_prefix})"
  vpc_id      = aws_vpc.main.id

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-sg-alb"
  })

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app"
  description = "API instance - from ALB only (${local.name_prefix})"
  vpc_id      = aws_vpc.main.id

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-sg-app"
  })

  ingress {
    description     = "HTTP from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
