# GitLab Server Configuration

# Public IP for GitLab
resource "yandex_vpc_address" "gitlab" {
  name = "${var.project_name}-gitlab-ip"
  
  external_ipv4_address {
    zone_id = var.yandex_zone
  }
  
  labels = local.common_tags
}

# GitLab Server Instance
resource "yandex_compute_instance" "gitlab" {
  name        = "${var.project_name}-gitlab"
  hostname    = local.gitlab_subdomain
  platform_id = "standard-v3"
  zone        = var.yandex_zone
  
  resources {
    cores  = var.gitlab_cores
    memory = var.gitlab_memory
  }
  
  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = var.gitlab_disk_size
      type     = "network-ssd"
    }
  }
  
  network_interface {
    subnet_id = yandex_vpc_subnet.public.id
    nat       = true
    nat_ip_address = yandex_vpc_address.gitlab.external_ipv4_address[0].address
    security_group_ids = [yandex_vpc_security_group.gitlab.id]
  }
  
  metadata = {
    user-data = templatefile("${path.module}/cloud-init/gitlab.yaml", {
      gitlab_hostname      = local.gitlab_fqdn
      gitlab_root_password = local.gitlab_root_password
      domain              = var.domain
    })
    ssh-keys  = "ubuntu:${var.ssh_public_key}"
  }
  
  labels = merge(
    local.common_tags,
    {
      service = "gitlab"
    }
  )
  
  scheduling_policy {
    preemptible = false
  }
}