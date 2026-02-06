param(
    [string]$PythonExe = "python",
    [switch]$NoVenv,
    [switch]$UpgradePip
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

function Resolve-Python {
    param([string]$Exe)
    try {
        & $Exe --version | Out-Null
        return $Exe
    } catch {
        throw "Python executable '$Exe' was not found. Install Python 3 and retry."
    }
}

$python = Resolve-Python -Exe $PythonExe
$requirementsFile = Join-Path $repoRoot "requirements.txt"

if (-not (Test-Path $requirementsFile)) {
    throw "Missing requirements file: $requirementsFile"
}

if ($NoVenv) {
    if ($UpgradePip) {
        & $python -m pip install --upgrade pip
    }
    & $python -m pip install -r $requirementsFile
    Write-Host "Dependencies installed in current Python environment."
    exit 0
}

$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment in $venvDir"
    & $python -m venv $venvDir
}

if ($UpgradePip) {
    & $venvPython -m pip install --upgrade pip
}

& $venvPython -m pip install -r $requirementsFile

Write-Host ""
Write-Host "Setup complete."
Write-Host "Activate with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Run app with:"
Write-Host "  python main.py run --scenario base"
