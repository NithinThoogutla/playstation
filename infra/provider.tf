terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Owner       = var.owner
      Env         = var.environment
      App         = "DataPlatform"
      CostCenter  = var.cost_center
      ManagedBy   = "Terraform"
    }
  }
}
