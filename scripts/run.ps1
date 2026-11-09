# Запуск сервера разработки FloraIS.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = Join-Path (Get-Location) "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Виртуальное окружение не найдено. Сначала выполните .\scripts\setup.ps1"
}

Write-Host "FloraIS: http://127.0.0.1:8000/" -ForegroundColor Green
& $python manage.py runserver
