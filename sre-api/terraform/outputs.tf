output "name_prefix" {
  description = "Computed resource prefix: workspace-product"
  value       = local.name_prefix
}

output "vpc_id" {
  description = "Dedicated VPC for this stack"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "alb_name" {
  description = "Application load balancer name (use in API /elb/{name} and DNS)"
  value       = aws_lb.api.name
}

output "alb_dns_name" {
  description = "Public DNS name for the ALB (port 80)"
  value       = aws_lb.api.dns_name
}

output "ecr_repository_name" {
  description = "ECR repository name (GitHub Actions var ECR_REPOSITORY_NAME)"
  value       = aws_ecr_repository.api.name
}

output "ecr_repository_url" {
  description = "Push your built image here before the instance can start serving"
  value       = aws_ecr_repository.api.repository_url
}

output "api_instance_id" {
  value = aws_instance.api.id
}
