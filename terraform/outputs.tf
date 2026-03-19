output "api_url" {
  value = aws_api_gateway_stage.main.invoke_url
  description = "The URL of the API Gateway endpoint for the Lambda function"
}
