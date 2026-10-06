param(
    [Parameter(Mandatory=$true)][string]$BuildPython,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'dist'))
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
if (-not $outputRoot.StartsWith($distRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Review output must be a new subdirectory of project/dist.'
}
if (Test-Path -LiteralPath $outputRoot) { throw 'Review directory exists; old builds must not be overwritten.' }
$runtimeSource = Join-Path $projectRoot 'runtimes\recognition\win-x64'
if (-not (Test-Path -LiteralPath (Join-Path $runtimeSource 'python\python.exe'))) { throw 'Prepared recognition runtime is missing.' }
$workRoot = Join-Path ([IO.Path]::GetTempPath()) ('vpa-review-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workRoot | Out-Null
Push-Location $projectRoot
try {
    & $BuildPython -m PyInstaller --noconfirm --clean --workpath (Join-Path $workRoot 'work') --distpath $outputRoot VirtualPianoArranger.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed. Partial output retained for diagnosis.' }
    $packageRoot = Join-Path $outputRoot 'VirtualPianoArranger'
    $runtimeParent = Join-Path $packageRoot 'runtimes\recognition'
    New-Item -ItemType Directory -Path $runtimeParent | Out-Null
    # Copy the prepared child runtime as data after collection. PyInstaller must
    # not analyse Python 3.11/native OMR DLLs as part of the Python 3.14 Qt host.
    Copy-Item -LiteralPath $runtimeSource -Destination $runtimeParent -Recurse
    & $BuildPython verify_packaged.py $packageRoot
    if ($LASTEXITCODE -ne 0) { throw 'EXE verification failed. Do not launch as a successful build.' }
    Write-Output "Review EXE verified: $(Join-Path $packageRoot 'VirtualPianoArranger.exe')"
} finally {
    Pop-Location
}
