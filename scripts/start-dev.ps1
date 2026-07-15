param(
    [string]$Python = "python",
    [string]$Pnpm = "pnpm"
)

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Admin = Join-Path $Root "admin-web"
$Mini = Join-Path $Root "customer-miniapp"
$BundledNodeBin = "C:\Users\84114\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$BundledPnpm = "C:\Users\84114\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"

if ($Pnpm -eq "pnpm" -and (Test-Path $BundledPnpm)) {
    $Pnpm = $BundledPnpm
}
if ($Python -eq "python" -and (Test-Path (Join-Path $Backend ".venv\Scripts\python.exe"))) {
    $Python = Join-Path $Backend ".venv\Scripts\python.exe"
}

Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "cd '$Backend'; `$env:ADMIN_USERNAME='admin'; `$env:ADMIN_PASSWORD='admin123'; & '$Python' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "cd '$Root'; `$env:PATH='$BundledNodeBin;' + `$env:PATH; & '$Pnpm' --dir '$Admin' dev"
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "cd '$Root'; `$env:PATH='$BundledNodeBin;' + `$env:PATH; & '$Pnpm' --dir '$Mini' dev:h5"

Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Admin:   http://127.0.0.1:5173"
Write-Host "Mini H5: http://localhost:5174"
