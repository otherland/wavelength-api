terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "principal-task"
}

# where users live
resource "aws_dynamodb_table" "users" {
  name         = "${var.project_name}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"

  attribute {
    name = "userId"
    type = "S"
  }
}

# where subscriptions live, with a secondary index so we can look up by userId
resource "aws_dynamodb_table" "subscriptions" {
  name         = "${var.project_name}-subscriptions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "subscriptionId"

  attribute {
    name = "subscriptionId"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  global_secondary_index {
    name            = "userId-index"
    hash_key        = "userId"
    projection_type = "ALL"
  }
}

# where report configs live (the extensibility bit)
resource "aws_dynamodb_table" "report_definitions" {
  name         = "${var.project_name}-report-definitions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "reportId"

  attribute {
    name = "reportId"
    type = "S"
  }
}

# zips handler.py so Lambda can accept it
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../src/handler.py"
  output_path = "${path.module}/lambda.zip"
}

# the actual function that runs our Python code
resource "aws_lambda_function" "api" {
  function_name    = "${var.project_name}-api"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256 # without this, Terraform won't update the Lambda when handler.py changes
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 10
  role             = aws_iam_role.lambda.arn

  environment { # pass the table names to the Lambda as env vars, so handler.py can reference them without hardcoding
    variables = {
      USERS_TABLE              = aws_dynamodb_table.users.name
      SUBSCRIPTIONS_TABLE      = aws_dynamodb_table.subscriptions.name
      REPORT_DEFINITIONS_TABLE = aws_dynamodb_table.report_definitions.name
    }
  }
}

# identity the Lambda runs as
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# what the Lambda is allowed to do (DynamoDB + logs, nothing else)
# least privilege is important - don't give the Lambda more permissions than it needs
resource "aws_iam_role_policy" "lambda_dynamo" {
  name = "${var.project_name}-lambda-dynamo"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.users.arn,
          aws_dynamodb_table.subscriptions.arn,
          "${aws_dynamodb_table.subscriptions.arn}/index/*",
          aws_dynamodb_table.report_definitions.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# the public URL that receives HTTP requests
resource "aws_api_gateway_rest_api" "main" {
  name = "${var.project_name}-api"
}

# catch-all path, every request goes to Lambda
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "{proxy+}" # if we wanted throttling or auth on specific endpoints we could define them here instead of a catch-all, but this is simpler for now
}

# accept any HTTP method (GET, POST, PUT, DELETE)
resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

# wire the method to Lambda (pass the whole request through)
resource "aws_api_gateway_integration" "proxy" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}

# publish the API config (redeploys when resources change)
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  depends_on = [aws_api_gateway_integration.proxy]

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_integration.proxy.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# version label on the URL (/v1)
resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "v1"
}

# lets API Gateway actually call the Lambda
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}
