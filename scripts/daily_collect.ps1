# daily_collect.ps1 -- forward experiment daily collector, v2 (D-013 wide collection).
# ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8-without-BOM scripts,
# which corrupts parsing (a non-ASCII comment can break the next line). Keep it ASCII.
#
# Config-driven (config/collect.json): chart markets (free Kworb), social hashtags
# (genre tags + watchlist act tags, paid Apify with per-tag USD cap), daily budget
# enforced cumulatively. Every fetched social snapshot passes the PII gate
# (scripts/validate_snapshot.py); REJECTed files are quarantined so they never join.
# Pipeline: collect -> gate -> merge/dedup -> signal-series (social+chart, watchlist
# attribution) -> signal-bridge (watchlist profile) -> dashboard refresh -> summary.
#
# Guards: (1) data/live/PAUSE file -> skip paid fetch (free chart still runs).
#         (2) past config experiment_end -> skip paid fetch (cost guard).
#         (3) AI_DRYRUN=1 env -> skip paid fetch (for testing).
#         (4) per-tag maxTotalChargeUsd cap + cumulative daily_budget_usd stop.
# Stop: disable/delete Task Scheduler task "AI-daily-collect", or create data/live/PAUSE.

$ErrorActionPreference = "Continue"
if ($PSScriptRoot) { $scriptDir = $PSScriptRoot } elseif ($PSCommandPath) { $scriptDir = Split-Path -Parent $PSCommandPath } else { $scriptDir = (Get-Location).Path }
$repo = Split-Path -Parent $scriptDir
if (-not (Test-Path (Join-Path $repo "AGENTS.md"))) { $repo = (Get-Location).Path }   # fallback to CWD
Set-Location $repo

$live = Join-Path $repo "data\live"
$logDir = Join-Path $live "logs"
New-Item -ItemType Directory -Force -Path $logDir, (Join-Path $live "social"), (Join-Path $live "chart"), (Join-Path $live "quarantine") | Out-Null
$today = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "daily.log"
function Log($msg) { $line = "$(Get-Date -Format s) | $msg"; Add-Content -Path $log -Value $line -Encoding utf8; Write-Output $line }

# --- config ---
$cfgPath = Join-Path $repo "config\collect.json"
$cfg = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json
$markets = @($cfg.chart_markets)
$tagList = @($cfg.genre_hashtags)
$wlPath = Join-Path $repo "packages\entity-master\watchlist.json"
if ($cfg.use_watchlist_hashtags -and (Test-Path $wlPath)) {
  $wl = Get-Content $wlPath -Raw -Encoding utf8 | ConvertFrom-Json
  foreach ($a in @($wl.artists)) { foreach ($t in @($a.hashtags)) { if ($t -and ($tagList -notcontains $t)) { $tagList += $t } } }
}
$perTagItems = [int]$cfg.per_tag_max_items
$perTagUsd = [double]$cfg.per_tag_max_usd
$dailyBudget = [double]$cfg.daily_budget_usd
$experimentEnd = [datetime]$cfg.experiment_end

Log "=== daily_collect v2 start ($today) | repo=$repo | markets=$($markets.Count) tags=$($tagList.Count) budget=`$$dailyBudget ==="

# --- one-time migrations: old flat stores -> chart/<cc>/ -> chart/<platform>/<cc>/ (D-016) ---
foreach ($pair in @(@("chart_kr", "kr"), @("chart_global", "global"))) {
  $old = Join-Path $live $pair[0]
  $new = Join-Path (Join-Path $live "chart") $pair[1]
  if (Test-Path $old) {
    New-Item -ItemType Directory -Force -Path $new | Out-Null
    Get-ChildItem "$old\*.html" -ErrorAction SilentlyContinue | Move-Item -Destination $new -Force
    Remove-Item $old -Recurse -Force -ErrorAction SilentlyContinue
    Log "migrated $($pair[0]) -> chart/$($pair[1])"
  }
}
# chart/<cc>/ (platform-less spotify era) -> chart/spotify/<cc>/
$chartRoot = Join-Path $live "chart"
if (Test-Path $chartRoot) {
  $known = @("spotify", "apple", "youtube")
  foreach ($dir in @(Get-ChildItem $chartRoot -Directory -ErrorAction SilentlyContinue)) {
    if ($known -notcontains $dir.Name) {
      $dest = Join-Path (Join-Path $chartRoot "spotify") $dir.Name
      New-Item -ItemType Directory -Force -Path $dest | Out-Null
      Get-ChildItem "$($dir.FullName)\*.html" -ErrorAction SilentlyContinue | Move-Item -Destination $dest -Force
      Remove-Item $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
      Log "migrated chart/$($dir.Name) -> chart/spotify/$($dir.Name)"
    }
  }
}

# 1) free chart collect -- 3 platform rails (D-016): Kworb Spotify + Apple official RSS + Kworb YouTube
$env:PYTHONPATH = "modules/chart-history/src"
$okM = 0; $failM = 0
foreach ($cc in $markets) {
  $ccU = $cc.ToUpper()
  python -m chart_history collect --url "https://kworb.net/spotify/country/${cc}_daily.html" --store "data/live/chart/spotify/$cc" --country $ccU --platform spotify --chart-name "Spotify $ccU Daily" 2>$null | Out-Null
  if ($?) { $okM++ } else { $failM++; Log "!! chart spotify/$cc collect FAILED (skipped)" }
}
Log "spotify charts: $okM ok, $failM failed of $($markets.Count) markets"
$appleMarkets = @($cfg.apple_markets)
$okA = 0; $failA = 0
foreach ($cc in $appleMarkets) {
  python -m chart_history collect-apple --storefront $cc --store "data/live/chart/apple/$cc" 2>$null | Out-Null
  if ($?) { $okA++ } else { $failA++; Log "!! chart apple/$cc collect FAILED (skipped)" }
}
Log "apple charts: $okA ok, $failA failed of $($appleMarkets.Count) storefronts (official RSS)"
$ytMarkets = @($cfg.youtube_markets)
$okY = 0; $failY = 0
foreach ($cc in $ytMarkets) {
  $ccU = $cc.ToUpper()
  python -m chart_history collect --url "https://kworb.net/youtube/insights/${cc}_daily.html" --store "data/live/chart/youtube/$cc" --country $ccU --platform youtube --chart-name "YouTube $ccU Daily" 2>$null | Out-Null
  if ($?) { $okY++ } else { $failY++; Log "!! chart youtube/$cc collect FAILED (skipped)" }
}
Log "youtube charts: $okY ok, $failY failed of $($ytMarkets.Count) markets"

# 1.5) live chart-history report -- latest snapshot per platform/market, 3-platform cross view (D-016)
$homeMarket = "KR"; if ($cfg.home_market) { $homeMarket = ([string]$cfg.home_market).ToUpper() }
python -m chart_history analyze data/live/chart --latest --entities packages/entity-master/entities.json --watchlist $wlPath --geo-scope $homeMarket -o modules/chart-history/output/
if ($?) { Log "chart-history live report written (3-platform cross view, home=$homeMarket)" } else { Log "!! chart-history analyze FAILED" }

# 2) paid social fetch per tag (capped) -- PAUSE / end-date / dry-run / budget guards
$pausePath = Join-Path $live "PAUSE"
$paused = Test-Path -LiteralPath $pausePath
$ended = (Get-Date) -gt $experimentEnd
$dryRun = $env:AI_DRYRUN -eq "1"
Log "guard | paused=$paused | ended=$ended | dryRun=$dryRun | perTag=`$$perTagUsd x $($tagList.Count) tags"
if ($paused) { Log "social fetch SKIPPED (PAUSE file present)" }
elseif ($ended) { Log "social fetch SKIPPED (past experiment_end $($experimentEnd.ToString('yyyy-MM-dd')))" }
elseif ($dryRun) { Log "social fetch SKIPPED (AI_DRYRUN=1)" }
else {
  # smart tag allocation (D-015): pick today's tags within budget (pin -> stale -> score).
  # Free-signal driven (chart_series/yt_series/social filenames), deterministic.
  # On failure fall back to the full list -- the budget guard below still caps spend.
  $fetchTags = $tagList
  if ($cfg.allocator -and $cfg.allocator.enabled) {
    New-Item -ItemType Directory -Force -Path (Join-Path $live "plans") | Out-Null
    $planPath = "data/live/plans/plan_$today.json"
    $planLine = python scripts/tag_allocator.py plan --config config/collect.json --watchlist $wlPath --live data/live --date $today -o $planPath
    if ($? -and (Test-Path $planPath)) {
      $fetchTags = @((Get-Content $planPath -Raw -Encoding utf8 | ConvertFrom-Json).tags)
      Log "allocator: $planLine"
    } else { Log "!! allocator FAILED -- fallback to full tag list (budget guard caps)" }
  }
  $env:PYTHONPATH = "modules/fandom-pulse/src"
  $spent = 0.0; $okT = 0; $failT = 0
  foreach ($tag in $fetchTags) {
    if (($spent + $perTagUsd) -gt $dailyBudget) { Log "budget stop: spent cap `$$spent + `$$perTagUsd would exceed `$$dailyBudget -- remaining tags skipped"; break }
    $out = "data/live/social/${today}_${tag}.json"
    python -m fandom_pulse fetch --hashtag $tag --results-type reels --max-items $perTagItems --max-usd $perTagUsd -o $out
    if ($?) {
      $spent += $perTagUsd; $okT++
      # PII gate: REJECT -> quarantine (never joins the pipeline)
      python scripts/validate_snapshot.py $out | Out-Null
      if (-not $?) { Move-Item $out (Join-Path $live "quarantine") -Force; Log "!! PII gate REJECT: $out -> quarantine" }
    } else { $failT++; Log "!! social fetch FAILED: #$tag" }
  }
  Log "social fetched: $okT tags ok, $failT failed | est spend cap <= `$$spent (per-run Apify cap enforced)"
}

# 3) rebuild forward signal-series (watchlist attribution, D-013)
python scripts/merge_social.py data/live/social data/live/social_merged.json
if ($?) { Log "social merged+deduped" } else { Log "!! social merge FAILED" }
$env:PYTHONPATH = "modules/fandom-pulse/src"
python -m fandom_pulse signals data/live/social_merged.json --entities packages/entity-master/entities.json --watchlist packages/entity-master/watchlist.json -o data/live/social_series.json
if ($?) { Log "social series rebuilt (sound+hashtag attribution)" } else { Log "!! social series FAILED" }

# 3.5) free YouTube rail (official API, ~12 units/day) -- D-014
$ytCache = Join-Path $repo "packages\entity-master\yt_channels.json"
$ytSeries = ""
if (Test-Path $ytCache) {
  New-Item -ItemType Directory -Force -Path (Join-Path $live "yt") | Out-Null
  $env:PYTHONPATH = "modules/yt-pulse/src"
  python -m yt_pulse fetch --channels $ytCache -o "data/live/yt/$today.json"
  if ($?) {
    python scripts/validate_snapshot.py "data/live/yt/$today.json" | Out-Null
    if (-not $?) { Move-Item "data/live/yt/$today.json" (Join-Path $live "quarantine") -Force; Log "!! PII gate REJECT: yt/$today.json -> quarantine" }
    else {
      python -m yt_pulse signals data/live/yt -o data/live/yt_series.json
      if ($?) { $ytSeries = "data/live/yt_series.json"; Log "yt fetched + series rebuilt (official channels)" } else { Log "!! yt series FAILED" }
      python -m yt_pulse analyze data/live/yt -o modules/yt-pulse/output/
      if ($?) { Log "yt report written" } else { Log "!! yt report FAILED" }
    }
  } else { Log "!! yt fetch FAILED (skipped)" }
} else { Log "yt SKIPPED (no channel cache -- run yt_pulse resolve once)" }

# chart: >=2 distinct dates -> real forward series; else Days-reconstruction fallback
$env:PYTHONPATH = "modules/chart-history/src"
$dates = @(Get-ChildItem "data\live\chart" -Recurse -Filter *.html -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName } | Sort-Object -Unique)
if ($dates.Count -ge 2) {
  python -m chart_history signals data/live/chart --entities packages/entity-master/entities.json --watchlist packages/entity-master/watchlist.json -o data/live/chart_series.json
  Log "chart series (forward multi-day, $($dates.Count) dates x markets)"
} else {
  python -m chart_history signals data/live/chart --reconstruct-days 21 --entities packages/entity-master/entities.json --watchlist packages/entity-master/watchlist.json -o data/live/chart_series.json
  Log "chart series (retrospective Days-reconstruction, $($dates.Count) date -- forward accrues)"
}

# 4) signal-bridge -> dashboard primary (live forward result, watchlist profile, +YT layer)
$env:PYTHONPATH = "modules/signal-bridge/src"
$ytArg = @(); if ($ytSeries) { $ytArg = @("--youtube", $ytSeries) }
python -m signal_bridge analyze --social data/live/social_series.json --chart data/live/chart_series.json --theta-rank 200 --focus-social --watchlist packages/entity-master/watchlist.json @ytArg -o modules/signal-bridge/output/
if ($?) { Log "bridge report written (forward, watchlist profile)" } else { Log "!! bridge FAILED" }
node apps/dashboard/scripts/collect-reports.mjs
if ($?) { Log "dashboard reports.json refreshed" } else { Log "!! dashboard collect FAILED" }

# 5) summary line: coverage + social-led / social-only counts to watch over time
python scripts/bridge_summary.py modules/signal-bridge/output/report.json 2>$null | ForEach-Object { Log $_ }
Log "=== daily_collect v2 done ($today) ==="
