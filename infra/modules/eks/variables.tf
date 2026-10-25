variable "name" {
  type        = string
  description = "Cluster and IAM resource prefix."
  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9-]{0,39}$", var.name))
    error_message = "Use a letter followed by up to 39 letters, digits or hyphens."
  }
}
variable "subnet_ids" {
  type        = list(string)
  description = "Private subnets spanning at least two AZs; caller owns routing and AZ validation."
  validation {
    condition     = length(distinct(var.subnet_ids)) >= 2
    error_message = "Supply at least two distinct private subnet IDs."
  }
}
variable "admin_principal_arn" {
  type        = string
  description = "Stable IAM role or user ARN granted explicit cluster administrator access."
  validation {
    condition     = can(regex("^arn:[^:]+:iam::[0-9]{12}:(role|user)/.+$", var.admin_principal_arn))
    error_message = "Supply an IAM role/user ARN, not a root or STS session ARN."
  }
}
variable "kubernetes_version" {
  type        = string
  description = "Explicit EKS version; caller must verify standard support before apply."
  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "Use an explicit Kubernetes minor version such as 1.34."
  }
}
variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional EC2 instance and volume tags; provider default_tags cover other resources."
}
variable "enable_demo_ssm" {
  type        = bool
  default     = false
  description = "Opt-in existing-node SSM channels for private evidence capture. No ingress or static credentials."
}
variable "log_retention_days" {
  type        = number
  default     = 3
  description = "Control-plane log retention; short default is for the bounded assignment."
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 730], var.log_retention_days)
    error_message = "Select a supported nonzero retention period."
  }
}
variable "cluster_log_types" {
  type        = set(string)
  default     = ["api", "audit", "authenticator"]
  description = "Control-plane logs; audit and authenticator are mandatory."
  validation {
    condition     = alltrue([for x in var.cluster_log_types : contains(["api", "audit", "authenticator", "controllerManager", "scheduler"], x)]) && contains(var.cluster_log_types, "audit") && contains(var.cluster_log_types, "authenticator")
    error_message = "Use supported log types and retain audit and authenticator."
  }
}
variable "node_volume_size" {
  type        = number
  default     = 20
  description = "Encrypted gp3 root volume GiB per node."
  validation {
    condition     = var.node_volume_size >= 20 && var.node_volume_size <= 200 && floor(var.node_volume_size) == var.node_volume_size
    error_message = "Select a whole GiB size between 20 and 200."
  }
}
variable "worker_taints" {
  type        = list(object({ key = string, value = string, effect = string }))
  default     = []
  description = "Additional worker taints; the workload=ray isolation taint is always retained."
  validation {
    condition     = alltrue([for t in var.worker_taints : t.key != "workload" && contains(["NO_SCHEDULE", "PREFER_NO_SCHEDULE", "NO_EXECUTE"], t.effect)])
    error_message = "Do not override workload taint; use a supported EKS effect."
  }
}

variable "system_pool" {
  type        = object({ instance_types = list(string), desired_size = number, min_size = number, max_size = number, labels = optional(map(string), {}) })
  default     = { instance_types = ["m6g.large"], desired_size = 1, min_size = 1, max_size = 1 }
  description = "ARM64 system pool configuration; instance types must be compatible with AL2023 ARM64."
  validation {
    condition     = length(var.system_pool.instance_types) > 0 && var.system_pool.min_size >= 1 && var.system_pool.min_size <= var.system_pool.desired_size && var.system_pool.desired_size <= var.system_pool.max_size && alltrue([for n in [var.system_pool.min_size, var.system_pool.desired_size, var.system_pool.max_size] : floor(n) == n])
    error_message = "Use nonempty types and integer sizes with minimum <= desired <= maximum; retain required minimum."
  }
}

variable "workers_pool" {
  type        = object({ instance_types = list(string), desired_size = number, min_size = number, max_size = number, labels = optional(map(string), {}) })
  default     = { instance_types = ["m6g.large", "m7g.large"], desired_size = 1, min_size = 0, max_size = 2 }
  description = "ARM64 workers pool configuration; instance types must be compatible with AL2023 ARM64."
  validation {
    condition     = length(var.workers_pool.instance_types) > 0 && var.workers_pool.min_size >= 0 && var.workers_pool.min_size <= var.workers_pool.desired_size && var.workers_pool.desired_size <= var.workers_pool.max_size && alltrue([for n in [var.workers_pool.min_size, var.workers_pool.desired_size, var.workers_pool.max_size] : floor(n) == n])
    error_message = "Use nonempty types and integer sizes with minimum <= desired <= maximum; retain required minimum."
  }
}
