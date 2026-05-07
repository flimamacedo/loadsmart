variable "aws_region" {
  type        = string
  description = "Region for all resources"
  default     = "us-east-1"
}

variable "skip_credentials_validation" {
  type        = bool
  description = "Set true to allow terraform init/validate without AWS credentials (CI)."
  default     = true
}

variable "skip_requesting_account_id" {
  type        = bool
  description = "Set true to avoid STS calls during provider init (CI)."
  default     = true
}

variable "create_iam" {
  type        = bool
  description = "Whether Terraform should create the EC2 IAM role + instance profile. Set false if your AWS principal cannot create IAM roles."
  default     = true
}

variable "existing_instance_profile_name" {
  type        = string
  description = "Existing IAM instance profile name to attach to the EC2 instance when create_iam=false."
  default     = null
  nullable    = true
}

variable "alb_name" {
  type        = string
  default     = "default-alb"
  nullable    = true
  description = "ALB name. The challenge requires \"default-alb\" so that /elb/default-alb resolves. Override with null to fall back to \"<workspace>-challenge-alb\"."
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type (use free-tier eligible in your account)"
  default     = "t3.micro"
}

variable "api_basic_user" {
  type        = string
  description = "HTTP Basic user for the API"
  sensitive   = true
}

variable "api_basic_password" {
  type        = string
  description = "HTTP Basic password for the API"
  sensitive   = true
}

variable "container_tag" {
  type        = string
  description = "Container image tag pushed to the created ECR repository"
  default     = "latest"
}

variable "vpc_cidr" {
  type        = string
  description = "Dedicated VPC CIDR; public subnets use cidrsubnet(vpc_cidr, 8, 1..public_subnet_count)"
  default     = "10.0.0.0/16"
}

variable "public_subnet_count" {
  type        = number
  description = "Number of public subnets across the first N AZs (min 2 for ALB)"
  default     = 2

  validation {
    condition     = var.public_subnet_count >= 2 && var.public_subnet_count <= 6
    error_message = "public_subnet_count must be between 2 and 6."
  }
}

variable "ecr_aws_access_key_id" {
  type        = string
  description = "AWS access key used by EC2 to pull from ECR (only needed when create_iam=false)"
  sensitive   = true
  default     = null
  nullable    = true
}

variable "ecr_aws_secret_access_key" {
  type        = string
  description = "AWS secret key used by EC2 to pull from ECR (only needed when create_iam=false)"
  sensitive   = true
  default     = null
  nullable    = true
}

variable "domain_name" {
  type        = string
  default     = null
  nullable    = true
  description = "Domain name for ACM TLS certificate (DNS validation) and HTTPS listener on port 443. Leave null to disable HTTPS."
}
