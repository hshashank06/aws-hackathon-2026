#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploys the reviewFunction Lambda, its IAM role, and the document-processing
    Step Functions Synchronous Express Workflow, then wires API Gateway routes.

.DESCRIPTION
    Resources created / updated:
      - IAM role  : ReviewFunctionRole  (S3, Textract, Comprehend, Comprehend Medical,
                                         Rekognition, Bedrock, Step Functions, DynamoDB)
      - Lambda    : reviewFunction       (Python 3.12, 512 MB, 5 min timeout)
      - Step Fn   : DocumentProcessingWorkflow  (EXPRESS, sync)
      - API GW    : new routes added to existing HealthcareAPI
                    POST   /reviews/presign
                    POST   /reviews/process-document
                    POST   /reviews
                    GET    /reviews
                    GET    /reviews/{reviewId}
                    PUT    /reviews/{reviewId}
                    DELETE /reviews/{reviewId}

.PREREQUISITES
    - AWS CLI v2 configured (aws configure)
    - reviewFunction source zipped at: aws/lambda/reviewFunction/reviewFunction.zip
      (run: Compress-Archive before executing this script)
    - Existing HTTP API (HealthcareAPI) already deployed via create-api-gateway.ps1

.USAGE
    .\create-review-infrastructure.ps1 `
        -Region eu-north-1 `
        -AccountId 123456789012 `
        -ApiId <your-api-id>
#>

param(
    [Parameter(Mandatory)][string] $Region,
    [string] $AccountId       = "",
    [Parameter(Mandatory)][string] $ApiId,

    [string] $FunctionName    = "reviewFunction",
    [string] $RoleName        = "ReviewFunctionRole",
    [string] $TableName       = "Review",
    [string] $S3Bucket        = "choco-warriors-db-synthetic-data",
    [string] $StateMachineName= "DocumentProcessingWorkflow",
    [string] $BedrockModelId  = "anthropic.claude-3-sonnet-20240229-v1:0",

    [string] $LambdaZipPath   = "$PSScriptRoot\lambda\reviewFunction\reviewFunction.zip",
    [string] $AslPath         = "$PSScriptRoot\step-functions\document-processing-state-machine.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Auto-detect AccountId
# ---------------------------------------------------------------------------
if (-not $AccountId) {
    Write-Host "Auto-detecting AWS Account ID..." -ForegroundColor Yellow
    $AccountId = aws sts get-caller-identity --query Account --output text --region $Region
    if ($LASTEXITCODE -ne 0 -or -not $AccountId) {
        Write-Host "ERROR: Could not determine AWS Account ID." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Account ID: $AccountId" -ForegroundColor Green
}

function Invoke-CLI {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "`n>>> $Description" -ForegroundColor Cyan
    $result = & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    return $result
}

function Get-LambdaArn([string]$Name) {
    return "arn:aws:lambda:${Region}:${AccountId}:function:${Name}"
}

# ---------------------------------------------------------------------------
# 1. Build deployment ZIP
# ---------------------------------------------------------------------------
Write-Host "`n>>> Building reviewFunction.zip" -ForegroundColor Cyan
$srcDir = "$PSScriptRoot\lambda\reviewFunction"
if (-not (Test-Path $LambdaZipPath)) {
    Push-Location $srcDir
    Compress-Archive -Path ".\*" -DestinationPath $LambdaZipPath -Force
    Pop-Location
    Write-Host "  Created: $LambdaZipPath" -ForegroundColor Green
} else {
    Write-Host "  ZIP already exists, re-packing..." -ForegroundColor Yellow
    Push-Location $srcDir
    Compress-Archive -Path ".\*" -DestinationPath $LambdaZipPath -Force -Update
    Pop-Location
}

# ---------------------------------------------------------------------------
# 2. Create IAM role + trust policy
# ---------------------------------------------------------------------------
$trustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": ["lambda.amazonaws.com", "states.amazonaws.com"] },
      "Action": "sts:AssumeRole"
    }
  ]
}
"@

$trustFile = [System.IO.Path]::GetTempFileName() + ".json"
$trustPolicy | Out-File -FilePath $trustFile -Encoding utf8 -Force

$roleJson = Invoke-CLI "Creating IAM role: $RoleName" {
    aws iam create-role `
        --role-name             $RoleName `
        --assume-role-policy-document "file://$trustFile" `
        --region                $Region `
        --output                json
}
$roleArn = ($roleJson | ConvertFrom-Json).Role.Arn
Write-Host "  Role ARN: $roleArn" -ForegroundColor Green

# Attach AWS-managed policies
$managedPolicies = @(
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AmazonTextractFullAccess",
    "arn:aws:iam::aws:policy/ComprehendFullAccess",
    "arn:aws:iam::aws:policy/AmazonRekognitionFullAccess",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
)

foreach ($policy in $managedPolicies) {
    Invoke-CLI "Attaching policy: $policy" {
        aws iam attach-role-policy `
            --role-name  $RoleName `
            --policy-arn $policy `
            --region     $Region
    } | Out-Null
}

# Inline policy for S3, ComprehendMedical, Bedrock, Step Functions
$inlinePolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Documents",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:HeadObject"],
      "Resource": "arn:aws:s3:::${S3Bucket}/*"
    },
    {
      "Sid": "ComprehendMedical",
      "Effect": "Allow",
      "Action": "comprehendmedical:*",
      "Resource": "*"
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:${Region}::foundation-model/*"
    },
    {
      "Sid": "StepFunctionsSync",
      "Effect": "Allow",
      "Action": ["states:StartSyncExecution", "states:StartExecution"],
      "Resource": "arn:aws:states:${Region}:${AccountId}:stateMachine:${StateMachineName}"
    },
    {
      "Sid": "PresignedUrls",
      "Effect": "Allow",
      "Action": "s3:GeneratePresignedUrl",
      "Resource": "arn:aws:s3:::${S3Bucket}/*"
    }
  ]
}
"@

$inlineFile = [System.IO.Path]::GetTempFileName() + ".json"
$inlinePolicy | Out-File -FilePath $inlineFile -Encoding utf8 -Force

Invoke-CLI "Attaching inline policy to $RoleName" {
    aws iam put-role-policy `
        --role-name         $RoleName `
        --policy-name       "ReviewFunctionInlinePolicy" `
        --policy-document   "file://$inlineFile" `
        --region            $Region
} | Out-Null

# IAM propagation delay
Write-Host "  Waiting 15s for IAM role to propagate..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# ---------------------------------------------------------------------------
# 3. Create the Lambda function
# ---------------------------------------------------------------------------
$lambdaJson = Invoke-CLI "Creating Lambda: $FunctionName" {
    aws lambda create-function `
        --function-name  $FunctionName `
        --runtime        python3.12 `
        --handler        lambda_function.lambda_handler `
        --role           $roleArn `
        --zip-file       "fileb://$LambdaZipPath" `
        --timeout        300 `
        --memory-size    512 `
        --environment    "Variables={TABLE_NAME=$TableName,S3_BUCKET=$S3Bucket,BEDROCK_MODEL_ID=$BedrockModelId,STEP_FUNCTION_ARN=PLACEHOLDER}" `
        --region         $Region `
        --output         json
}
$lambdaArn = ($lambdaJson | ConvertFrom-Json).FunctionArn
Write-Host "  Lambda ARN: $lambdaArn" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Create the Step Functions Synchronous Express Workflow
# ---------------------------------------------------------------------------
$aslDefinition = Get-Content $AslPath -Raw

# Inject the Lambda ARN as the processor ARN (used in all task states)
$aslWithArn = $aslDefinition -replace '"processorLambdaArn"', $lambdaArn

$aslTempFile = [System.IO.Path]::GetTempFileName() + ".json"
$aslWithArn | Out-File -FilePath $aslTempFile -Encoding utf8 -Force

$sfJson = Invoke-CLI "Creating Step Functions state machine: $StateMachineName" {
    aws stepfunctions create-state-machine `
        --name          $StateMachineName `
        --type          EXPRESS `
        --definition    "file://$aslTempFile" `
        --role-arn      $roleArn `
        --region        $Region `
        --output        json
}
$sfArn = ($sfJson | ConvertFrom-Json).stateMachineArn
Write-Host "  State Machine ARN: $sfArn" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 5. Update Lambda with the real STEP_FUNCTION_ARN
# ---------------------------------------------------------------------------
Invoke-CLI "Updating Lambda env with STEP_FUNCTION_ARN" {
    aws lambda update-function-configuration `
        --function-name  $FunctionName `
        --environment    "Variables={TABLE_NAME=$TableName,S3_BUCKET=$S3Bucket,BEDROCK_MODEL_ID=$BedrockModelId,STEP_FUNCTION_ARN=$sfArn}" `
        --region         $Region `
        --output         json
} | Out-Null

# ---------------------------------------------------------------------------
# 6. Wire API Gateway routes
# ---------------------------------------------------------------------------
$lambdaUri = "arn:aws:apigateway:${Region}:lambda:path/2015-03-31/functions/${lambdaArn}/invocations"

$intJson = Invoke-CLI "Creating API Gateway integration for $FunctionName" {
    aws apigatewayv2 create-integration `
        --api-id              $ApiId `
        --integration-type    AWS_PROXY `
        --integration-uri     $lambdaUri `
        --payload-format-version "2.0" `
        --region              $Region `
        --output              json
}
$intId = ($intJson | ConvertFrom-Json).IntegrationId
Write-Host "  Integration ID: $intId" -ForegroundColor Green

function New-Route([string]$Method, [string]$RouteKey) {
    $target = "integrations/$intId"
    Invoke-CLI "Route: $Method $RouteKey" {
        aws apigatewayv2 create-route `
            --api-id        $ApiId `
            --route-key     "$Method $RouteKey" `
            --target        $target `
            --region        $Region `
            --output        json
    } | Out-Null
}

New-Route "POST"   "/reviews/presign"
New-Route "POST"   "/reviews/process-document"
New-Route "POST"   "/reviews"
New-Route "GET"    "/reviews"
New-Route "GET"    "/reviews/{reviewId}"
New-Route "PUT"    "/reviews/{reviewId}"
New-Route "DELETE" "/reviews/{reviewId}"

# ---------------------------------------------------------------------------
# 7. Grant API Gateway permission to invoke the Lambda
# ---------------------------------------------------------------------------
$sourceArn  = "arn:aws:execute-api:${Region}:${AccountId}:${ApiId}/*/*"
$statementId = "apigw-invoke-$FunctionName-$(Get-Random -Maximum 9999)"

Invoke-CLI "Granting API Gateway invoke permission to $FunctionName" {
    aws lambda add-permission `
        --function-name $FunctionName `
        --statement-id  $statementId `
        --action        lambda:InvokeFunction `
        --principal     apigateway.amazonaws.com `
        --source-arn    $sourceArn `
        --region        $Region `
        --output        json
} | Out-Null

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Green
Write-Host " Review infrastructure setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " Lambda ARN      : $lambdaArn"
Write-Host " State Machine   : $sfArn"
Write-Host " Integration ID  : $intId"
Write-Host ""
Write-Host " New API endpoints:"
$apiBase = (aws apigatewayv2 get-api --api-id $ApiId --region $Region --output json | ConvertFrom-Json).ApiEndpoint
Write-Host "   POST   $apiBase/reviews/presign"
Write-Host "   POST   $apiBase/reviews/process-document"
Write-Host "   POST   $apiBase/reviews"
Write-Host "   GET    $apiBase/reviews"
Write-Host "   GET    $apiBase/reviews/{reviewId}"
Write-Host "   PUT    $apiBase/reviews/{reviewId}"
Write-Host "   DELETE $apiBase/reviews/{reviewId}"
Write-Host ""
Write-Host " Set this in your frontend .env:"
Write-Host "   VITE_API_BASE_URL=$apiBase" -ForegroundColor Yellow

# Cleanup temp files
Remove-Item $trustFile, $inlineFile, $aslTempFile -ErrorAction SilentlyContinue
