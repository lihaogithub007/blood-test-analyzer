param(
  [string]$RepoDir = (Split-Path -Parent $PSScriptRoot),
  [string]$Branch = "main",
  [int]$IntervalSeconds = 300
)

# Every $IntervalSeconds (default 300 = 5 min), run auto_commit_push.ps1 if there are changes.
$ErrorActionPreference = "Stop"
$auto = Join-Path $PSScriptRoot "auto_commit_push.ps1"

while ($true) {
  Start-Sleep -Seconds $IntervalSeconds
  & $auto -RepoDir $RepoDir -Branch $Branch
}
