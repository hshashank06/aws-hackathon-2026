# PowerShell deployment script for Windows
# Deploy SearchLambda function to AWS

param(
    [string]$FunctionName = "SearchLambda",
    [string]$Region = "us-east-1"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deploying SearchLambda Function" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if AWS CLI is installed
try {
    $awsVersion = aws --version
    Write-Host "✓ AWS CLI found: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ AWS CLI not found. Please install AWS CLI first." -ForegroundColor Red
    exit 1
}

# Create deployment package
Write-Host ""
Write-Host "Creating deployment package..." -ForegroundColor Yellow

# Remove old zip if exists
if (Test-Path "function.zip") {
    Remove-Item "function.zip"
}

# Create zip file
Compress-Archive -Path "lambda_function.py" -DestinationPath "function.zip"

if (Test-Path "function.zip") {
    $zipSize = (Get-Item "function.zip").Length / 1KB
    Write-Host "✓ Package created: function.zip ($([math]::Round($zipSize, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to create deployment package" -ForegroundColor Red
    exit 1
}

# Deploy to AWS
Write-Host ""
Write-Host "Deploying to AWS Lambda..." -ForegroundColor Yellow
Write-Host "  Function: $FunctionName" -ForegroundColor Gray
Write-Host "  Region: $Region" -ForegroundColor Gray

try {
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file fileb://function.zip `
        --region $Region `
        --output json | ConvertFrom-Json | Format-List FunctionName, LastModified, CodeSize, Runtime
    
    Write-Host ""
    Write-Host "✓ Deployment successful!" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "✗ Deployment failed. Error:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# Cleanup
Write-Host ""
Write-Host "Cleaning up..." -ForegroundColor Yellow
Remove-Item "function.zip"
Write-Host "✓ Cleanup complete" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Verify environment variables in Lambda console" -ForegroundColor White
Write-Host "2. Check IAM permissions for DynamoDB and Lambda invoke" -ForegroundColor White
Write-Host "3. Test with: aws lambda invoke --function-name $FunctionName --payload file://test-events/test-search-initial.json response.json --region $Region" -ForegroundColor White
Write-Host ""
