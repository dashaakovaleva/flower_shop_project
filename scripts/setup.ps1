# Полная подготовка окружения FloraIS (Windows PowerShell).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path "venv")) {
    Write-Host "Создание виртуального окружения..." -ForegroundColor Cyan
    python -m venv venv
}

$python = Join-Path (Get-Location) "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Не найден $python. Убедитесь, что Python 3.10+ установлен."
}

Write-Host "Установка зависимостей..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

Write-Host "Миграции..." -ForegroundColor Cyan
& $python manage.py migrate

Write-Host "Подготовка демонстрационных данных (3-5 минут)..." -ForegroundColor Cyan
& $python manage.py bootstrap_demo

Write-Host "Готово. Запуск: .\scripts\run.ps1" -ForegroundColor Green
Write-Host "Демо-аккаунты: admin/admin123, manager/manager123, client/client123"
