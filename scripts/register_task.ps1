# register_task.ps1 -- register/refresh the "AI-daily-collect" scheduled task (D-018).
# ASCII-only on purpose (same reason as daily_collect.ps1: PS 5.1 misparses UTF-8-without-BOM).
#
# The scheduler settings are part of the experiment's contract, so they live in the repo
# instead of only inside Windows. Running this is idempotent -- it replaces the task
# definition with exactly what is written here.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_task.ps1 -WhatIf
#
# Why each setting exists -> docs/EXPERIMENT-forward-leading.md, collection-reliability section (D-018).
# Missed days are permanent gaps (charts/IG only ever serve "today"), so the task is
# tuned to try often; daily_collect.ps1 makes every retry idempotent and free.

param(
  [string]$TaskName = "AI-daily-collect",
  [string]$At = "09:00",
  [int]$RepeatHours = 2,
  [int]$RepeatWindowHours = 12,
  [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
if ($PSScriptRoot) { $scriptDir = $PSScriptRoot } else { $scriptDir = Split-Path -Parent $PSCommandPath }
$repo = Split-Path -Parent $scriptDir
$target = Join-Path $scriptDir "daily_collect.ps1"
if (-not (Test-Path $target)) { throw "collector not found: $target" }

$user = "$env:USERDOMAIN\$env:USERNAME"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$target`"" `
  -WorkingDirectory $repo

# Daily at $At, then retry every $RepeatHours for $RepeatWindowHours -- a run that dies
# mid-way gets picked up the same day. Retries are cheap: daily_collect resumes from
# run state and never re-pays for a tag it already fetched today.
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$repeat = (New-ScheduledTaskTrigger -Once -At $At `
    -RepetitionInterval (New-TimeSpan -Hours $RepeatHours) `
    -RepetitionDuration (New-TimeSpan -Hours $RepeatWindowHours)).Repetition
$trigger.Repetition = $repeat

$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -WakeToRun `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -DontStopOnIdleEnd `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 20)

# Interactive: the collector reads user-scope env vars (APIFY_TOKEN, YOUTUBE_API_KEY,
# FIRECRAWL_API_KEY). A non-interactive principal (S4U) may start without the user hive
# loaded, which would silently drop the keys -- so the task stays logon-bound on purpose.
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

if ($WhatIf) {
  Write-Output "task        : $TaskName"
  Write-Output "runs        : daily $At, then every ${RepeatHours}h for ${RepeatWindowHours}h"
  Write-Output "action      : powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$target`""
  Write-Output "workingDir  : $repo"
  Write-Output "principal   : $user (Interactive, Limited)"
  Write-Output "settings    : StartWhenAvailable, WakeToRun, AllowStartIfOnBatteries,"
  Write-Output "              DontStopIfGoingOnBatteries, DontStopOnIdleEnd,"
  Write-Output "              IgnoreNew, limit 3h, restart 3x/20m"
  Write-Output "(WhatIf: nothing registered)"
  return
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Output "registered: $TaskName | state=$($t.State) | next=$($i.NextRunTime)"
Write-Output "  StartWhenAvailable=$($t.Settings.StartWhenAvailable) WakeToRun=$($t.Settings.WakeToRun) StopIfGoingOnBatteries=$($t.Settings.StopIfGoingOnBatteries)"
Write-Output "  repetition=$($t.Triggers[0].Repetition.Interval) for $($t.Triggers[0].Repetition.Duration) | restart=$($t.Settings.RestartCount)x/$($t.Settings.RestartInterval)"
