# Output values for the infrastructure

# Network Information
output "vpc_id" {
  description = "ID of the VPC network"
  value       = yandex_vpc_network.main.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = yandex_vpc_subnet.public.id
}

output "private_subnet_id" {
  description = "ID of the private subnet"
  value       = yandex_vpc_subnet.private.id
}

# GitLab Server
output "gitlab_public_ip" {
  description = "Public IP address of GitLab server"
  value       = yandex_vpc_address.gitlab.external_ipv4_address[0].address
}

output "gitlab_url" {
  description = "GitLab URL"
  value       = "https://${local.gitlab_fqdn}"
}

output "gitlab_root_password" {
  description = "GitLab root password"
  value       = local.gitlab_root_password
  sensitive   = true
}

output "gitlab_ssh_command" {
  description = "SSH command to connect to GitLab server"
  value       = "ssh ubuntu@${yandex_vpc_address.gitlab.external_ipv4_address[0].address}"
}

# Manytask Server
output "manytask_public_ip" {
  description = "Public IP address of Manytask server"
  value       = yandex_vpc_address.manytask.external_ipv4_address[0].address
}

output "manytask_url" {
  description = "Manytask URL"
  value       = "https://${local.manytask_fqdn}"
}

output "manytask_ssh_command" {
  description = "SSH command to connect to Manytask server"
  value       = "ssh ubuntu@${yandex_vpc_address.manytask.external_ipv4_address[0].address}"
}

# PostgreSQL Server
output "postgresql_private_ip" {
  description = "Private IP address of PostgreSQL server"
  value       = yandex_compute_instance.postgresql.network_interface[0].ip_address
}

output "postgresql_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://manytask:${local.postgres_password}@${yandex_compute_instance.postgresql.network_interface[0].ip_address}:5432/manytask"
  sensitive   = true
}

output "postgresql_password" {
  description = "PostgreSQL password for manytask user"
  value       = local.postgres_password
  sensitive   = true
}

# DNS Information
output "dns_zone_id" {
  description = "ID of the DNS zone"
  value       = var.create_dns_zone ? yandex_dns_zone.main[0].id : null
}

output "dns_nameservers" {
  description = "DNS nameservers for the zone"
  value       = var.create_dns_zone ? "Configure your domain registrar to use Yandex Cloud DNS nameservers" : null
}

# Summary
output "deployment_summary" {
  description = "Summary of the deployed infrastructure"
  value = <<-EOT
    
    ========================================
    Manytask Infrastructure Deployment
    ========================================
    
    Domain: ${var.domain}
    
    Services:
    ---------
    GitLab:    https://${local.gitlab_fqdn}
    Manytask:  https://${local.manytask_fqdn}
    
    Access Information:
    -------------------
    GitLab Root Password: [SENSITIVE - use: terraform output gitlab_root_password]
    PostgreSQL Password:  [SENSITIVE - use: terraform output postgresql_password]
    
    SSH Access:
    -----------
    GitLab:     ssh ubuntu@${yandex_vpc_address.gitlab.external_ipv4_address[0].address}
    Manytask:   ssh ubuntu@${yandex_vpc_address.manytask.external_ipv4_address[0].address}
    
    Next Steps:
    -----------
    1. Wait 5-10 minutes for GitLab to fully initialize
    2. Access GitLab and create OAuth application
    3. Update /opt/manytask/.env on Manytask server with OAuth credentials
    4. Restart Manytask: ssh to server and run 'cd /opt/manytask && docker-compose restart manytask'
    ${var.create_dns_zone ? "\n5. Configure your domain registrar to use Yandex Cloud DNS nameservers" : ""}
    
    ========================================
  EOT
}