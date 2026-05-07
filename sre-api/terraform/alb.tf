resource "aws_lb_target_group" "api" {
  name                 = local.target_group_name
  port                 = 80
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  target_type          = "instance"
  deregistration_delay = 30

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-tg-api"
  })

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    protocol            = "HTTP"
    path                = "/healthcheck"
    port                = "traffic-port"
    matcher             = "200"
  }
}

resource "aws_lb" "api" {
  name               = local.alb_name
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = merge(local.standard_tags, {
    Name = local.alb_name
  })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  # Redirect to HTTPS when a certificate is configured; otherwise forward directly.
  default_action {
    type = var.domain_name != null ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.domain_name != null ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "forward" {
      for_each = var.domain_name == null ? [1] : []
      content {
        target_group {
          arn = aws_lb_target_group.api.arn
        }
      }
    }
  }
}

resource "aws_acm_certificate" "api" {
  count             = var.domain_name != null ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.standard_tags, {
    Name = "${local.name_prefix}-cert"
  })
}

resource "aws_lb_listener" "https" {
  count             = var.domain_name != null ? 1 : 0
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.api[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
