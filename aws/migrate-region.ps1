#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Migrates all Lambda functions, the Step Functions state machine, and the
    API Gateway from one AWS region to another (default: eu-north-1 -> us-east-1).

.DESCRIPTION
    For each Lambda function the script will:
      1. Download the current deployment package from the source region.
      2. Replicate the function configuration (runtime, handler, memory, timeout,
         environment variables, description) to the target region.
      3. Upload the deployment package to the new function.

    After functions are ready it will:
      4. Create the Step Functions state machine in the target region.
      5. Optionally re-create the API Gateway by calling create-api-gateway.ps1.

    NOTE: IAM execution roles are global so the same role ARN is reused.
    Environment variables that contain region-specific ARNs are automatically
    rewritten (e.g. every occurrence of the source region string is replaced
    with the target region string).

.PARAMETER SourceRegion
    AWS region where the functions currently live (default: eu-north-1).

.PARAMETER TargetRegion
    AWS region to migrate to (default: us-east-1).

.PARAMETER AccountId
    AWS account ID. Auto-detected from STS if omitted.

.PARAMETER StepFunctionName
    Name of the existing Step Functions state machine in the source region.
    Defaults to "DocumentProcessingWorkflow".

.PARAMETER StepFunctionRoleArn
    IAM role ARN for the Step Functions state machine in the target region.
    If omitted the role is copied from the source state machine (global ARN,
    works across regions without changes).

.PARAMETER SkipApiGateway
    Switch: skip re-creating the API Gateway after migrating functions.

.PARAMETER UseLocalStateMachine
    Switch: use the local file aws/step-functions/document-processing-state-machine.json
    instead of downloading the definition from the source region.

.EXAMPLE
    # Dry-run -- print what would happen without making changes:
    .\migrate-region.ps1 -WhatIf

    # Full migration from eu-north-1 to us-east-1:
    .\migrate-region.ps1

    # Custom regions:
    .\migrate-region.ps1 -SourceRegion ap-southeast-1 -TargetRegion us-west-2
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $SourceRegion        = "eu-north-1",
    [string] $TargetRegion        = "us-east-1",
    [string] $AccountId           = "",
    [string] $StepFunctionName    = "DocumentProcessingWorkflow",
    [string] $StepFunctionRoleArn = "",
    [switch] $SkipApiGateway,
    [switch] $UseLocalStateMachine,
    # S3: list of "sourceBucketName=targetBucketName" mappings.
    # If omitted, all buckets whose home region matches $SourceRegion are discovered
    # automatically and each gets a target name of "<original>-us" (or you can
    # override with explicit pairs like "my-bucket=my-bucket-us-east-1").
    [string[]] $S3BucketMappings  = @(),
    [switch]   $SkipS3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Colour helpers ------------------------------------------------------------------
function Write-Step  ([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok    ([string]$msg) { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Warn  ([string]$msg) { Write-Host "    WARN $msg" -ForegroundColor Yellow }
function Write-Fail  ([string]$msg) { Write-Host "    FAIL $msg" -ForegroundColor Red; exit 1 }

# -- Auto-detect account ID ----------------------------------------------------------
if (-not $AccountId) {
    Write-Step "Auto-detecting AWS Account ID"
    $AccountId = aws sts get-caller-identity --query Account --output text 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $AccountId) { Write-Fail "Cannot detect account ID. Run 'aws configure'." }
    Write-Ok "Account ID: $AccountId"
}

# -- Function names ------------------------------------------------------------------
$FunctionNames = @(
    "customerFunction",
    "departmentFunction",
    "doctorFunction",
    "hospitalFunction",
    "insuranceCompanyFunction",
    "insurancePolicyFunction",
    "reviewFunction",
    "InvokeFlow",
    "web-search-tools-zsjfc",
    "hospital-search-tools-gu11y"
)

# -- Temp directory for downloaded zips ----------------------------------------
$TempDir = Join-Path $env:TEMP "lambda-migration-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
Write-Ok "Temp directory: $TempDir"

# =============================================================================
# PHASE 1 -- Migrate Lambda Functions
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Magenta
Write-Host " PHASE 1 -- Lambda Functions  ($SourceRegion -> $TargetRegion)" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta

foreach ($fnName in $FunctionNames) {

    Write-Step "Processing: $fnName"

    # 1a. Fetch configuration from source region
    Write-Host "    Fetching config from $SourceRegion..."
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $configJson = aws lambda get-function-configuration `
        --function-name $fnName `
        --region        $SourceRegion `
        --output        json 2>&1
    $fetchOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevPref

    if (-not $fetchOk) {
        Write-Warn "Function '$fnName' not found in $SourceRegion -- skipping."
        continue
    }

    $config = $configJson | ConvertFrom-Json

    # 1b. Download deployment package
    $urlJson  = aws lambda get-function `
        --function-name $fnName `
        --region        $SourceRegion `
        --query         "Code.Location" `
        --output        text
    $zipPath  = Join-Path $TempDir "$fnName.zip"

    Write-Host "    Downloading deployment package..."
    if ($PSCmdlet.ShouldProcess($fnName, "Download zip from $SourceRegion")) {
        Invoke-WebRequest -Uri $urlJson -OutFile $zipPath -UseBasicParsing
        $sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
        Write-Ok "Downloaded ${sizeMB} MB"
    }

    # 1c. Rewrite region-specific environment variables
    $envVars = if ($config.PSObject.Properties['Environment'] -and $config.Environment.PSObject.Properties['Variables']) { $config.Environment.Variables } else { $null }
    $envArgs = @()
    if ($envVars) {
        $rewritten = @{}
        foreach ($key in $envVars.PSObject.Properties.Name) {
            $val = $envVars.$key -replace [regex]::Escape($SourceRegion), $TargetRegion
            $rewritten[$key] = $val
        }
        # Flatten to KEY=VALUE,KEY2=VALUE2 format required by CLI
        $envStr  = ($rewritten.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ","
        $envArgs = @("--environment", "Variables={$envStr}")
    }

    # 1d. Create or update function in target region
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $null = aws lambda get-function-configuration `
        --function-name $fnName `
        --region        $TargetRegion `
        --output        json 2>&1
    $functionExists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevPref

    if ($functionExists) {
        # Function already exists -- update code then config
        Write-Host "    Function exists in $TargetRegion -- updating code & config..."

        if ($PSCmdlet.ShouldProcess($fnName, "Update function code in $TargetRegion")) {
            aws lambda update-function-code `
                --function-name $fnName `
                --zip-file      "fileb://$zipPath" `
                --region        $TargetRegion `
                --no-cli-pager | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-Fail "update-function-code failed for $fnName" }
        }

        # Wait for update to propagate before patching config
        Start-Sleep -Seconds 3

        if ($PSCmdlet.ShouldProcess($fnName, "Update function configuration in $TargetRegion")) {
            $updateArgs = @(
                "lambda", "update-function-configuration",
                "--function-name", $fnName,
                "--region",        $TargetRegion,
                "--runtime",       $config.Runtime,
                "--handler",       $config.Handler,
                "--timeout",       $config.Timeout,
                "--memory-size",   $config.MemorySize,
                "--no-cli-pager"
            )
            $desc = if ($config.PSObject.Properties['Description']) { $config.Description } else { $null }
            if ($desc)    { $updateArgs += @("--description", $desc) }
            if ($envArgs) { $updateArgs += $envArgs }
            & aws @updateArgs | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-Fail "update-function-configuration failed for $fnName" }
        }

    } else {
        # Function does not exist -- create it
        Write-Host "    Creating function in $TargetRegion..."

        if ($PSCmdlet.ShouldProcess($fnName, "Create function in $TargetRegion")) {
            $createArgs = @(
                "lambda", "create-function",
                "--function-name", $fnName,
                "--region",        $TargetRegion,
                "--runtime",       $config.Runtime,
                "--handler",       $config.Handler,
                "--role",          $config.Role,
                "--zip-file",      "fileb://$zipPath",
                "--timeout",       $config.Timeout,
                "--memory-size",   $config.MemorySize,
                "--no-cli-pager"
            )
            $desc = if ($config.PSObject.Properties['Description']) { $config.Description } else { $null }
            if ($desc)    { $createArgs += @("--description", $desc) }
            if ($envArgs) { $createArgs += $envArgs }
            & aws @createArgs | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-Fail "create-function failed for $fnName" }
        }
    }

    Write-Ok "$fnName ready in $TargetRegion"
}

# =============================================================================
# PHASE 2 -- Step Functions State Machine
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Magenta
Write-Host " PHASE 2 -- Step Functions State Machine" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalSMPath = Join-Path $ScriptRoot "step-functions\document-processing-state-machine.json"

if ($true) {

    if ($UseLocalStateMachine) {
        Write-Step "Using local state machine definition: $LocalSMPath"
        $smDefinition = Get-Content $LocalSMPath -Raw
        $smRoleArn    = $StepFunctionRoleArn
    } else {
        Write-Step "Fetching state machine '$StepFunctionName' from $SourceRegion"

        # Try to find the state machine ARN in the source region
        $smArn = aws stepfunctions list-state-machines `
            --region $SourceRegion `
            --query  "stateMachines[?name=='$StepFunctionName'].stateMachineArn | [0]" `
            --output text 2>$null

        if ($LASTEXITCODE -ne 0 -or $smArn -eq "None" -or -not $smArn) {
            Write-Warn "State machine '$StepFunctionName' not found in $SourceRegion -- falling back to local file."
            Write-Warn "Falling back to local file: $LocalSMPath"
            $smDefinition = Get-Content $LocalSMPath -Raw
            $smRoleArn    = $StepFunctionRoleArn
        } else {
            $smDetails    = aws stepfunctions describe-state-machine `
                --state-machine-arn $smArn `
                --region            $SourceRegion `
                --output            json | ConvertFrom-Json
            $smDefinition = $smDetails.definition
            $smRoleArn    = if ($StepFunctionRoleArn) { $StepFunctionRoleArn } else { $smDetails.roleArn }
        }
    }

    # Rewrite any source-region ARNs inside the definition
    $smDefinition = $smDefinition -replace [regex]::Escape($SourceRegion), $TargetRegion

    # Check if state machine already exists in target region
    $existingSMArn = aws stepfunctions list-state-machines `
        --region $TargetRegion `
        --query  "stateMachines[?name=='$StepFunctionName'].stateMachineArn | [0]" `
        --output text 2>$null

    $defFile = Join-Path $TempDir "sm-definition.json"
    [System.IO.File]::WriteAllText($defFile, $smDefinition, [System.Text.UTF8Encoding]::new($false))

    if ($existingSMArn -and $existingSMArn -ne "None") {
        Write-Host "    State machine already exists in $TargetRegion -- updating definition..."
        if ($PSCmdlet.ShouldProcess($StepFunctionName, "Update state machine in $TargetRegion")) {
            aws stepfunctions update-state-machine `
                --state-machine-arn $existingSMArn `
                --definition        "file://$defFile" `
                --region            $TargetRegion `
                --no-cli-pager | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-Fail "update-state-machine failed" }
        }
    } else {
        Write-Host "    Creating state machine in $TargetRegion..."

        if (-not $smRoleArn) {
            Write-Fail "No IAM role ARN for Step Functions. Pass -StepFunctionRoleArn or ensure the source machine exists."
        }

        if ($PSCmdlet.ShouldProcess($StepFunctionName, "Create state machine in $TargetRegion")) {
            aws stepfunctions create-state-machine `
                --name       $StepFunctionName `
                --definition "file://$defFile" `
                --role-arn   $smRoleArn `
                --type       STANDARD `
                --region     $TargetRegion `
                --no-cli-pager | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-Fail "create-state-machine failed" }
        }
    }

    Write-Ok "Step Functions state machine '$StepFunctionName' ready in $TargetRegion"
}

# =============================================================================
# PHASE 3 -- API Gateway (optional)
# =============================================================================
if (-not $SkipApiGateway) {
    Write-Host "`n============================================================" -ForegroundColor Magenta
    Write-Host " PHASE 3 -- API Gateway (HTTP API)" -ForegroundColor Magenta
    Write-Host "============================================================" -ForegroundColor Magenta

    $ApiGwScript = Join-Path $ScriptRoot "create-api-gateway.ps1"
    if (Test-Path $ApiGwScript) {
        Write-Step "Running create-api-gateway.ps1 for $TargetRegion"
        if ($PSCmdlet.ShouldProcess("API Gateway", "Create in $TargetRegion")) {
            & $ApiGwScript -Region $TargetRegion -AccountId $AccountId
            if ($LASTEXITCODE -ne 0) { Write-Fail "API Gateway creation failed" }
        }
        Write-Ok "API Gateway created in $TargetRegion"
    } else {
        Write-Warn "create-api-gateway.ps1 not found -- skipping API Gateway step."
    }
}

# =============================================================================
# PHASE 4 -- S3 Buckets
# =============================================================================
if (-not $SkipS3) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Magenta
    Write-Host " PHASE 4 -- S3 Buckets  ($SourceRegion -> $TargetRegion)" -ForegroundColor Magenta
    Write-Host "============================================================" -ForegroundColor Magenta

    # Build mapping hashtable: sourceName -> targetName
    $bucketMap = [ordered]@{}

    if ($S3BucketMappings.Count -gt 0) {
        foreach ($pair in $S3BucketMappings) {
            $parts = $pair -split "=", 2
            if ($parts.Count -eq 2) {
                $bucketMap[$parts[0].Trim()] = $parts[1].Trim()
            } else {
                # No target name given -- auto-derive
                $bucketMap[$parts[0].Trim()] = "$($parts[0].Trim())-us"
            }
        }
    } else {
        # Auto-discover all buckets whose home region is $SourceRegion
        Write-Step "Discovering buckets in $SourceRegion..."
        $allBuckets = aws s3api list-buckets --query "Buckets[].Name" --output text 2>$null
        if ($LASTEXITCODE -eq 0 -and $allBuckets) {
            foreach ($b in ($allBuckets -split "\s+")) {
                $b = $b.Trim()
                if (-not $b) { continue }
                $prevPref = $ErrorActionPreference; $ErrorActionPreference = "Continue"
                $bRegion = aws s3api get-bucket-location --bucket $b --query "LocationConstraint" --output text 2>$null
                $ErrorActionPreference = $prevPref
                # us-east-1 returns "None" for LocationConstraint
                if ($bRegion -eq "None") { $bRegion = "us-east-1" }
                if ($bRegion -eq $SourceRegion) {
                    $targetName = "$b-us"
                    $bucketMap[$b] = $targetName
                    Write-Ok "Found: $b  ->  $targetName"
                }
            }
        }
    }

    if ($bucketMap.Count -eq 0) {
        Write-Warn "No buckets found in $SourceRegion -- skipping S3 phase."
    }

    foreach ($srcBucket in $bucketMap.Keys) {
        $dstBucket = $bucketMap[$srcBucket]
        Write-Step "Migrating bucket: $srcBucket  ->  $dstBucket"

        # --- Create target bucket ---
        $prevPref = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $null = aws s3api head-bucket --bucket $dstBucket 2>&1
        $bucketExists = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $prevPref

        if ($bucketExists) {
            Write-Host "    Bucket '$dstBucket' already exists -- skipping creation."
        } else {
            Write-Host "    Creating bucket '$dstBucket' in $TargetRegion..."
            if ($PSCmdlet.ShouldProcess($dstBucket, "Create S3 bucket in $TargetRegion")) {
                if ($TargetRegion -eq "us-east-1") {
                    # us-east-1 must NOT pass --create-bucket-configuration
                    aws s3api create-bucket `
                        --bucket $dstBucket `
                        --region $TargetRegion `
                        --no-cli-pager | Out-Null
                } else {
                    aws s3api create-bucket `
                        --bucket $dstBucket `
                        --region $TargetRegion `
                        --create-bucket-configuration "LocationConstraint=$TargetRegion" `
                        --no-cli-pager | Out-Null
                }
                if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to create bucket '$dstBucket'" }
                Write-Ok "Bucket '$dstBucket' created"
            }
        }

        # --- Copy versioning setting ---
        $prevPref = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $versioningStatus = aws s3api get-bucket-versioning `
            --bucket $srcBucket --query "Status" --output text 2>$null
        $ErrorActionPreference = $prevPref
        if ($versioningStatus -eq "Enabled") {
            Write-Host "    Enabling versioning on '$dstBucket'..."
            if ($PSCmdlet.ShouldProcess($dstBucket, "Enable versioning")) {
                aws s3api put-bucket-versioning `
                    --bucket $dstBucket `
                    --versioning-configuration Status=Enabled `
                    --no-cli-pager | Out-Null
            }
        }

        # --- Sync objects ---
        Write-Host "    Syncing objects: s3://$srcBucket  ->  s3://$dstBucket ..."
        if ($PSCmdlet.ShouldProcess($dstBucket, "Sync from $srcBucket")) {
            aws s3 sync "s3://$srcBucket" "s3://$dstBucket" --no-progress
            if ($LASTEXITCODE -ne 0) { Write-Fail "s3 sync failed for $srcBucket -> $dstBucket" }
        }
        Write-Ok "Sync complete for $srcBucket -> $dstBucket"

        # --- Update Lambda env vars that reference the old bucket name ---
        # Also explicitly sets S3_BUCKET on functions that rely on a hardcoded
        # default of the old bucket name (env var may be absent).
        Write-Host "    Updating Lambda env vars that reference '$srcBucket'..."
        $prevPref = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $allFnsJson = aws lambda list-functions `
            --region $TargetRegion --output json 2>$null | ConvertFrom-Json
        $ErrorActionPreference = $prevPref
        if ($allFnsJson) {
            foreach ($fn in $allFnsJson.Functions) {
                $needsUpdate = $false
                $updated = @{}

                # Collect existing env vars (if any)
                if ($fn.PSObject.Properties['Environment'] -and $fn.Environment.PSObject.Properties['Variables'] -and $fn.Environment.Variables) {
                    foreach ($key in $fn.Environment.Variables.PSObject.Properties.Name) {
                        $val = $fn.Environment.Variables.$key
                        if ($val -match [regex]::Escape($srcBucket)) {
                            $updated[$key] = $val -replace [regex]::Escape($srcBucket), $dstBucket
                            $needsUpdate = $true
                        } else {
                            $updated[$key] = $val
                        }
                    }
                }

                # If S3_BUCKET isn't set at all, check if this function uses the old
                # bucket as a hardcoded default (reviewFunction pattern) and inject it
                if (-not $updated.ContainsKey("S3_BUCKET")) {
                    # Download the function ZIP and check source code for the old bucket name
                    $prevPref2 = $ErrorActionPreference; $ErrorActionPreference = "Continue"
                    $fnCodeUrl = aws lambda get-function `
                        --function-name $fn.FunctionName `
                        --region        $TargetRegion `
                        --query         "Code.Location" `
                        --output        text 2>$null
                    $ErrorActionPreference = $prevPref2
                    if ($fnCodeUrl) {
                        $tmpZip  = Join-Path $TempDir "$($fn.FunctionName)-check.zip"
                        $tmpDir  = Join-Path $TempDir "$($fn.FunctionName)-check"
                        Invoke-WebRequest -Uri $fnCodeUrl -OutFile $tmpZip -UseBasicParsing 2>$null
                        Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force 2>$null
                        $srcOccurrences = Get-ChildItem -Path $tmpDir -Recurse -File |
                            Select-String -Pattern ([regex]::Escape($srcBucket)) -ErrorAction SilentlyContinue
                        if ($srcOccurrences) {
                            $updated["S3_BUCKET"] = $dstBucket
                            $needsUpdate = $true
                            Write-Host "      Detected hardcoded default '$srcBucket' in $($fn.FunctionName) -- injecting S3_BUCKET env var"
                        }
                        Remove-Item $tmpZip, $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }

                if ($needsUpdate) {
                    $envStr = ($updated.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ","
                    Write-Host "      Patching env vars on $($fn.FunctionName)..."
                    if ($PSCmdlet.ShouldProcess($fn.FunctionName, "Update env vars")) {
                        aws lambda update-function-configuration `
                            --function-name $fn.FunctionName `
                            --region        $TargetRegion `
                            --environment   "Variables={$envStr}" `
                            --no-cli-pager | Out-Null
                    }
                }
            }
        }
        Write-Ok "$srcBucket migration done"
    }
}

# =============================================================================
# Done
# =============================================================================
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " Migration complete!  $SourceRegion -> $TargetRegion" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. DynamoDB tables are regional. Options:"
Write-Host "       a) Keep tables in $SourceRegion and access cross-region (update env vars)"
Write-Host "       b) Enable DynamoDB Global Tables (recommended for production)"
Write-Host "       c) Re-create and re-populate tables in $TargetRegion"
Write-Host "  2. S3 buckets: migrated above. Update front-end/Lambda references to the new bucket name(s)."
Write-Host "  3. Bedrock model access must be re-requested per region in the AWS console."
Write-Host "  4. Update your front-end API URL to the new $TargetRegion API Gateway endpoint."
Write-Host ""
Write-Host "Temp files: $TempDir" -ForegroundColor DarkGray
