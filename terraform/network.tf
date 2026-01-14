# VPC Network
resource "yandex_vpc_network" "main" {
  name        = "${var.project_name}-network"
  description = "Main network for ${var.project_name} infrastructure"
  
  labels = local.common_tags
}

# Public Subnet
resource "yandex_vpc_subnet" "public" {
  name           = "${var.project_name}-public-subnet"
  description    = "Public subnet for external-facing services"
  zone           = var.yandex_zone
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = [var.public_subnet_cidr]
  
  labels = local.common_tags
}

# Private Subnet
resource "yandex_vpc_subnet" "private" {
  name           = "${var.project_name}-private-subnet"
  description    = "Private subnet for internal services (database)"
  zone           = var.yandex_zone
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = [var.private_subnet_cidr]
  route_table_id = yandex_vpc_route_table.private_rt.id
  
  labels = local.common_tags
}

# NAT Gateway for private subnet
resource "yandex_vpc_gateway" "nat_gateway" {
  name = "${var.project_name}-nat-gateway"
  
  shared_egress_gateway {}
  
  labels = local.common_tags
}

# Route table for private subnet
resource "yandex_vpc_route_table" "private_rt" {
  name       = "${var.project_name}-private-rt"
  network_id = yandex_vpc_network.main.id

  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = yandex_vpc_gateway.nat_gateway.id
  }
  
  labels = local.common_tags
}

# Security Group for GitLab
resource "yandex_vpc_security_group" "gitlab" {
  name        = "${var.project_name}-gitlab-sg"
  description = "Security group for GitLab server"
  network_id  = yandex_vpc_network.main.id

  ingress {
    protocol       = "TCP"
    description    = "SSH"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 22
  }

  ingress {
    protocol       = "TCP"
    description    = "HTTP"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 80
  }

  ingress {
    protocol       = "TCP"
    description    = "HTTPS"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 443
  }

  ingress {
    protocol       = "ICMP"
    description    = "ICMP ping"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    protocol       = "ANY"
    description    = "Allow all outbound traffic"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  labels = local.common_tags
}

# Security Group for Manytask
resource "yandex_vpc_security_group" "manytask" {
  name        = "${var.project_name}-manytask-sg"
  description = "Security group for Manytask server"
  network_id  = yandex_vpc_network.main.id

  ingress {
    protocol       = "TCP"
    description    = "SSH"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 22
  }

  ingress {
    protocol       = "TCP"
    description    = "HTTP"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 80
  }

  ingress {
    protocol       = "TCP"
    description    = "HTTPS"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 443
  }

  ingress {
    protocol       = "ICMP"
    description    = "ICMP ping"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    protocol       = "ANY"
    description    = "Allow all outbound traffic"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  labels = local.common_tags
}

# Security Group for PostgreSQL
resource "yandex_vpc_security_group" "postgresql" {
  name        = "${var.project_name}-postgresql-sg"
  description = "Security group for PostgreSQL server"
  network_id  = yandex_vpc_network.main.id

  ingress {
    protocol       = "TCP"
    description    = "SSH from anywhere (temporary for debugging)"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 22
  }

  ingress {
    protocol       = "TCP"
    description    = "PostgreSQL from public subnet"
    v4_cidr_blocks = [var.public_subnet_cidr]
    port           = 5432
  }

  ingress {
    protocol       = "ICMP"
    description    = "ICMP ping from public subnet"
    v4_cidr_blocks = [var.public_subnet_cidr]
  }

  egress {
    protocol       = "ANY"
    description    = "Allow all outbound traffic"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  labels = local.common_tags
}
