# daily_publish.ps1 -- publish the day's reports once daily_collect has closed the day.
#
# Purpose    run refresh_and_deploy.ps1 once a day without a person at the keyboard
# Boundary   it does not collect, and it never pushes a commit it did not make
# Invariant  it publishes only from main, with an empty index, behind origin/main by 0, and
#            ahead only by its own data commits. Without this a dev session's unpushed
#            work would go public together with the data
# Failure    a failed guard or step exits 1 and leaves the day open; the next scheduled
#            attempt retries. data/live/PAUSE_PUBLISH stops it without touching collection
#
# ASCII-only: Windows PowerShell 5.1 misreads UTF-8 without a BOM. Task: register_task.ps1.

param([switch]$WhatIf)   # run the guards only

$ErrorActionPreference = "Continue"
if ($PSScriptRoot) { $scriptDir = $PSScriptRoot } else { $scriptDir = Split-Path -Parent $PSCommandPath }
$repo = Split-Path -Parent $scriptDir
Set-Location $repo
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$live = Join-Path $repo "data\live"
$stateDir = Join-Path $live "state"
$logDir = Join-Path $live "logs"
New-Item -ItemType Directory -Force -Path $stateDir, $logDir | Out-Null
$today = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "publish.log"
function Log($msg) { $line = "$(Get-Date -Format s) | $msg"; Add-Content -Path $log -Value $line -Encoding utf8; Write-Output $line }
function Fail($msg) { Log "!! $msg"; Log "=== daily_publish failed ($today) ==="; exit 1 }

if (Test-Path (Join-Path $live "PAUSE_PUBLISH")) { Log "PAUSE_PUBLISH present -- skipped"; exit 0 }

function Is-Done($path) {
  if (-not (Test-Path $path)) { return $false }
  try { return [bool](Get-Content $path -Raw -Encoding utf8 | ConvertFrom-Json).done } catch { return $false }
}

# Publishing before the collector closes the day would ship a half-built set of reports.
# Yesterday comes first: a collect retried late can close its day after the last publish
# attempt, or after midnight, and that day would otherwise never be published.
$day = $null
$yesterday = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
foreach ($d in @($yesterday, $today)) {
  if ((Is-Done (Join-Path $stateDir "run_$d.json")) -and -not (Is-Done (Join-Path $stateDir "publish_$d.json"))) { $day = $d; break }
}
if (-not $day) {
  if (Is-Done (Join-Path $stateDir "publish_$today.json")) { Log "skip ($today) -- already published"; exit 0 }
  Log "wait ($today) -- collect not done yet"; exit 0
}
$pubPath = Join-Path $stateDir "publish_$day.json"

# --- git guards ---
$branch = (git rev-parse --abbrev-ref HEAD | Out-String).Trim()
if ($branch -ne "main") { Fail "on branch '$branch', not main" }
git fetch -q origin main
if ($LASTEXITCODE -ne 0) { Fail "git fetch failed" }
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { Fail "index has staged changes -- someone is mid-commit" }

$counts = (git rev-list --left-right --count "origin/main...HEAD" | Out-String).Trim() -split '\s+'
$behind = [int]$counts[0]
$ahead = [int]$counts[1]
if ($behind -gt 0) { Fail "main is $behind commit(s) behind origin/main -- pull by hand first" }
if ($ahead -gt 0) {
  # Only a push that failed on an earlier attempt may be retried. Anything else is a person's work.
  $reportPath = '^(modules/[^/]+/output/report\.json|apps/dashboard/data/(reports|labs)\.json)$'
  $subjects = @(git log --format=%s "origin/main..HEAD")
  $files = @(git diff --name-only "origin/main" HEAD)
  $foreignSubj = @($subjects | Where-Object { $_ -notmatch '^data: \d{4}-\d{2}-\d{2} ' })
  $foreignFile = @($files | Where-Object { $_ -notmatch $reportPath })
  if ($foreignSubj.Count -gt 0 -or $foreignFile.Count -gt 0) {
    Fail "main is $ahead commit(s) ahead with work that is not a data commit -- not publishing it"
  }
  Log "retry ($today) -- $ahead unpushed data commit(s) from an earlier attempt"
}

if ($WhatIf) { Log "guards passed ($day) -- WhatIf, nothing run"; exit 0 }

# --- publish ---
Log "=== daily_publish start ($day) ==="
$out = Join-Path $logDir "publish_$today.log"
$refresh = Join-Path $scriptDir "refresh_and_deploy.ps1"
# A child process, so the refresh script's own exit codes stay its own.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $refresh -DataOnly 2>&1 | Out-File -FilePath $out -Append -Encoding utf8
$code = $LASTEXITCODE
# Exit 3: pushed, page not confirmed. The day is closed anyway, because a retry would
# rebuild with a new generatedAt and push another commit every two hours.
if ($code -ne 0 -and $code -ne 3) { Fail "refresh_and_deploy exited $code -- see logs\publish_$today.log" }

$head = (git rev-parse --short HEAD | Out-String).Trim()
$state = [ordered]@{ date = $day; done = $true; completedAt = (Get-Date -Format s); head = $head; pageConfirmed = ($code -eq 0) }
($state | ConvertTo-Json) | Set-Content -Path $pubPath -Encoding utf8
if ($code -eq 3) { Log "!! pushed but the page was not confirmed -- check Vercel. see logs\publish_$today.log" }
Log "=== daily_publish done ($day) head=$head ==="
exit 0
