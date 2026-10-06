param(
    [Parameter(Mandatory=$true)][string]$PythonHome,
    [Parameter(Mandatory=$true)][string]$SitePackages
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeTarget = Join-Path $projectRoot 'runtimes\recognition\win-x64'
if (Test-Path -LiteralPath $runtimeTarget) { throw 'Runtime already exists; do not overwrite it.' }
$pythonSource = (Resolve-Path -LiteralPath $PythonHome).Path
$packagesSource = (Resolve-Path -LiteralPath $SitePackages).Path
if (-not (Test-Path -LiteralPath (Join-Path $pythonSource 'python311.dll'))) { throw 'Python 3.11 x64 installation required.' }
if (-not (Test-Path -LiteralPath (Join-Path $packagesSource 'homr\main.py'))) { throw 'HOMR installation missing.' }
# This is a local resource copy, not an installation or a venv move. Retain
# distribution metadata/licenses; no symlinks or user projects are copied.
if (Get-ChildItem -LiteralPath $packagesSource -Recurse -Attributes ReparsePoint | Where-Object LinkType) { throw 'Symbolic links and junctions are not supported.' }
New-Item -ItemType Directory -Path $runtimeTarget | Out-Null
Copy-Item -LiteralPath $pythonSource -Destination (Join-Path $runtimeTarget 'python') -Recurse
Copy-Item -LiteralPath $packagesSource -Destination (Join-Path $runtimeTarget 'site-packages') -Recurse
$isolatedPython = Join-Path $runtimeTarget 'python\python.exe'
$isolatedPackages = Join-Path $runtimeTarget 'site-packages'
& $isolatedPython -I -c 'import sys;sys.path.insert(0,sys.argv[1]);import homr.main;print("HOMR runtime imports OK")' $isolatedPackages
if ($LASTEXITCODE -ne 0) { throw 'Runtime import check failed; incomplete folder retained for diagnosis.' }
Write-Output 'Local runtime prepared. EXE packaging, redistribution review and macOS remain separate gates.'
