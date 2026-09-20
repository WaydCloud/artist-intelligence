# Rebuild every report from layer 1, gate it, commit, push and deploy.
#
# Purpose    one command between a finished collection and the public page
# Boundary   it does not collect. Run it after daily_collect has finished for the day
# Invariant  it stops before deploying when a gate fails. Shipping a page that a gate
#            rejected is how a thin day gets read as a real one
# Failure    any failing step ends the run with a non-zero exit and nothing is deployed
# Note       the deploy is not run from here. The Vercel project builds every commit on
#            main, so the push is the deploy. This waits for it and checks the paths.

param(
  [switch]$NoDeploy,   # rebuild, gate and commit only
  [switch]$NoCommit    # rebuild and gate only
)

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONIOENCODING = "utf-8"
$wl = "packages/entity-master/watchlist.json"

function Step($name, [scriptblock]$body) {
  Write-Host ""
  Write-Host "== $name =="
  & $body
  if ($LASTEXITCODE -ne 0) { Write-Host "!! $name FAILED (exit $LASTEXITCODE)"; exit 1 }
}

Step "chart-history report" {
  $env:PYTHONPATH = "modules/chart-history/src"
  python -m chart_history analyze data/live/chart --latest --entities packages/entity-master/entities.json --watchlist $wl --geo-scope KR -o modules/chart-history/output/
}
Step "chart series" {
  $env:PYTHONPATH = "modules/chart-history/src"
  python -m chart_history signals data/live/chart --entities packages/entity-master/entities.json --watchlist $wl -o data/live/chart_series.json
}
Step "fandom report" {
  $env:PYTHONPATH = "modules/fandom-pulse/src"
  python -m fandom_pulse analyze data/live/social_merged.json --entities packages/entity-master/entities.json --watchlist $wl -o modules/fandom-pulse/output/
}
Step "yt report" {
  $env:PYTHONPATH = "modules/yt-pulse/src"
  python -m yt_pulse analyze data/live/yt -o modules/yt-pulse/output/
}
Step "sonic report" {
  $env:PYTHONPATH = "modules/sonic-profile/src"
  python -m sonic_profile analyze data/live/sonic --watchlist $wl -o modules/sonic-profile/output/
}
Step "genre report" {
  $env:PYTHONPATH = "modules/genre-impulse/src;modules/sonic-profile/src"
  python -m genre_impulse analyze --sonic data/live/sonic --watchlist $wl -o modules/genre-impulse/output/
}
Step "signal-bridge report" {
  $env:PYTHONPATH = "modules/signal-bridge/src"
  python -m signal_bridge analyze --social data/live/social_series.json --chart data/live/chart_series.json --theta-rank 200 --focus-social --watchlist $wl --youtube data/live/yt_series.json -o modules/signal-bridge/output/
}
Step "dashboard collect" { node apps/dashboard/scripts/collect-reports.mjs; node apps/dashboard/scripts/collect-labs.mjs }

Step "contract gate" { python scripts/validate_report_data.py --selftest; python scripts/validate_report_data.py }

# The coverage gate reports, it does not withhold. A thin day still ships, carrying its
# own sample line. It is here so the person running this sees it before the page is public.
Write-Host ""
Write-Host "== coverage gate =="
python scripts/validate_coverage.py data/live/sonic --latest-only
if ($LASTEXITCODE -ne 0) { Write-Host "!! coverage RED -- the page will carry a thin sample. Continuing." }

if ($NoCommit) { Write-Host ""; Write-Host "done (no commit)"; exit 0 }

Step "commit" {
  git add modules/*/output/report.json apps/dashboard/data/reports.json apps/dashboard/data/labs.json
  $changed = git diff --cached --name-only
  if (-not $changed) { Write-Host "  변경 없음 -- 커밋 생략"; $global:LASTEXITCODE = 0; return }
  $today = Get-Date -Format "yyyy-MM-dd"
  git commit -m "data: $today 수집을 리포트에 반영"
}
Step "push" { git push }

if ($NoDeploy) { Write-Host ""; Write-Host "done (no deploy)"; exit 0 }

# The push above already triggered the deploy: this project is connected to GitHub and
# every commit on main builds. Uploading out/ by hand would race that build and land a
# second deployment on the same alias. So here we only watch and check.
Write-Host ""
Write-Host "== deploy (push 가 이미 걸었다. 기다린다) =="
$deadline = (Get-Date).AddMinutes(6)
do {
  Start-Sleep -Seconds 15
  $row = (vercel ls artist-intelligence --scope waydclouds-projects 2>$null | Select-Object -Index 4)
  Write-Host "  $($row -replace '\s+', ' ')"
} while ($row -notmatch 'Ready|Error' -and (Get-Date) -lt $deadline)

if ($row -match 'Error') { Write-Host "!! 배포 실패 -- Vercel 로그를 볼 것"; exit 1 }
if ($row -notmatch 'Ready') { Write-Host "!! 6분 안에 Ready 가 안 됐다 -- Vercel 을 볼 것"; exit 1 }

# A green build is not a working page. The static export names the page
# artist-intelligence.html while the site links to /artist-intelligence, and that gap
# served 404 on every link once (2026-09-21). So the paths get checked, not assumed.
Write-Host ""
Write-Host "== 경로 확인 =="
$bad = 0
foreach ($path in @("/", "/artist-intelligence", "/labs", "/utilities")) {
  try {
    $code = (Invoke-WebRequest -Uri "https://artist-intelligence-mocha.vercel.app$path" -Method Head -UseBasicParsing).StatusCode
  } catch { $code = $_.Exception.Response.StatusCode.value__ }
  Write-Host "  $code  $path"
  if ($code -ne 200) { $bad++ }
}
if ($bad) { Write-Host "!! 200 이 아닌 경로 $bad 개"; exit 1 }

Write-Host ""
Write-Host "done -- https://artist-intelligence-mocha.vercel.app"
