terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    bucket               = "loadsmart-sre-terraform-state"
    key                  = "terraform.tfstate"
    region               = "us-east-1"
    use_lockfile         = true
    workspace_key_prefix = "workspace"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = var.skip_credentials_validation
  skip_requesting_account_id  = var.skip_requesting_account_id
}
