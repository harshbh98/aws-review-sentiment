# ============================================================
# main.tf  –  AWS Customer Review Sentiment Analysis Pipeline
# ============================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -------------------------------------------------------
# S3 – Input bucket (raw customer reviews)
# -------------------------------------------------------
resource "aws_s3_bucket" "reviews_input" {
  bucket        = "${var.project_name}-reviews-raw-${var.environment}"
  force_destroy = var.force_destroy_buckets

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "reviews_input" {
  bucket = aws_s3_bucket.reviews_input.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reviews_input" {
  bucket = aws_s3_bucket.reviews_input.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "reviews_input" {
  bucket                  = aws_s3_bucket.reviews_input.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -------------------------------------------------------
# S3 – Output bucket (sentiment results)
# -------------------------------------------------------
resource "aws_s3_bucket" "reviews_output" {
  bucket        = "${var.project_name}-reviews-sentiment-${var.environment}"
  force_destroy = var.force_destroy_buckets

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "reviews_output" {
  bucket = aws_s3_bucket.reviews_output.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reviews_output" {
  bucket = aws_s3_bucket.reviews_output.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "reviews_output" {
  bucket                  = aws_s3_bucket.reviews_output.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -------------------------------------------------------
# IAM – Lambda execution role
# -------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${var.project_name}-lambda-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "lambda_permissions" {
  # CloudWatch Logs
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
  # Read from input bucket
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.reviews_input.arn}/*"]
  }
  # Write to output bucket
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.reviews_output.arn}/*"]
  }
  # Amazon Comprehend
  statement {
    actions   = ["comprehend:DetectSentiment"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name   = "${var.project_name}-lambda-policy-${var.environment}"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# -------------------------------------------------------
# Lambda – package & deploy
# -------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/../dist/lambda_function.zip"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-sentiment-${var.environment}"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_lambda_function" "sentiment" {
  function_name    = "${var.project_name}-sentiment-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      OUTPUT_BUCKET  = aws_s3_bucket.reviews_output.bucket
      OUTPUT_PREFIX  = "sentiment-results/"
      LANGUAGE_CODE  = var.language_code
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
  tags       = local.common_tags
}

# -------------------------------------------------------
# S3 Event Notification → Lambda
# -------------------------------------------------------
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sentiment.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.reviews_input.arn
}

resource "aws_s3_bucket_notification" "trigger" {
  bucket = aws_s3_bucket.reviews_input.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.sentiment.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reviews/"
    filter_suffix       = ".txt"
  }

  depends_on = [aws_lambda_permission.allow_s3]
}

# -------------------------------------------------------
# Athena – database & workgroup
# -------------------------------------------------------
resource "aws_athena_database" "reviews" {
  name   = replace("${var.project_name}_${var.environment}", "-", "_")
  bucket = aws_s3_bucket.reviews_output.bucket
}

resource "aws_s3_bucket" "athena_results" {
  bucket        = "${var.project_name}-athena-results-${var.environment}"
  force_destroy = var.force_destroy_buckets
  tags          = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_athena_workgroup" "reviews" {
  name = "${var.project_name}-workgroup-${var.environment}"

  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/query-results/"
    }
  }

  tags = local.common_tags
}

# -------------------------------------------------------
# Locals
# -------------------------------------------------------
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
