# Manytask Server Configuration

# Generate Flask secret key
resource "random_password" "flask_secret" {
  length  = 64
  special = true
}

# Generate registration secret
resource "random_password" "registration_secret" {
  length  = 64
  special = false
}

# Generate tester token
resource "random_password" "tester_token" {
  length  = 64
  special = false
}

# Public IP for Manytask
resource "yandex_vpc_address" "manytask" {
  name = "${var.project_name}-manytask-ip"
  
  external_ipv4_address {
    zone_id = var.yandex_zone
  }
  
  labels = local.common_tags
}

# Manytask Server Instance
resource "yandex_compute_instance" "manytask" {
  name        = "${var.project_name}-manytask"
  hostname    = local.manytask_subdomain
  platform_id = "standard-v3"
  zone        = var.yandex_zone
  
  resources {
    cores  = var.manytask_cores
    memory = var.manytask_memory
  }
  
  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = var.manytask_disk_size
      type     = "network-ssd"
    }
  }
  
  network_interface {
    subnet_id = yandex_vpc_subnet.public.id
    nat       = true
    nat_ip_address = yandex_vpc_address.manytask.external_ipv4_address[0].address
    security_group_ids = [yandex_vpc_security_group.manytask.id]
  }
  
  metadata = {
    user-data = templatefile("${path.module}/cloud-init/manytask.yaml", {
      flask_secret_key      = random_password.flask_secret.result
      registration_secret   = random_password.registration_secret.result
      tester_token          = random_password.tester_token.result
      gitlab_hostname       = local.gitlab_fqdn
      postgres_password     = local.postgres_password
      postgresql_ip         = yandex_compute_instance.postgresql.network_interface[0].ip_address
      domain                = var.domain
      manytask_hostname     = local.manytask_fqdn
      manytask_version      = var.manytask_version
    })
    ssh-keys  = "ubuntu:${var.ssh_public_key}"
  }
  
  labels = merge(
    local.common_tags,
    {
      service = "manytask"
    }
  )
  
  scheduling_policy {
    preemptible = false
  }
  
  depends_on = [
    yandex_compute_instance.postgresql
  ]
}