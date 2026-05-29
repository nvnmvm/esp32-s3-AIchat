param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryUrl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath ".git")) {
    git init
}

$branch = git branch --show-current
if ([string]::IsNullOrWhiteSpace($branch)) {
    git checkout -b main
} elseif ($branch -ne "main") {
    git branch -M main
}

git add .
git commit -m "Initial ESP32 AI voice cloud service"

$remote = git remote
if ($remote -contains "origin") {
    git remote set-url origin $RepositoryUrl
} else {
    git remote add origin $RepositoryUrl
}

git push -u origin main
