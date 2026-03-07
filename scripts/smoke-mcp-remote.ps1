param(
    [Parameter(Mandatory = $true)]
    [string]$Fqdn,
    [int]$TimeoutSeconds = 120,
    [string]$ToolName = "list_scanners"
)

$ErrorActionPreference = "Stop"

function Get-SseJsonPayload {
    param([string]$Content)

    $dataLines = ($Content -split "`n" | Where-Object { $_ -like "data:*" })
    if (-not $dataLines) {
        throw "No SSE data payload found in response"
    }

    foreach ($line in $dataLines) {
        $payload = $line.Substring(5).Trim()
        if (-not $payload) {
            continue
        }

        try {
            $obj = $payload | ConvertFrom-Json
            if ($obj.result -or $obj.error) {
                return $obj
            }
        } catch {
            continue
        }
    }

    throw "No JSON-RPC result/error payload found in SSE response"
}

function Invoke-McpRequest {
    param(
        [string]$Url,
        [string]$Body,
        [string]$Accept,
        [string]$SessionId = ""
    )

    $args = @(
        "-sS",
        "-i",
        "-X",
        "POST",
        $Url,
        "-H",
        "Content-Type: application/json",
        "-H",
        "Accept: $Accept"
    )

    if ($SessionId) {
        $args += @("-H", "mcp-session-id: $SessionId")
    }

    $args += @("--data", $Body)

    $raw = & curl.exe @args
    if ($LASTEXITCODE -ne 0) {
        throw "curl request failed with exit code $LASTEXITCODE"
    }

    $text = [string]::Join("`n", $raw)
    $parts = [regex]::Split($text, "`r?`n`r?`n", 2)
    if ($parts.Count -lt 2) {
        throw "Failed to parse HTTP response"
    }

    return [PSCustomObject]@{
        Headers = $parts[0]
        Body = $parts[1]
    }
}

$baseUrl = "https://$Fqdn"
$mcpUrl = "$baseUrl/mcp"
$acceptHeader = "application/json, text/event-stream"

Write-Host "Checking health: $baseUrl/health"
$healthResponse = $null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
        $healthResponse = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get -TimeoutSec $TimeoutSeconds
        break
    } catch {
        Write-Host "Health check attempt $attempt failed: $_"
        if ($attempt -lt 3) { Start-Sleep -Seconds 10 }
    }
}
if (-not $healthResponse -or $healthResponse.status -ne "ok") {
    throw "Health check failed after 3 attempts"
}

Write-Host "Health OK (version=$($healthResponse.version))"

$initializeBody = @{
    jsonrpc = "2.0"
    id = 1
    method = "initialize"
    params = @{
        protocolVersion = "2025-03-26"
        capabilities = @{}
        clientInfo = @{
            name = "codecustodian-smoke"
            version = "1.0.0"
        }
    }
} | ConvertTo-Json -Depth 10

Write-Host "Initializing MCP session"
$initResponse = Invoke-McpRequest -Url $mcpUrl -Body $initializeBody -Accept $acceptHeader
$sessionIdMatch = [regex]::Match($initResponse.Headers, "(?im)^mcp-session-id:\s*(\S+)")
if ($sessionIdMatch.Success) {
    $sessionId = $sessionIdMatch.Groups[1].Value.Trim()
}
if (-not $sessionId) {
    throw "Missing mcp-session-id in initialize response"
}

$initPayload = Get-SseJsonPayload -Content $initResponse.Body
if ($initPayload.error) {
    throw "Initialize failed: $($initPayload.error.message)"
}

Write-Host "Session established: $sessionId"

$toolsListBody = @{
    jsonrpc = "2.0"
    id = 2
    method = "tools/list"
    params = @{}
} | ConvertTo-Json -Depth 5

Write-Host "Listing tools"
$toolsResponse = Invoke-McpRequest -Url $mcpUrl -Body $toolsListBody -Accept $acceptHeader -SessionId $sessionId
$toolsPayload = Get-SseJsonPayload -Content $toolsResponse.Body
if ($toolsPayload.error) {
    throw "tools/list failed: $($toolsPayload.error.message)"
}

$toolCount = ($toolsPayload.result.tools | Measure-Object).Count
if ($toolCount -le 0) {
    throw "tools/list returned no tools"
}

Write-Host "Tools available: $toolCount"

$toolCallBody = @{
    jsonrpc = "2.0"
    id = 3
    method = "tools/call"
    params = @{
        name = $ToolName
        arguments = @{}
    }
} | ConvertTo-Json -Depth 10

Write-Host "Calling tool: $ToolName"
$callPayload = $null
$callNotificationText = $null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    $callResponse = Invoke-McpRequest -Url $mcpUrl -Body $toolCallBody -Accept $acceptHeader -SessionId $sessionId
    $dataLines = @($callResponse.Body -split "`n" | Where-Object { $_ -like "data:*" })

    foreach ($line in $dataLines) {
        $payload = $line.Substring(5).Trim()
        if (-not $payload) {
            continue
        }

        if ($payload -match "registered scanners") {
            $callNotificationText = $payload
        }

        try {
            $obj = $payload | ConvertFrom-Json
            if ($obj.error) {
                throw "tools/call failed: $($obj.error.message)"
            }
            if ($obj.id -eq 3 -and $obj.result) {
                $callPayload = $obj
                break
            }
        } catch {
            continue
        }
    }

    if ($callPayload) {
        break
    }

    Start-Sleep -Seconds 1
}

$scannerCount = 0
if ($callPayload) {
    if ($callPayload.result.structuredContent -and $callPayload.result.structuredContent.result) {
        $scannerCount = @($callPayload.result.structuredContent.result).Count
    } elseif ($callPayload.result.content -and $callPayload.result.content[0].text) {
        $parsed = $callPayload.result.content[0].text | ConvertFrom-Json
        if ($parsed.result) {
            $scannerCount = @($parsed.result).Count
        } else {
            $scannerCount = @($parsed).Count
        }
    }
} elseif ($callNotificationText -and $callNotificationText -match 'Found\s+(\d+)\s+registered scanners') {
    $scannerCount = [int]$Matches[1]
}

if (-not $callPayload -and -not $callNotificationText) {
    throw "tools/call did not return a result or scanner notification payload"
}

if ($ToolName -eq "list_scanners" -and $scannerCount -le 0) {
    if ($callPayload) {
        throw "tools/call list_scanners returned no scanner entries"
    }
}

Write-Host "Tool call OK ($ToolName), result_count=$scannerCount"
Write-Host "MCP smoke test passed"
