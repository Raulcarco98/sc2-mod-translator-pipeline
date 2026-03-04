<#
.SYNOPSIS
Ejecuta la tubería completa (pipeline) de traducción de los archivos base de StarCraft 2.

.DESCRIPTION
Este script orquesta los tres módulos de Python secuencialmente. Gestiona excepciones y detiene
completamente la ejecución si encuentra errores críticos, garantizando que no se generen artefactos
(como el JSON final) a partir de datos corruptos o incompletos.

Pasos automáticos:
1. Activa el entorno virtual.
2. Ejecuta extractor_base.py leyendo de mapas_originales/
3. Ejecuta generador_diccionario.py si el paso 1 tiene éxito.
4. Ejecuta optimizador_json.py si el paso 2 tiene éxito.
#>

$ErrorActionPreference = "Stop"

try {
    Write-Host "[*] Activando entorno virtual..." -ForegroundColor Cyan
    . (Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1")
    
    Write-Host "[*] Buscando archivos MPQ (.SC2Mod, .MPQ) en la carpeta 'mapas_originales/..." -ForegroundColor Yellow
    $files = Get-ChildItem -Path (Join-Path $PSScriptRoot "mapas_originales") -Include *.SC2Mod, *.MPQ -Recurse -File
    
    if (-not $files) {
        throw "No se encontraron archivos .SC2Mod o .MPQ en la carpeta 'mapas_originales/'. El script requiere datos fuente para iniciar el pipeline."
    }
    
    $filePaths = $files | Select-Object -ExpandProperty FullName
    
    Write-Host "`n======================================================="
    Write-Host " [PASO 1/3] Ejecutando Extractor Base (extractor_base.py)" -ForegroundColor Green
    Write-Host "======================================================="
    & python (Join-Path $PSScriptRoot "src\extractor_base.py") $filePaths
    if ($LASTEXITCODE -ne 0) { throw "Fallo crítico devuelto por extractor_base.py." }
    
    Write-Host "`n======================================================="
    Write-Host " [PASO 2/3] Generando Diccionario (generador_diccionario.py)" -ForegroundColor Green
    Write-Host "======================================================="
    & python (Join-Path $PSScriptRoot "src\generador_diccionario.py")
    if ($LASTEXITCODE -ne 0) { throw "Fallo crítico devuelto por generador_diccionario.py." }
    
    Write-Host "`n======================================================="
    Write-Host " [PASO 3/3] Optimizando JSON (optimizador_json.py)" -ForegroundColor Green
    Write-Host "======================================================="
    & python (Join-Path $PSScriptRoot "src\optimizador_json.py")
    if ($LASTEXITCODE -ne 0) { throw "Fallo crítico devuelto por optimizador_json.py." }
    
    Write-Host "`n[+] Operación Exitosa. El pipeline ha finalizado sin errores críticos y el glosario_saneado.json inmutable se generó." -ForegroundColor DarkGreen

}
catch {
    Write-Host "`n[ERROR CRÍTICO] La ejecución del pipeline se detuvo." -ForegroundColor Red
    Write-Host "Detalle de la excepción capturada: $_" -ForegroundColor Red
    # Limpiamos el código de salida de forma proactiva
    exit 1
}
