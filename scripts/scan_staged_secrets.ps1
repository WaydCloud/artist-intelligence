# scan_staged_secrets.ps1 -- fail when the staged diff carries a secret.
#
# Purpose    a local secret gate between `git add` and `git commit` for unattended publishes
# Boundary   it reads only added lines of the staged diff. It never prints a matched value
# Invariant  exit 1 on any hit. The repo is public, and a pushed key cannot be pulled back
# Note       gitleaks is not installed on this PC (2026-10-15). CI still runs gitleaks after push
#
# ASCII-only: Windows PowerShell 5.1 misreads UTF-8 without a BOM.

param([string[]]$Paths = @())   # limit the scan to these paths; empty means the whole index

$ErrorActionPreference = "Continue"

$patterns = [ordered]@{
  "github token"      = 'gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}'
  "anthropic key"     = 'sk-ant-[A-Za-z0-9_\-]{20,}'
  "openai-style key"  = 'sk-[A-Za-z0-9]{32,}'
  "aws access key"    = 'AKIA[0-9A-Z]{16}'
  "google api key"    = 'AIza[0-9A-Za-z_\-]{35}'
  "apify token"       = 'apify_api_[A-Za-z0-9]{20,}'
  "slack token"       = 'xox[abprs]-[A-Za-z0-9\-]{10,}'
  "private key block" = '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  "jwt"               = 'eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'
}

# Exact values of this user's secret-looking env vars. A pattern list misses vendor
# formats it does not know; the real value does not.
$values = @{}
foreach ($scope in @("Process", "User", "Machine")) {
  $vars = [Environment]::GetEnvironmentVariables($scope)
  foreach ($name in $vars.Keys) {
    $v = [string]$vars[$name]
    if ($name -match '(TOKEN|SECRET|PASSWORD|API_KEY|_KEY)$' -and $v.Length -ge 12) { $values[$name] = $v }
  }
}

$file = ""
$header = $false
$hits = @()
foreach ($line in (git diff --cached -U0 --no-color -- $Paths)) {
  # "+++ " names the file only in a file header. Inside a hunk it is an added line.
  if ($line.StartsWith("diff --git ")) { $header = $true; continue }
  if ($line.StartsWith("@@")) { $header = $false; continue }
  if ($header) { if ($line.StartsWith("+++ ")) { $file = $line.Substring(4) -replace '^b/', '' }; continue }
  if (-not $line.StartsWith("+")) { continue }
  foreach ($k in $patterns.Keys) {
    # Case-sensitive: the formats are, and -match would let lowercase IDs trip AKIA or eyJ.
    if ($line -cmatch $patterns[$k]) { $hits += "$file : $k" }
  }
  foreach ($k in $values.Keys) {
    if ($line.Contains($values[$k])) { $hits += "$file : value of env $k" }
  }
}

if ($hits.Count -gt 0) {
  Write-Output "!! secret scan: $($hits.Count) hit(s)"
  $hits | Sort-Object -Unique | ForEach-Object { Write-Output "   $_" }
  exit 1
}
Write-Output "secret scan clean ($($patterns.Count) patterns, $($values.Count) env values)"
exit 0
