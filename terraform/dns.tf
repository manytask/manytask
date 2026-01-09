# DNS Configuration

# DNS Zone
resource "yandex_dns_zone" "main" {
  count = var.create_dns_zone ? 1 : 0
  
  name        = "${var.project_name}-zone"
  description = "DNS zone for ${var.project_name} infrastructure"
  zone        = "${var.domain}."
  public      = true
  
  labels = local.common_tags
}

# A Record for GitLab
resource "yandex_dns_recordset" "gitlab" {
  count = var.create_dns_zone ? 1 : 0
  
  zone_id = yandex_dns_zone.main[0].id
  name    = "${local.gitlab_subdomain}.${var.domain}."
  type    = "A"
  ttl     = 300
  data    = [yandex_vpc_address.gitlab.external_ipv4_address[0].address]
}

# A Record for Manytask
resource "yandex_dns_recordset" "manytask" {
  count = var.create_dns_zone ? 1 : 0
  
  zone_id = yandex_dns_zone.main[0].id
  name    = "${local.manytask_subdomain}.${var.domain}."
  type    = "A"
  ttl     = 300
  data    = [yandex_vpc_address.manytask.external_ipv4_address[0].address]
}

# Wildcard A Record for Manytask (for multiple courses)
resource "yandex_dns_recordset" "manytask_wildcard" {
  count = var.create_dns_zone ? 1 : 0
  
  zone_id = yandex_dns_zone.main[0].id
  name    = "*.${var.domain}."
  type    = "A"
  ttl     = 300
  data    = [yandex_vpc_address.manytask.external_ipv4_address[0].address]
}

# A Record for docs subdomain (points to Manytask server)
resource "yandex_dns_recordset" "docs" {
  count = var.create_dns_zone ? 1 : 0
  
  zone_id = yandex_dns_zone.main[0].id
  name    = "docs.${var.domain}."
  type    = "A"
  ttl     = 300
  data    = [yandex_vpc_address.manytask.external_ipv4_address[0].address]
}