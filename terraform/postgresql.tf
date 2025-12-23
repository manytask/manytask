# PostgreSQL Server Configuration

# PostgreSQL Server Instance (Private Subnet)
resource "yandex_compute_instance" "postgresql" {
  name        = "${var.project_name}-postgresql"
  hostname    = "postgresql"
  platform_id = "standard-v3"
  zone        = var.yandex_zone
  
  resources {
    cores  = var.postgresql_cores
    memory = var.postgresql_memory
  }
  
  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = var.postgresql_disk_size
      type     = "network-ssd"
    }
  }
  
  network_interface {
    subnet_id = yandex_vpc_subnet.private.id
    nat       = true
    security_group_ids = [yandex_vpc_security_group.postgresql.id]
  }
  
  metadata = {
    user-data = templatefile("${path.module}/cloud-init/postgresql.yaml", {
      postgresql_version   = var.postgresql_version
      postgres_password    = local.postgres_password
      public_subnet_cidr   = var.public_subnet_cidr
      postgresql_ip        = "POSTGRESQL_IP"
    })
    ssh-keys  = "ubuntu:${var.ssh_public_key}"
  }
  
  labels = merge(
    local.common_tags,
    {
      service = "postgresql"
    }
  )
  
  scheduling_policy {
    preemptible = false
  }
}