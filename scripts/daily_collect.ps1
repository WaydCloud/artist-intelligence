# daily_collect.ps1 -- forward experiment daily collector, v2 (D-013 wide collection).
# ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8-without-BOM scripts,
# which corrupts parsing (a non-ASCII comment can break the next line). Keep it ASCII.
# 2026-08-01: the rule bites hardest in Log strings -- non-ASCII there is not a risk but a
# certainty. The 08-01 spend line shipped as mojibake, so the one audit trail that exists
# for a paid leg was unreadable on the first day it actually ran. Log strings stay ASCII.
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
#
# Resumable (D-018): run state lives in data/live/state/run_<date>.json. The task retries
# through the day, so every attempt must be idempotent -- a completed day is a no-op, a
# finished leg is skipped, a partly-failed leg retries only its failed targets, and a paid
# tag already collected today is never bought again. Task settings: scripts/register_task.ps1.

$ErrorActionPreference = "Continue"
if ($PSScriptRoot) { $scriptDir = $PSScriptRoot } elseif ($PSCommandPath) { $scriptDir = Split-Path -Parent $PSCommandPath } else { $scriptDir = (Get-Location).Path }
$repo = Split-Path -Parent $scriptDir
if (-not (Test-Path (Join-Path $repo "AGENTS.md"))) { $repo = (Get-Location).Path }   # fallback to CWD
Set-Location $repo

# --- 출력 인코딩: 여기서 한 번, 모든 레그보다 먼저 ---
# 이 두 줄은 **짝**이다. PYTHONIOENCODING은 파이썬이 UTF-8로 '쓰게' 만들 뿐이고, 그 stdout을
# 텍스트로 '읽는' 쪽은 PowerShell이라 [Console]::OutputEncoding을 따른다. 하나만 맞추면
# UTF-8 바이트를 콘솔 코드페이지로 읽어 로그의 한글이 깨진다(실측 2026-07-29: SUMMARY 줄
# '소셜' -> '?뚯뀥', 바이트 ec 86 8c -> 3f eb 9a af. 복구 불가).
#
# 2026-08-01: 이 짝이 원래 sonic 레그(3.6) 안에 있었다. 그 앞 레그들(chart analyze / social
# merge / yt)도 한글을 찍는데(모듈 CLI 43줄) 로컬 콘솔이 cp949라 인코딩이 되어 안 보였다.
# 러너는 코드페이지가 cp949가 아니므로 같은 print가 UnicodeEncodeError로 **레그를 죽인다** --
# 이전 첫날 chart-history 라이브 리포트부터 터졌을 자리다. 코드페이지에 의존하지 않도록
# 맨 위로 올린다. 규율은 "여기서 한 번"이고, 아래 어느 레그도 다시 묻지 않는다.
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }   # 콘솔 없는 호스트에서 던질 수 있다

$live = Join-Path $repo "data\live"
$logDir = Join-Path $live "logs"
New-Item -ItemType Directory -Force -Path $logDir, (Join-Path $live "social"), (Join-Path $live "chart"), (Join-Path $live "quarantine") | Out-Null
$today = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "daily.log"
function Log($msg) { $line = "$(Get-Date -Format s) | $msg"; Add-Content -Path $log -Value $line -Encoding utf8; Write-Output $line }

# --- run state (D-018): resume a killed run, never pay twice ---
# A missed day is a permanent gap (charts and IG only ever serve "today"), so the task
# retries through the day. That is only safe if retries are idempotent: finished legs are
# skipped, partly-failed legs retry only their failed targets, and a paid tag that already
# has a file for today is never fetched again.
$stateDir = Join-Path $live "state"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$statePath = Join-Path $stateDir "run_$today.json"
$legs = @{}
$pending = @{}
$attempt = 1
$startedAt = (Get-Date -Format s)
# 🔴 파생 단계(머지·시리즈·리포트)의 실패도 하루를 열어 둔다 (2026-08-01 실측).
# 그날까지 완주 판정은 **수집 레그만** 봤다. 그래서 08-01 실행에서 `social merge FAILED`가
# 로그에 찍혔는데도 하루가 done 으로 닫혔고, 산 데이터($3)가 리포트에 들어가지 못한 채
# 재시도도 돌지 않았다. 파생은 네트워크도 돈도 쓰지 않으므로 다시 돌리는 값이 싸다 --
# 열어 두지 않을 이유가 없었고, 닫아 두는 쪽의 값이 "오늘 수집이 조용히 증발"이었다.
$deriveFails = @()
function Set-Derive([string]$name, [bool]$ok, [string]$okMsg, [string]$failMsg) {
  if ($ok) { Log $okMsg } else { $script:deriveFails += $name; Log "!! $failMsg" }
}
if (Test-Path $statePath) {
  try {
    $prev = Get-Content $statePath -Raw -Encoding utf8 | ConvertFrom-Json
    if ($prev.legs) { foreach ($p in $prev.legs.PSObject.Properties) { $legs[$p.Name] = [string]$p.Value } }
    if ($prev.pending) { foreach ($p in $prev.pending.PSObject.Properties) { $pending[$p.Name] = @($p.Value) } }
    if ($prev.attempts) { $attempt = [int]$prev.attempts + 1 }
    if ($prev.startedAt) { $startedAt = [string]$prev.startedAt }
    if ($prev.done) {
      Log "=== daily_collect skip ($today) -- already completed at $($prev.completedAt), no-op ==="
      exit 0
    }
    Log "resume: run $today was interrupted after attempt $($attempt - 1) -- continuing"
  } catch { Log "!! run state unreadable ($statePath) -- starting fresh" }
}

function Save-State([bool]$done) {
  $obj = [ordered]@{
    date        = $today
    startedAt   = $startedAt
    attempts    = $attempt
    legs        = $legs
    pending     = $pending
    done        = $done
    completedAt = $(if ($done) { Get-Date -Format s } else { "" })
  }
  ($obj | ConvertTo-Json -Depth 5) | Set-Content -Path $statePath -Encoding utf8
}
# Targets for a collect leg: none if it finished, only the failures if it partly failed.
# NOTE: Log writes to the success stream, so inside a function its line would be folded
# into the return value (a log string then gets collected as if it were a market code).
# Every Log call in here must be discarded with $null = .
function Get-Targets([string]$leg, $all) {
  if ($legs[$leg] -eq "ok") { $null = Log "resume: $leg leg already complete -- skipped"; return @() }
  if ($pending.ContainsKey($leg) -and @($pending[$leg]).Count -gt 0) {
    $t = @($pending[$leg]); $null = Log "resume: $leg retrying $($t.Count) failed target(s) only"; return $t
  }
  return @($all)
}
function Set-LegResult([string]$leg, $failed) {
  $f = @($failed)
  if ($f.Count -eq 0) { $legs[$leg] = "ok"; if ($pending.ContainsKey($leg)) { $pending.Remove($leg) } }
  else { $legs[$leg] = "partial"; $pending[$leg] = $f }
  Save-State $false
}

# gap alarm -- a scheduler that quietly stops is the one failure this experiment cannot afford
$gapMsg = ""
$doneDates = @(Get-ChildItem $stateDir -Filter "run_*.json" -ErrorAction SilentlyContinue |
  Where-Object { $_.BaseName -ne "run_$today" } |
  ForEach-Object { try { $s = Get-Content $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json; if ($s.done) { [string]$s.date } } catch { } } |
  Sort-Object)
if ($doneDates.Count -gt 0) {
  $missed = ([datetime]$today - [datetime]$doneDates[-1]).Days - 1
  if ($missed -gt 0) { $gapMsg = "!! GAP: $missed day(s) with no completed run since $($doneDates[-1]) -- those dates are permanently missing" }
}

# keep the machine awake for the run. This PC sleeps after 15 min idle on AC, which is what
# killed the 2026-07-23 and 2026-07-24 runs part-way through the (slow) Apple leg.
$awake = $false
try {
  if (-not ("Ai.Power" -as [type])) {
    Add-Type -Namespace Ai -Name Power -MemberDefinition '[DllImport("kernel32.dll", SetLastError=true)] public static extern uint SetThreadExecutionState(uint esFlags);'
  }
  [Ai.Power]::SetThreadExecutionState([uint32]2147483649) | Out-Null   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
  $awake = $true
} catch { Log "!! keep-awake unavailable ($($_.Exception.Message)) -- run may be cut short by idle sleep" }

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

Log "=== daily_collect v2 start ($today) | repo=$repo | markets=$($markets.Count) tags=$($tagList.Count) budget=`$$dailyBudget | attempt=$attempt keepAwake=$awake ==="
if ($gapMsg) { Log $gapMsg }

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
  # A platform store is chart/<platform>/<cc>/ -- it holds market subdirectories, never .html
  # directly. The old flat layout was chart/<cc>/*.html. Only the latter shape is migratable,
  # and checking the shape (not a hard-coded name list) is what keeps this safe: on 2026-07-20
  # this block deleted the whole melon store because "melon" was not in the known list, so
  # chart/melon/kr/ was treated as a stray market dir and removed. Never trust the name alone.
  $known = @("spotify", "apple", "youtube", "melon", "shazam")
  foreach ($dir in @(Get-ChildItem $chartRoot -Directory -ErrorAction SilentlyContinue)) {
    if ($known -contains $dir.Name) { continue }
    $hasSubDirs = @(Get-ChildItem $dir.FullName -Directory -ErrorAction SilentlyContinue).Count -gt 0
    $htmls = @(Get-ChildItem "$($dir.FullName)\*.html" -ErrorAction SilentlyContinue)
    if ($hasSubDirs -or $htmls.Count -eq 0) {
      Log "!! chart/$($dir.Name) looks like a platform store, not a legacy market dir -- left untouched"
      continue
    }
    $dest = Join-Path (Join-Path $chartRoot "spotify") $dir.Name
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $htmls | Move-Item -Destination $dest -Force
    Remove-Item $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    Log "migrated chart/$($dir.Name) -> chart/spotify/$($dir.Name)"
  }
}

# 1) free chart collect -- 3 platform rails (D-016): Kworb Spotify + Apple official RSS + Kworb YouTube
# 2026-07-30 재시도 감사: 재시도는 collect/collect-apple 안(--attempts, 지수 백오프)에 있고,
# 여기서는 **소진됐을 때의 원인을 로그에 남긴다**. 이전엔 2>$null이 사유를 삼켜 "FAILED (skipped)"만
# 남았고, 원인을 찾으려면 별도 재현이 필요했다. $? 대신 $LASTEXITCODE를 보는 이유는 stderr를
# 리다이렉트하면 PS 5.1이 종료코드 0에도 $?를 false로 만들기 때문이다(sonic 레그 주석과 같은 함정).
$errFile = Join-Path $env:TEMP "ai_collect_err.txt"
$env:PYTHONPATH = "modules/chart-history/src"
$targetsM = @(Get-Targets "spotify" $markets)
if ($targetsM.Count -gt 0) {
  $okM = 0; $failedM = @()
  foreach ($cc in $targetsM) {
    $ccU = $cc.ToUpper()
    python -m chart_history collect --url "https://kworb.net/spotify/country/${cc}_daily.html" --store "data/live/chart/spotify/$cc" --country $ccU --platform spotify --chart-name "Spotify $ccU Daily" 2>$errFile | Out-Null
    if ($LASTEXITCODE -eq 0) { $okM++ } else { $failedM += $cc; Log "!! chart spotify/$cc collect FAILED (skipped) -- $(Get-Content $errFile -Tail 1 -ErrorAction SilentlyContinue)" }
  }
  Set-LegResult "spotify" $failedM
  Log "spotify charts: $okM ok, $($failedM.Count) failed of $($targetsM.Count) markets"
}
$appleMarkets = @($cfg.apple_markets)
$targetsA = @(Get-Targets "apple" $appleMarkets)
if ($targetsA.Count -gt 0) {
  $okA = 0; $failedA = @()
  # 2026-07-30 실측: 49개를 연달아 때리면 9개가 실패하고(kr 포함 — sonic 코호트의 소스다)
  # 몇 초 뒤 재시도하면 전부 성공한다. 재시도는 collect-apple 안으로 들어갔고(--attempts),
  # 여기서는 **소진됐을 때의 원인을 로그에 남긴다** — 이전엔 2>$null이 사유를 삼켜
  # "FAILED (skipped)"만 남았고, 그래서 원인을 찾는 데 별도 재현이 필요했다.
  foreach ($cc in $targetsA) {
    python -m chart_history collect-apple --storefront $cc --store "data/live/chart/apple/$cc" 2>$errFile | Out-Null
    if ($LASTEXITCODE -eq 0) { $okA++ }
    else {
      $failedA += $cc
      $why = (Get-Content $errFile -Tail 1 -ErrorAction SilentlyContinue)
      Log "!! chart apple/$cc collect FAILED (skipped) -- $why"
    }
  }
  Set-LegResult "apple" $failedA
  Log "apple charts: $okA ok, $($failedA.Count) failed of $($targetsA.Count) storefronts (official RSS)"
}
$ytMarkets = @($cfg.youtube_markets)
$targetsY = @(Get-Targets "youtube" $ytMarkets)
if ($targetsY.Count -gt 0) {
  $okY = 0; $failedY = @()
  foreach ($cc in $targetsY) {
    $ccU = $cc.ToUpper()
    python -m chart_history collect --url "https://kworb.net/youtube/insights/${cc}_daily.html" --store "data/live/chart/youtube/$cc" --country $ccU --platform youtube --chart-name "YouTube $ccU Daily" 2>$errFile | Out-Null
    if ($LASTEXITCODE -eq 0) { $okY++ } else { $failedY += $cc; Log "!! chart youtube/$cc collect FAILED (skipped) -- $(Get-Content $errFile -Tail 1 -ErrorAction SilentlyContinue)" }
  }
  Set-LegResult "youtube" $failedY
  Log "youtube charts: $okY ok, $($failedY.Count) failed of $($targetsY.Count) markets"
}
# shazam (D-020): a discovery lens -- what people reach for their phone to identify.
# Kworb's shazam boards print no date, so collect falls back to the collection date
# and stamps date_source=collected in the snapshot metadata.
$shazamMarkets = @($cfg.shazam_markets)
$targetsS = @(Get-Targets "shazam" $shazamMarkets)
if ($targetsS.Count -gt 0) {
  $okS = 0; $failedS = @()
  foreach ($cc in $targetsS) {
    $ccU = $cc.ToUpper()
    python -m chart_history collect --url "https://kworb.net/charts/shazam/${cc}.html" --store "data/live/chart/shazam/$cc" --country $ccU --platform shazam --chart-name "Shazam $ccU Daily" 2>$errFile | Out-Null
    if ($LASTEXITCODE -eq 0) { $okS++ } else { $failedS += $cc; Log "!! chart shazam/$cc collect FAILED (skipped) -- $(Get-Content $errFile -Tail 1 -ErrorAction SilentlyContinue)" }
  }
  Set-LegResult "shazam" $failedS
  Log "shazam charts: $okS ok, $($failedS.Count) failed of $($targetsS.Count) markets (discovery lens)"
}

# 1.5) live chart-history report -- latest snapshot per platform/market, 3-platform cross view (D-016)
$homeMarket = "KR"; if ($cfg.home_market) { $homeMarket = ([string]$cfg.home_market).ToUpper() }
python -m chart_history analyze data/live/chart --latest --entities packages/entity-master/entities.json --watchlist $wlPath --geo-scope $homeMarket -o modules/chart-history/output/
Set-Derive "chart-report" $? "chart-history live report written (3-platform cross view, home=$homeMarket)" "chart-history analyze FAILED"

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
  # 🔴 시도 원장 (D-054). 예산은 **시도**로 세야 한다 -- 액터가 돌면 실패해도 돈이 나가는데
  # 예전 셈법은 성공만 셌다. 그 상태로 재시도를 켜면 실패 태그가 하루 4번 다시 돌아
  # 문서가 적어 둔 "일 상한 안"이 거짓이 된다. 성공은 파일이 증거이지만 실패는 증거를
  # 남기지 않으므로, 실행을 넘어 살아남는 원장을 따로 둔다.
  # 🔴 원장은 **스냅샷 디렉터리 밖**에 둔다 (2026-08-01 실측). 처음에는
  # `data/live/social/attempts_<date>.json` 이었는데, 그 디렉터리는 merge_social.py 가
  # `*.json` 으로 훑는 자리다 -- 원장이 스냅샷인 척 끼어들어 **머지가 통째로 죽었다**.
  # 스냅샷 디렉터리에는 스냅샷만 있어야 한다. 원장은 재개 상태와 같은 성격이므로 state 로.
  $attemptsPath = Join-Path $live "state\social_attempts_$today.json"
  $attempts = @{}
  # 옛 자리에 남아 있으면 그대로 이어받는다 -- 여기서 못 읽으면 그날 지출이 0으로 리셋되고
  # 재시도가 이미 산 태그를 다시 산다. 자리를 옮기는 변경에서 가장 비싼 실수가 그것이다.
  $legacyPath = Join-Path $live "social\attempts_$today.json"
  foreach ($p in @($attemptsPath, $legacyPath)) {
    if (-not (Test-Path $p)) { continue }
    try {
      # BOM 유무와 무관하게 읽는다 -- 예전 Set-Content -Encoding utf8 이 BOM을 붙였다.
      $prevA = [System.IO.File]::ReadAllText($p) | ConvertFrom-Json
      foreach ($q in $prevA.PSObject.Properties) { $attempts[$q.Name] = [int]$q.Value }
      break
    } catch { Log "!! social attempts ledger unreadable ($p) -- starting fresh (spend may be under-counted)" }
  }
  # 🔴 BOM 없이 쓴다. Windows PowerShell 5.1 의 `Set-Content -Encoding utf8` 은 BOM을 붙이고,
  # 파이썬 `json.loads` 는 BOM이 있는 utf-8 을 거부한다(utf-8-sig 가 아니면).
  function Save-Attempts {
    [System.IO.File]::WriteAllText($attemptsPath, ($attempts | ConvertTo-Json -Depth 3),
      (New-Object System.Text.UTF8Encoding($false)))
  }
  # 오늘 이미 쓴 돈 = 시도 총합. 성공/실패를 가리지 않는다.
  $spent = 0.0
  foreach ($v in $attempts.Values) { $spent += ($perTagUsd * [int]$v) }
  $okT = 0; $failT = 0; $skipT = 0; $failedTags = @()
  foreach ($tag in $fetchTags) {
    $out = "data/live/social/${today}_${tag}.json"
    # Already fetched today (kept or quarantined): never buy the same tag twice (D-018).
    # 지출은 위에서 시도 원장으로 이미 계상됐다 -- 여기서 또 더하면 이중 계상이 된다.
    if ((Test-Path $out) -or (Test-Path (Join-Path $live "quarantine\${today}_${tag}.json"))) {
      $skipT++; continue
    }
    if (($spent + $perTagUsd) -gt $dailyBudget) { Log "budget stop: spent `$$spent + `$$perTagUsd would exceed `$$dailyBudget -- remaining tags skipped (cumulative, retries included)"; break }
    # 시도를 **먼저** 기록한다. 여기서 스크립트가 죽어도 돈은 이미 나갔을 수 있다.
    $attempts[$tag] = [int]$attempts[$tag] + 1
    Save-Attempts
    $spent += $perTagUsd
    python -m fandom_pulse fetch --hashtag $tag --results-type reels --max-items $perTagItems --max-usd $perTagUsd -o $out
    if ($?) {
      $okT++
      # PII gate: REJECT -> quarantine (never joins the pipeline)
      python scripts/validate_snapshot.py $out | Out-Null
      if (-not $?) { Move-Item $out (Join-Path $live "quarantine") -Force; Log "!! PII gate REJECT: $out -> quarantine" }
    } else { $failT++; $failedTags += $tag; Log "!! social fetch FAILED: #$tag (attempt $($attempts[$tag]) of today)" }
  }
  Log "social fetched: $okT tags ok, $failT failed, $skipT already collected today (not re-paid) | attempts today `$$spent / `$$dailyBudget (failures included)"
  if ($failT -eq 0) {
    $legs["social"] = "ok"; $pending.Remove("social"); Save-State $false
  } else {
    # 유료 레그도 하루를 열어 둔다 (D-054 · 도메인 소유자 승인). 다음 시도는 실패한 태그만
    # 다시 산다 -- 성공한 태그는 파일이 있어 건너뛰고, 예산은 시도 원장이 누적으로 막는다.
    $legs["social"] = "partial"; $pending["social"] = @($failedTags); Save-State $false
  }
}

# 3) rebuild forward signal-series (watchlist attribution, D-013)
python scripts/merge_social.py data/live/social data/live/social_merged.json
Set-Derive "social-merge" $? "social merged+deduped" "social merge FAILED"
$env:PYTHONPATH = "modules/fandom-pulse/src"
python -m fandom_pulse signals data/live/social_merged.json --entities packages/entity-master/entities.json --watchlist packages/entity-master/watchlist.json -o data/live/social_series.json
Set-Derive "social-series" $? "social series rebuilt (sound+hashtag attribution)" "social series FAILED"

# 3.5) free YouTube rail (official API, ~12 units/day) -- D-014
$ytCache = Join-Path $repo "packages\entity-master\yt_channels.json"
$ytSeries = ""
if (Test-Path $ytCache) {
  New-Item -ItemType Directory -Force -Path (Join-Path $live "yt") | Out-Null
  $env:PYTHONPATH = "modules/yt-pulse/src"
  $ytFile = "data/live/yt/$today.json"
  $ytOk = $false
  if (Test-Path $ytFile) { Log "resume: yt snapshot $today already fetched -- skipped (API quota saved)"; $ytOk = $true }
  else {
    python -m yt_pulse fetch --channels $ytCache -o $ytFile
    if ($?) {
      python scripts/validate_snapshot.py $ytFile | Out-Null
      if (-not $?) { Move-Item $ytFile (Join-Path $live "quarantine") -Force; Log "!! PII gate REJECT: yt/$today.json -> quarantine" }
      else { $ytOk = $true }
    } else { Log "!! yt fetch FAILED (skipped)" }
  }
  if ($ytOk) {
    $legs["yt"] = "ok"; Save-State $false
    python -m yt_pulse signals data/live/yt -o data/live/yt_series.json
    if ($?) { $ytSeries = "data/live/yt_series.json"; Log "yt fetched + series rebuilt (official channels)" } else { Log "!! yt series FAILED" }
    python -m yt_pulse analyze data/live/yt -o modules/yt-pulse/output/
    Set-Derive "yt-report" $? "yt report written" "yt report FAILED"
  }
} else { Log "yt SKIPPED (no channel cache -- run yt_pulse resolve once)" }

# 3.6) sonic-profile (D-019/D-022): 30s previews -> numbers only, audio never stored.
# Cohort = Apple chart top-N + the watchlist. A distribution needs a population: the module's
# whole claim is "position within the distribution", which 11 tracks cannot support. The Apple
# chart is the cohort source because its naming matches the Apple Search API exactly, so track
# verification is near-perfect (measured 25/25 vs 72% when matching Kworb's romanized strings).
# Cost stays bounded because features are a property of the recording -- the track cache means
# only chart newcomers are ever downloaded again (measured: 3m20s cold, 8s warm).
# NOTE: these calls check $LASTEXITCODE, not $?. librosa writes warnings to stderr, and in
# PowerShell 5.1 redirecting a native command's stderr sets $? to false even when the exe
# exited 0 -- the leg would log FAILED while actually having succeeded. Exit code is the
# only reliable signal for a native process. Other legs get away with $? only because their
# commands stay silent on stderr.
$sonicToday = "data/live/sonic/$today.json"
$cohortPath = "data/live/sonic/cohort.json"
$cohortArg = @()
$cohortMarket = "kr"; if ($cfg.sonic_cohort_market) { $cohortMarket = [string]$cfg.sonic_cohort_market }
$cohortTop = 100; if ($cfg.sonic_cohort_top) { $cohortTop = [int]$cfg.sonic_cohort_top }
# 인코딩 짝은 스크립트 맨 위에서 이미 한 번 걸렸다(레그마다 다시 걸지 않는다).
if ($legs["sonic"] -eq "ok") { Log "resume: sonic leg already complete -- skipped" }
elseif (Test-Path $sonicToday) { Log "resume: sonic snapshot $today already fetched -- skipped" }
else {
  New-Item -ItemType Directory -Force -Path (Join-Path $live "sonic") | Out-Null
  $env:PYTHONPATH = "modules/sonic-profile/src"
  $env:PYTHONPATH = "modules/chart-history/src"
  python -m chart_history tracks --store "data/live/chart/apple/$cohortMarket" --top $cohortTop -o $cohortPath 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $cohortArg = @("--cohort", $cohortPath); Log "sonic cohort: apple/$cohortMarket top $cohortTop" }
  else { $cohortArg = @(); Log "!! sonic cohort build FAILED -- watchlist only" }
  $env:PYTHONPATH = "modules/sonic-profile/src"
  python -m sonic_profile fetch --watchlist $wlPath @cohortArg -o $sonicToday 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $legs["sonic"] = "ok"; Save-State $false; Log "sonic previews fetched (features only, audio discarded)" }
  else { Log "!! sonic fetch FAILED (exit $LASTEXITCODE, skipped)" }
}
if (Test-Path $sonicToday) {
  $env:PYTHONPATH = "modules/sonic-profile/src"
  python -m sonic_profile signals data/live/sonic -o data/live/sonic_series.json 2>$null | Out-Null
  Set-Derive "sonic-series" ($LASTEXITCODE -eq 0) "sonic series rebuilt" "sonic series FAILED (exit $LASTEXITCODE)"
  python -m sonic_profile analyze data/live/sonic --watchlist $wlPath -o modules/sonic-profile/output/ 2>$null | Out-Null
  Set-Derive "sonic-report" ($LASTEXITCODE -eq 0) "sonic report written" "sonic report FAILED (exit $LASTEXITCODE)"
}

# 3.7) genre-impulse (D-035): impulse ledger x daily sonic cohort -> monitor report (offline, no cost)
if (Test-Path $sonicToday) {
  $env:PYTHONPATH = "modules/genre-impulse/src;modules/sonic-profile/src"
  python -m genre_impulse analyze --sonic data/live/sonic --watchlist $wlPath -o modules/genre-impulse/output/ 2>$null | Out-Null
  Set-Derive "genre-impulse" ($LASTEXITCODE -eq 0) "genre-impulse report written" "genre-impulse FAILED (exit $LASTEXITCODE)"
}

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
Set-Derive "bridge" $? "bridge report written (forward, watchlist profile)" "bridge FAILED"
node apps/dashboard/scripts/collect-reports.mjs
Set-Derive "dashboard" $? "dashboard reports.json refreshed" "dashboard collect FAILED"

# 5) summary line: coverage + social-led / social-only counts to watch over time
python scripts/bridge_summary.py modules/signal-bridge/output/report.json 2>$null | ForEach-Object { Log $_ }

# 6) backup -- layer-1 originals (chart HTML, paid social snapshots, sonic features, spend
#    ledger) to a private object-storage bucket. Free, offline-deterministic, incremental:
#    a day whose content did not change is skipped, so the daily cost is ~1.2MB.
#
#    Not configured = not enabled. data/live leaves this machine only after the owner sets
#    the two secrets, and that act IS the approval -- the script never guesses a target.
#    Once configured, a backup failure holds the day open like any derive step: "believed
#    uploaded but empty" is the one failure a backup cannot afford, and the retry is free.
#    Run `python scripts/backup_live.py --verify` to cross-check the remote against the
#    manifest (it does not trust the manifest alone).
if ($env:SUPABASE_URL -and $env:SUPABASE_SERVICE_KEY) {
  python scripts/backup_live.py 2>$null | ForEach-Object { Log $_ }
  Set-Derive "backup" ($LASTEXITCODE -eq 0) "backup leg ok" "backup FAILED (exit $LASTEXITCODE) -- layer-1 originals are NOT safe"
} else {
  Log "backup skipped -- SUPABASE_URL / SUPABASE_SERVICE_KEY not set (nothing left this machine)"
}

# mark the day complete -- but NOT while a collect leg still has targets left to retry.
#
# 2026-07-30 감사에서 나온 결함: 여기서 Save-State $true 를 **무조건** 호출하고 있었다.
# 그래서 Set-LegResult 가 legs=partial 로 남긴 pending 타깃이 실제로는 한 번도 재시도되지
# 않았다 -- 2시간 뒤 다음 시도가 done=true 를 보고 "already completed, no-op" 으로 즉시
# 나갔기 때문이다. 재개 기계장치(D-018)는 스크립트가 **중간에 죽은** 경우에만 동작하고
# **부분 실패**에는 동작하지 않았다. 오늘 Apple 9개가 살아난 것은 재시도가 파이썬 안으로
# 들어갔기 때문이고, 여기 밖에서는 여전히 새는 구조였다.
#
# 상한을 두는 이유: 진짜로 사라진 시장(코드 폐지 등)을 무한히 재시도하면 그 날짜는
# 영원히 done 이 안 되고 GAP 경보가 매일 울린다. 4회 시도(=8시간) 뒤에는 결손을 결손으로
# 확정하고 무엇이 비었는지 로그에 남긴다.
# 2026-07-31 (D-054 · 도메인 소유자 승인): **유료 소셜도 하루를 열어 둔다.**
# 예전에는 무료 레그만 열어 뒀는데, 그 이유는 실패 태그를 하루 최대 4번 다시 사는 것이
# 돈에 관한 결정이기 때문이었다. 승인과 함께 **셈법의 구멍을 먼저 막았다**: 예산을
# 성공이 아니라 **시도**로 세고(액터가 돌면 실패해도 돈이 나간다) 그 원장을 실행 너머로
# 유지한다. 그래서 재시도를 켜도 하루 총액은 여전히 $dailyBudget 에서 멈춘다.
# 2026-08-01: derive steps count too. Until today only collect legs could hold the day open,
# so the 08-01 run logged "social merge FAILED" and still closed done -- the tags bought that
# morning ($3) never reached a report and no retry ever looked at them. Deriving is free and
# idempotent, so holding the day open for it costs a re-run and buys back the day's data.
$retryLegs = @("spotify", "apple", "youtube", "shazam", "social")
$stillPending = @($retryLegs | Where-Object { $pending.ContainsKey($_) -and @($pending[$_]).Count -gt 0 })
$maxAttempts = 4
if ($stillPending.Count -gt 0 -or $deriveFails.Count -gt 0) {
  $detail = ((@($stillPending | ForEach-Object { "$_=$(@($pending[$_]) -join '/')" }) +
              @($deriveFails | ForEach-Object { "derive:$_" })) -join ", ")
  if ($attempt -lt $maxAttempts) {
    Save-State $false
    Log "!! day left INCOMPLETE on purpose (attempt $attempt/$maxAttempts) -- pending: $detail. The next scheduled attempt retries only these."
  } else {
    Save-State $true
    Log "!! day marked complete WITH GAPS after $attempt attempts -- permanently missing for ${today}: $detail"
  }
} else {
  Save-State $true
}
Remove-Item $errFile -ErrorAction SilentlyContinue
if ($awake) { [Ai.Power]::SetThreadExecutionState([uint32]2147483648) | Out-Null }   # ES_CONTINUOUS -- release
Log "=== daily_collect v2 done ($today) | attempt=$attempt ==="
