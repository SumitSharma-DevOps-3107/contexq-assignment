resource "terraform_data" "lease" {
  input = var.lease_expires_at
  lifecycle {
    precondition {
      condition     = try(timecmp(var.lease_expires_at, plantimestamp()) > 0 && timecmp(var.lease_expires_at, timeadd(plantimestamp(), "8h")) <= 0, false)
      error_message = "Lease expiry must be in the future and no more than eight hours from this plan."
    }
  }
}
data "archive_file" "lease" {
  type        = "zip"
  source_file = "${path.module}/lease_guard.py"
  output_path = "${path.module}/lease-guard.zip"
}
resource "aws_iam_role" "lease" {
  name = "${var.project}-lease-guard"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_cloudwatch_log_group" "lease" {
  name              = "/aws/lambda/${var.project}-lease-guard"
  retention_in_days = 3
}
resource "aws_iam_role_policy" "lease" {
  role = aws_iam_role.lease.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["eks:DescribeNodegroup", "eks:DeleteNodegroup"], Resource = [for group in ["system", "workers"] : "arn:aws:eks:${var.region}:${var.expected_account_id}:nodegroup/${var.project}/${group}/*"] },
    { Effect = "Allow", Action = ["eks:DescribeCluster", "eks:DeleteCluster"], Resource = "arn:aws:eks:${var.region}:${var.expected_account_id}:cluster/${var.project}" },
    { Effect = "Allow", Action = ["ec2:DescribeNatGateways"], Resource = "*" },
    { Effect = "Allow", Action = ["ec2:DeleteNatGateway"], Resource = "arn:aws:ec2:${var.region}:${var.expected_account_id}:natgateway/${module.network.nat_id}" },
    { Effect = "Allow", Action = ["ec2:ReleaseAddress"], Resource = "arn:aws:ec2:${var.region}:${var.expected_account_id}:elastic-ip/${module.network.eip_allocation_id}" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.lease.arn}:*" }
  ] })
}
resource "aws_lambda_function" "lease" {
  function_name    = "${var.project}-lease-guard"
  role             = aws_iam_role.lease.arn
  runtime          = "python3.12"
  handler          = "lease_guard.handler"
  filename         = data.archive_file.lease.output_path
  source_code_hash = data.archive_file.lease.output_base64sha256
  timeout          = 60
  memory_size      = 128
  environment {
    variables = { LEASE_CONFIG = jsonencode({
      expires_at        = terraform_data.lease.output
      cluster           = var.project, nat_id = module.network.nat_id
      eip_allocation_id = module.network.eip_allocation_id
    }) }
  }
  depends_on = [aws_iam_role_policy.lease]
}
resource "aws_cloudwatch_event_rule" "lease" {
  name                = "${var.project}-lease-guard"
  schedule_expression = "rate(15 minutes)"
}
resource "aws_cloudwatch_event_target" "lease" {
  rule = aws_cloudwatch_event_rule.lease.name
  arn  = aws_lambda_function.lease.arn
}
resource "aws_lambda_permission" "lease" {
  statement_id  = "AllowLeaseSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lease.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lease.arn
}
