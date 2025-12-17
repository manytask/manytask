# General Configuration
variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "manytask"
}

variable "domain" {
  description = "Base domain for the infrastructure (e.g., example.com)"
  type        = string
}

variable "yandex_cloud_id" {
  description = "Yandex Cloud ID"
  type        = string
}

variable "yandex_folder_id" {
  description = "Yandex Cloud Folder ID"
  type        = string
}

variable "yandex_zone" {
  description = "Yandex Cloud availability zone"
  type        = string
  default     = "ru-central1-a"
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "private_subnet_cidr" {
  description = "CIDR block for private subnet"
  type        = string
  default     = "10.0.2.0/24"
}

# GitLab Server Configuration
variable "gitlab_cores" {
  description = "Number of CPU cores for GitLab server"
  type        = number
  default     = 4
}

variable "gitlab_memory" {
  description = "Amount of RAM in GB for GitLab server"
  type        = number
  default     = 8
}

variable "gitlab_disk_size" {
  description = "Disk size in GB for GitLab server"
  type        = number
  default     = 100
}

variable "gitlab_image_family" {
  description = "OS image family for GitLab server"
  type        = string
  default     = "ubuntu-2204-lts"
}

# Manytask Server Configuration
variable "manytask_cores" {
  description = "Number of CPU cores for Manytask server"
  type        = number
  default     = 2
}

variable "manytask_memory" {
  description = "Amount of RAM in GB for Manytask server"
  type        = number
  default     = 8
}

variable "manytask_disk_size" {
  description = "Disk size in GB for Manytask server"
  type        = number
  default     = 50
}

variable "manytask_image_family" {
  description = "OS image family for Manytask server"
  type        = string
  default     = "ubuntu-2204-lts"
}

# PostgreSQL Server Configuration
variable "postgresql_cores" {
  description = "Number of CPU cores for PostgreSQL server"
  type        = number
  default     = 2
}

variable "postgresql_memory" {
  description = "Amount of RAM in GB for PostgreSQL server"
  type        = number
  default     = 4
}

variable "postgresql_disk_size" {
  description = "Disk size in GB for PostgreSQL server"
  type        = number
  default     = 50
}

variable "postgresql_image_family" {
  description = "OS image family for PostgreSQL server"
  type        = string
  default     = "ubuntu-2204-lts"
}

variable "postgresql_version" {
  description = "PostgreSQL version to install"
  type        = string
  default     = "15"
}

# Application Configuration
variable "manytask_version" {
  description = "Manytask Docker image version"
  type        = string
  default     = "latest"
}

variable "gitlab_root_password" {
  description = "GitLab root password (leave empty to auto-generate)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "postgres_password" {
  description = "PostgreSQL password (leave empty to auto-generate)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for server access"
  type        = string
}

# DNS Configuration
variable "create_dns_zone" {
  description = "Create DNS zone in Yandex Cloud (set to false if managing DNS externally)"
  type        = bool
  default     = true
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}