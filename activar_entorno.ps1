<#
.SYNOPSIS
Activa el entorno virtual del proyecto traductor-mods.

.DESCRIPTION
Este script es una ayuda (wrapper) para activar rápidamente el entorno virtual local "venv" en PowerShell, 
aplicando buenas prácticas de administración y asegurando que las dependencias de Python estén disponibles.
#>

$VenvPath = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"

if (Test-Path $VenvPath) {
    Write-Host "[*] Activando el entorno virtual de traductor-mods..." -ForegroundColor Cyan
    & $VenvPath
    Write-Host "[+] Entorno activado exitosamente. Ahora puedes ejecutar los scripts de la carpeta src/." -ForegroundColor Green
} else {
    Write-Host "[ERROR] No se ha encontrado el entorno virtual en la ruta esperada: $VenvPath" -ForegroundColor Red
    Write-Host "Por favor, asegúrate de que el entorno fue creado con 'python -m venv venv'." -ForegroundColor Yellow
}
