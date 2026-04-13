param(
  [string]$RepoDir = (Split-Path -Parent $PSScriptRoot),
  [string]$Branch = "main",
  [string]$Message = ""
)

$ErrorActionPreference = "Stop"

Set-Location $RepoDir

# Safety: never commit local secrets
if (Test-Path ".env") {
  git reset --quiet -- .env | Out-Null
}

git add -A | Out-Null
git reset --quiet -- .env | Out-Null

# If nothing staged, exit quietly
$staged = git diff --cached --name-only
if (-not $staged) {
  Write-Output "No changes to commit."
  exit 0
}

if ([string]::IsNullOrWhiteSpace($Message)) {
  $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm")
  $Message = "chore: auto sync $ts"
}

git commit -m "$Message" | Out-Null
git push origin $Branch | Out-Null

Write-Output "Pushed to $Branch."
