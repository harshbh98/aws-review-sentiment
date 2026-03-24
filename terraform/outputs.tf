output "input_bucket_name" {
  description = "S3 bucket for uploading raw reviews"
  value       = aws_s3_bucket.reviews_input.bucket
}

output "output_bucket_name" {
  description = "S3 bucket where sentiment JSON results are saved"
  value       = aws_s3_bucket.reviews_output.bucket
}

output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = aws_lambda_function.sentiment.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function"
  value       = aws_lambda_function.sentiment.arn
}

output "athena_database" {
  description = "Athena database for querying sentiment results"
  value       = aws_athena_database.reviews.name
}

output "athena_workgroup" {
  description = "Athena workgroup name"
  value       = aws_athena_workgroup.reviews.name
}
