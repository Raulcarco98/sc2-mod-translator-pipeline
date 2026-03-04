import sys
from pathlib import Path

def limpiar_extracciones(ruta_base: str = "extracciones_mapas"):
    ruta = Path(ruta_base)
    
    if not ruta.exists() or not ruta.is_dir():
        print(f"Error: La carpeta '{ruta_base}' no existe o no es un directorio.")
        return
    
    print(f"Iniciando limpieza en: {ruta.resolve()}")
    carpetas_procesadas = 0
    archivos_movidos = 0
    carpetas_eliminadas = 0
    
    # Rglob para buscar todas las carpetas 'localizeddata' de forma recursiva.
    # Usamos list() para evitar problemas al modificar el árbol de directorios mientras iteramos.
    directorios_localized = list(ruta.rglob("localizeddata"))
    
    for carpeta_localized in directorios_localized:
        if not carpeta_localized.is_dir():
            continue
            
        print(f"\nProcesando carpeta: {carpeta_localized}")
        carpeta_padre = carpeta_localized.parent
        carpetas_procesadas += 1
        
        # Buscar todos los archivos de texto (.txt) dentro de la carpeta
        archivos_texto = list(carpeta_localized.glob("*.txt"))
        
        if not archivos_texto:
            print("  No se encontraron archivos de texto (.txt).")
        else:
            for archivo in archivos_texto:
                if archivo.is_file():
                    destino = carpeta_padre / archivo.name
                    if destino.exists():
                        print(f"  [Advertencia] El archivo {destino.name} ya existe en el directorio padre, será reemplazado.")
                    
                    try:
                        # replace() mueve el archivo y sobreescribe si ya existe en el destino (Python 3.3+)
                        archivo.replace(destino)
                        print(f"  Movido: {archivo.name} -> {carpeta_padre.name}/")
                        archivos_movidos += 1
                    except Exception as e:
                        print(f"  [Error] No se pudo mover {archivo.name}: {e}")
        
        # Intentar eliminar la carpeta localizeddata
        # rmdir() fallará con OSError si la carpeta no está completamente vacía
        try:
            carpeta_localized.rmdir()
            print(f"  Eliminada carpeta vacía: {carpeta_localized}")
            carpetas_eliminadas += 1
        except OSError:
            # Si no se elimina, mostramos cuántos elementos han quedado dentro impidiendo el borrado
            elementos_restantes = list(carpeta_localized.iterdir())
            print(f"  [Atención] No se pudo eliminar '{carpeta_localized.name}' porque aún contiene {len(elementos_restantes)} elemento(s) no soportado(s).")

    print("\n" + "="*40)
    print("Resumen de la operación:")
    print(f"- Carpetas 'localizeddata' procesadas: {carpetas_procesadas}")
    print(f"- Archivos de texto movidos: {archivos_movidos}")
    print(f"- Carpetas 'localizeddata' eliminadas: {carpetas_eliminadas}")
    print("="*40)

if __name__ == "__main__":
    limpiar_extracciones()
