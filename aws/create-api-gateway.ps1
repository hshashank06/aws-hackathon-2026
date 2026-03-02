#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Creates an AWS HTTP API (API Gateway v2) with Lambda integrations and routes
    for all 6 microservice Lambda functions.

.DESCRIPTION
    Resources created:
      - 1 HTTP API
      - 6 Lambda integrations (one per function)
      - 30 routes (5 CRUD routes per function)
      - Lambda resource-based permissions so API Gateway can invoke each function
      - 1 default auto-deployed stage ($default)

.PREREQUISITES
    - AWS CLI v2 installed and configured (aws configure)
    - All 6 Lambda functions already deployed

.USAGE
    .\create-api-gateway.ps1 -Region eu-north-1 -AccountId 123456789012
#>

param(
    [Parameter(Mandatory)][string] $Region,
    [string] $AccountId = "",  # auto-detected from AWS STS if not provided

    # Override function names if they differ from defaults
    [string] $CustomerFn         = "customerFunction",
    [string] $DepartmentFn       = "departmentFunction",
    [string] $DoctorFn           = "doctorFunction",
    [string] $HospitalFn         = "hospitalFunction",
    [string] $InsuranceCompanyFn = "insuranceCompanyFunction",
    [string] $InsurancePolicyFn  = "insurancePolicyFunction",
    [string] $ReviewFn            = "reviewFunction",

    [string] $ApiName            = "HealthcareAPI",
    [string] $StageName          = '$default'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Auto-detect AccountId if not provided
# ---------------------------------------------------------------------------
if (-not $AccountId) {
    Write-Host "Auto-detecting AWS Account ID..." -ForegroundColor Yellow
    $AccountId = aws sts get-caller-identity --query Account --output text --region $Region
    if ($LASTEXITCODE -ne 0 -or -not $AccountId) {
        Write-Host "ERROR: Could not determine AWS Account ID. Run 'aws configure' or pass -AccountId explicitly." -ForegroundColor Red
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

# ---------------------------------------------------------------------------
# Helper: build Lambda ARN
# ---------------------------------------------------------------------------
function Get-LambdaArn([string]$FunctionName) {
    return "arn:aws:lambda:${Region}:${AccountId}:function:${FunctionName}"
}

# ---------------------------------------------------------------------------
# 1. Create HTTP API
# ---------------------------------------------------------------------------
$apiJson = Invoke-CLI "Creating HTTP API: $ApiName" {
    aws apigatewayv2 create-api `
        --name            $ApiName `
        --protocol-type   HTTP `
        --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,AllowHeaders=Content-Type,Authorization" `
        --region          $Region `
        --output          json
}

$api      = $apiJson | ConvertFrom-Json
$ApiId    = $api.ApiId
$ApiEndpoint = $api.ApiEndpoint
Write-Host "  API ID       : $ApiId"
Write-Host "  API Endpoint : $ApiEndpoint" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. Create Lambda integrations (one per function)
# ---------------------------------------------------------------------------
function New-LambdaIntegration([string]$FunctionName) {
    $arn = Get-LambdaArn $FunctionName
    $uri = "arn:aws:apigateway:${Region}:lambda:path/2015-03-31/functions/${arn}/invocations"

    $intJson = Invoke-CLI "Creating integration for $FunctionName" {
        aws apigatewayv2 create-integration `
            --api-id              $ApiId `
            --integration-type    AWS_PROXY `
            --integration-uri     $uri `
            --payload-format-version "2.0" `
            --region              $Region `
            --output              json
    }
    return ($intJson | ConvertFrom-Json).IntegrationId
}

$intCustomer         = New-LambdaIntegration $CustomerFn
$intDepartment       = New-LambdaIntegration $DepartmentFn
$intDoctor           = New-LambdaIntegration $DoctorFn
$intHospital         = New-LambdaIntegration $HospitalFn
$intInsuranceCompany = New-LambdaIntegration $InsuranceCompanyFn
$intInsurancePolicy  = New-LambdaIntegration $InsurancePolicyFn
$intReview           = New-LambdaIntegration $ReviewFn

Write-Host "`nIntegration IDs:" -ForegroundColor Yellow
Write-Host "  Customer         : $intCustomer"
Write-Host "  Department       : $intDepartment"
Write-Host "  Doctor           : $intDoctor"
Write-Host "  Hospital         : $intHospital"
Write-Host "  InsuranceCompany : $intInsuranceCompany"
Write-Host "  InsurancePolicy  : $intInsurancePolicy"
Write-Host "  Review           : $intReview"

# ---------------------------------------------------------------------------
# 3. Create routes
# ---------------------------------------------------------------------------
function New-Route([string]$Method, [string]$RouteKey, [string]$IntegrationId) {
    $target = "integrations/$IntegrationId"
    Invoke-CLI "Route: $Method $RouteKey" {
        aws apigatewayv2 create-route `
            --api-id        $ApiId `
            --route-key     "$Method $RouteKey" `
            --target        $target `
            --region        $Region `
            --output        json
    } | Out-Null
}

# --- Customers ---
New-Route "POST"   "/customers"               $intCustomer
New-Route "GET"    "/customers"               $intCustomer
New-Route "GET"    "/customers/{customerId}"  $intCustomer
New-Route "PUT"    "/customers/{customerId}"  $intCustomer
New-Route "DELETE" "/customers/{customerId}"  $intCustomer

# --- Departments ---
New-Route "POST"   "/departments"                    $intDepartment
New-Route "GET"    "/departments"                    $intDepartment
New-Route "GET"    "/departments/{departmentId}"     $intDepartment
New-Route "PUT"    "/departments/{departmentId}"     $intDepartment
New-Route "DELETE" "/departments/{departmentId}"     $intDepartment

# --- Doctors ---
New-Route "POST"   "/doctors"               $intDoctor
New-Route "GET"    "/doctors"               $intDoctor
New-Route "GET"    "/doctors/{doctorId}"    $intDoctor
New-Route "PUT"    "/doctors/{doctorId}"    $intDoctor
New-Route "DELETE" "/doctors/{doctorId}"    $intDoctor

# --- Hospitals ---
New-Route "POST"   "/hospitals"               $intHospital
New-Route "GET"    "/hospitals"               $intHospital
New-Route "GET"    "/hospitals/{hospitalId}"  $intHospital
New-Route "PUT"    "/hospitals/{hospitalId}"  $intHospital
New-Route "DELETE" "/hospitals/{hospitalId}"  $intHospital

# --- Insurance Companies ---
New-Route "POST"   "/insurance-companies"                          $intInsuranceCompany
New-Route "GET"    "/insurance-companies"                          $intInsuranceCompany
New-Route "GET"    "/insurance-companies/{insuranceCompanyId}"     $intInsuranceCompany
New-Route "PUT"    "/insurance-companies/{insuranceCompanyId}"     $intInsuranceCompany
New-Route "DELETE" "/insurance-companies/{insuranceCompanyId}"     $intInsuranceCompany

# --- Insurance Policies ---
New-Route "POST"   "/insurance-policies"               $intInsurancePolicy
New-Route "GET"    "/insurance-policies"               $intInsurancePolicy
New-Route "GET"    "/insurance-policies/{policyId}"    $intInsurancePolicy
New-Route "PUT"    "/insurance-policies/{policyId}"    $intInsurancePolicy
New-Route "DELETE" "/insurance-policies/{policyId}"    $intInsurancePolicy

# --- Reviews ---
New-Route "POST"   "/reviews/presign-upload"           $intReview
New-Route "POST"   "/reviews/process-document"         $intReview
New-Route "POST"   "/reviews"                          $intReview
New-Route "GET"    "/reviews"                          $intReview
New-Route "GET"    "/reviews/{reviewId}"               $intReview
New-Route "PUT"    "/reviews/{reviewId}"               $intReview
New-Route "DELETE" "/reviews/{reviewId}"               $intReview

# ---------------------------------------------------------------------------
# 4. Create auto-deployed stage
# ---------------------------------------------------------------------------
Invoke-CLI "Creating stage: $StageName" {
    aws apigatewayv2 create-stage `
        --api-id        $ApiId `
        --stage-name    $StageName `
        --auto-deploy `
        --region        $Region `
        --output        json
} | Out-Null

# ---------------------------------------------------------------------------
# 5. Grant API Gateway permission to invoke each Lambda function
# ---------------------------------------------------------------------------
function Add-LambdaPermission([string]$FunctionName) {
    $sourceArn = "arn:aws:execute-api:${Region}:${AccountId}:${ApiId}/*/*"
    $statementId = "apigw-invoke-$FunctionName-$(Get-Random -Maximum 9999)"

    Invoke-CLI "Lambda invoke permission: $FunctionName" {
        aws lambda add-permission `
            --function-name $FunctionName `
            --statement-id  $statementId `
            --action        lambda:InvokeFunction `
            --principal     apigateway.amazonaws.com `
            --source-arn    $sourceArn `
            --region        $Region `
            --output        json
    } | Out-Null
}

Add-LambdaPermission $CustomerFn
Add-LambdaPermission $DepartmentFn
Add-LambdaPermission $DoctorFn
Add-LambdaPermission $HospitalFn
Add-LambdaPermission $InsuranceCompanyFn
Add-LambdaPermission $InsurancePolicyFn
Add-LambdaPermission $ReviewFn

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Green
Write-Host " API Gateway setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " API ID       : $ApiId"
Write-Host " Base URL     : $ApiEndpoint" -ForegroundColor Green
Write-Host ""
Write-Host " Sample endpoints:"
Write-Host "   GET  $ApiEndpoint/customers"
Write-Host "   POST $ApiEndpoint/customers"
Write-Host "   GET  $ApiEndpoint/customers/{customerId}"
Write-Host "   PUT  $ApiEndpoint/customers/{customerId}"
Write-Host "   DELETE $ApiEndpoint/customers/{customerId}"
Write-Host ""
Write-Host "   GET  $ApiEndpoint/departments"
Write-Host "   GET  $ApiEndpoint/doctors"
Write-Host "   GET  $ApiEndpoint/hospitals"
Write-Host "   GET  $ApiEndpoint/insurance-companies"
Write-Host "   GET  $ApiEndpoint/insurance-policies"
Write-Host "   POST $ApiEndpoint/reviews/presign-upload"
Write-Host "   POST $ApiEndpoint/reviews/process-document"
Write-Host "   GET  $ApiEndpoint/reviews"
Write-Host "   GET  $ApiEndpoint/reviews/{reviewId}"
