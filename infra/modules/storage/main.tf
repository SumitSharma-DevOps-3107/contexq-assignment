variable "name" { type = string }
variable "force_destroy" {
  type    = bool
  default = false
}
variable "expiring_prefixes" {
  type    = list(string)
  default = []
}

resource "aws_s3_bucket" "this" {
  bucket        = var.name
  force_destroy = var.force_destroy
}
resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyNonTLS", Effect = "Deny", Principal = "*", Action = "s3:*"
      Resource  = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}
resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  dynamic "rule" {
    for_each = toset(var.expiring_prefixes)
    content {
      id     = "expire-${replace(rule.value, "/", "-")}"
      status = "Enabled"
      filter { prefix = rule.value }
      expiration { days = 1 }
    }
  }
  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
  rule {
    id     = "expire-old-object-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 7 }
  }
}
output "name" { value = aws_s3_bucket.this.id }
output "arn" { value = aws_s3_bucket.this.arn }
