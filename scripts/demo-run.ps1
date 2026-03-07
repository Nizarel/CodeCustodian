<#
.SYNOPSIS
    CodeCustodian Demo Script — scan, analyze, and showcase the full pipeline.

.DESCRIPTION
    Runs CodeCustodian against the demo enterprise app to demonstrate:
    1. Scanning (all 5 scanner types)
    2. Findings summary with severity breakdown
    3. Dry-run pipeline (plan + cost savings estimate)
    4. Individual finding deep-dive

.EXAMPLE
    .\scripts\demo-run.ps1
    .\scripts\demo-run.ps1 -SkipPause
#>
param(
    [switch]$SkipPause
)

$ErrorActionPreference = "Continue"
$DemoRepo = "demo/sample-enterprise-app"

function Write-Step {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host ""
    if (-not $SkipPause) {
        Write-Host "  Press any key to continue..." -ForegroundColor DarkGray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Write-Host ""
    }
}

# ── Step 0: Banner ──────────────────────────────────────────────────────
Write-Host ""
Write-Host @"
   ____          _       ____          _            _ _
  / ___|___   __| | ___ / ___|   _ ___| |_ ___   __| (_) __ _ _ __
 | |   / _ \ / _` |/ _ \ |  | | | / __| __/ _ \ / _` | |/ _` | '_ \
 | |__| (_) | (_| |  __/ |__| |_| \__ \ || (_) | (_| | | (_| | | | |
  \____\___/ \__,_|\___|\____\__,_|___/\__\___/ \__,_|_|\__,_|_| |_|

"@ -ForegroundColor Green

Write-Host "  Autonomous AI Agent for Technical Debt Management" -ForegroundColor White
Write-Host "  Powered by GitHub Copilot SDK + FastMCP + Azure" -ForegroundColor DarkGray
Write-Host "  Version: $(codecustodian version 2>$null)" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Scan ────────────────────────────────────────────────────────
Write-Step "STEP 1: Scanning Enterprise Codebase (5 Scanner Types)"

Write-Host "  Target: $DemoRepo" -ForegroundColor Yellow
Write-Host "  Scanners: deprecated_apis, todo_comments, code_smells, security, type_coverage" -ForegroundColor Yellow
Write-Host ""

codecustodian scan --repo-path $DemoRepo 2>$null

# ── Step 2: Findings breakdown ──────────────────────────────────────────
Write-Step "STEP 2: Findings Analysis"

$json = codecustodian scan --repo-path $DemoRepo --output-format json 2>$null
$findings = $json | ConvertFrom-Json
$total = $findings.Count

Write-Host "  Total findings: $total" -ForegroundColor White
Write-Host ""

Write-Host "  By Type:" -ForegroundColor Yellow
$findings | Group-Object -Property type | ForEach-Object {
    $pct = [math]::Round(($_.Count / $total) * 100)
    $bar = "#" * [math]::Min($_.Count, 30)
    Write-Host ("    {0,-20} {1,3} ({2}%)  {3}" -f $_.Name, $_.Count, $pct, $bar) -ForegroundColor White
}

Write-Host ""
Write-Host "  By Severity:" -ForegroundColor Yellow
$severityColors = @{ "critical" = "Red"; "high" = "Magenta"; "medium" = "Yellow"; "low" = "Gray" }
$findings | Group-Object -Property severity | Sort-Object { switch ($_.Name) { "critical" {0} "high" {1} "medium" {2} "low" {3} } } | ForEach-Object {
    $color = $severityColors[$_.Name]
    if (-not $color) { $color = "White" }
    Write-Host ("    {0,-12} {1,3}" -f $_.Name.ToUpper(), $_.Count) -ForegroundColor $color
}

# ── Step 3: Cost estimate ───────────────────────────────────────────────
Write-Step "STEP 3: Business Value — Cost Savings Estimate"

$criticalCount = ($findings | Where-Object { $_.severity -eq "critical" }).Count
$highCount = ($findings | Where-Object { $_.severity -eq "high" }).Count
$mediumCount = ($findings | Where-Object { $_.severity -eq "medium" }).Count
$lowCount = ($findings | Where-Object { $_.severity -eq "low" }).Count

# Industry averages: critical ~4h, high ~2h, medium ~1h, low ~0.5h manual fix time
$manualHours = ($criticalCount * 4) + ($highCount * 2) + ($mediumCount * 1) + ($lowCount * 0.5)
$automatedMinutes = $total * 5  # ~5 min review per auto-fix
$hoursSaved = $manualHours - ($automatedMinutes / 60)
$costPerHour = 85  # Average senior dev hourly rate
$moneySaved = [math]::Round($hoursSaved * $costPerHour)

Write-Host "  Manual remediation estimate:" -ForegroundColor Yellow
Write-Host "    Critical `($criticalCount findings x 4h`)  = $($criticalCount * 4)h" -ForegroundColor Red
Write-Host "    High     `($highCount findings x 2h`)  = $($highCount * 2)h" -ForegroundColor Magenta
Write-Host "    Medium   `($mediumCount findings x 1h`)  = $($mediumCount * 1)h" -ForegroundColor Yellow
Write-Host "    Low      `($lowCount findings x 0.5h`) = $($lowCount * 0.5)h" -ForegroundColor Gray
Write-Host "    ─────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "    Total manual effort:        $($manualHours)h" -ForegroundColor White
Write-Host ""
Write-Host "  With CodeCustodian:" -ForegroundColor Green
Write-Host "    Auto-fix + human review:    $([math]::Round($automatedMinutes / 60, 1))h" -ForegroundColor Green
Write-Host "    Engineering hours saved:    $([math]::Round($hoursSaved, 1))h" -ForegroundColor Green
Write-Host "    Cost savings (@ `$$costPerHour/h):  `$$moneySaved" -ForegroundColor Green

# ── Step 4: Dry-run pipeline ────────────────────────────────────────────
Write-Step "STEP 4: Dry-Run Pipeline (Scan → Plan → Safety Check)"

codecustodian run --repo-path $DemoRepo --dry-run --output-format json 2>$null

# ── Step 5: ChatOps — Teams Notification (Work IQ enriched) ─────────────
Write-Step "STEP 5: ChatOps → Teams Notification (Azure + Work IQ)"

Write-Host "  Sending scan results to Microsoft Teams via ChatOps..." -ForegroundColor Yellow
Write-Host "  Enriched with Work IQ sprint context (capacity, code freeze, experts)" -ForegroundColor Yellow
Write-Host ""

$chatPayload = @{
    total_findings = $total
    critical = $criticalCount
    high = $highCount
    repo = $DemoRepo
} | ConvertTo-Json -Compress

Write-Host "  Adaptive Card payload:" -ForegroundColor DarkGray
Write-Host "    Type: scan_complete" -ForegroundColor White
Write-Host "    Findings: $total (Critical: $criticalCount, High: $highCount)" -ForegroundColor White
Write-Host "    Connector: Microsoft Teams (Incoming Webhook)" -ForegroundColor White
Write-Host "    Work IQ: Sprint context enrichment enabled" -ForegroundColor White
Write-Host ""

# Demo the MCP tool invocation (simulated if no webhook configured)
$webhookUrl = $env:TEAMS_WEBHOOK_URL
if ($webhookUrl) {
    Write-Host "  Webhook configured - sending live notification" -ForegroundColor Green
    $pyScript = @"
import asyncio, json
from codecustodian.integrations.teams_chatops import TeamsConnector, build_scan_complete_card
from codecustodian.config.schema import ChatOpsConfig
from codecustodian.models import ChatOpsNotification
async def send():
    config = ChatOpsConfig(enabled=True, teams_webhook_url='$webhookUrl')
    n = ChatOpsNotification(message_type='scan_complete', payload=json.loads('$chatPayload'))
    connector = TeamsConnector(config=config)
    ok = await connector.send(n)
    await connector.close()
    print(f'  Delivered: {ok}')
asyncio.run(send())
"@
    python -c $pyScript 2>$null
} else {
    Write-Host "  No TEAMS_WEBHOOK_URL set - showing Adaptive Card preview" -ForegroundColor Cyan
    $pyScript = @"
import json
from codecustodian.integrations.teams_chatops import build_scan_complete_card
card = build_scan_complete_card(total_findings=$total, critical=$criticalCount, high=$highCount, repo='$DemoRepo')
print(json.dumps(card, indent=2))
"@
    python -c $pyScript 2>$null
}

Write-Host ""
Write-Host "  Azure deployment: Teams webhook URL stored in Azure Key Vault" -ForegroundColor DarkGray
Write-Host "  Container App receives TEAMS_WEBHOOK_URL environment variable" -ForegroundColor DarkGray

# ── Step 6: Security deep-dive ──────────────────────────────────────────
Write-Step "STEP 6: Security Findings Deep-Dive"

codecustodian findings --repo-path $DemoRepo --severity critical --output-format table 2>$null

# ── Done ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host "  DEMO COMPLETE" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host ""
Write-Host "  Summary:" -ForegroundColor White
Write-Host "    Findings detected:     $total" -ForegroundColor White
Write-Host "    Scanner types used:    5" -ForegroundColor White
Write-Host "    Engineering hours saved: $([math]::Round($hoursSaved, 1))h" -ForegroundColor Green
Write-Host "    Estimated cost savings:  `$$moneySaved" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "    codecustodian run --repo-path $DemoRepo           # Create PRs" -ForegroundColor DarkGray
Write-Host "    codecustodian report --format json                 # ROI report" -ForegroundColor DarkGray
Write-Host "    codecustodian interactive                          # Interactive menu" -ForegroundColor DarkGray
Write-Host "    TEAMS_WEBHOOK_URL=<url> .\scripts\demo-run.ps1    # Live ChatOps" -ForegroundColor DarkGray
Write-Host ""
