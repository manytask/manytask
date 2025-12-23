# Random passwords generation
resource "random_password" "gitlab_root" {
  count   = var.gitlab_root_password == "" ? 1 : 0
  length  = 32
  special = true
}

resource "random_password" "postgres" {
  count   = var.postgres_password == "" ? 1 : 0
  length  = 32
  special = false
}

# Local variables
locals {
  gitlab_root_password = var.gitlab_root_password != "" ? var.gitlab_root_password : random_password.gitlab_root[0].result
  postgres_password    = var.postgres_password != "" ? var.postgres_password : random_password.postgres[0].result
  
  gitlab_subdomain     = "gitlab"
  manytask_subdomain   = "manytask"
  
  gitlab_fqdn          = "${local.gitlab_subdomain}.${var.domain}"
  manytask_fqdn        = "${local.manytask_subdomain}.${var.domain}"
  
  common_tags = merge(
    {
      project     = var.project_name
      managed-by  = "terraform"
      environment = "production"
    },
    var.tags
  )
}

# Data sources
data "yandex_compute_image" "ubuntu" {
  family = "ubuntu-2204-lts"
}