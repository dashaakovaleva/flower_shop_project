# Проверка проекта: system check, миграции и тесты.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = Join-Path (Get-Location) "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Виртуальное окружение не найдено. Сначала выполните .\scripts\setup.ps1"
}

Write-Host "1/3 System check..." -ForegroundColor Cyan
& $python manage.py check

Write-Host "2/3 Проверка миграций..." -ForegroundColor Cyan
& $python manage.py makemigrations --check --dry-run

Write-Host "3/3 Тесты..." -ForegroundColor Cyan
& $python manage.py test shop.tests -v 1

Write-Host "Все проверки пройдены." -ForegroundColor Green
