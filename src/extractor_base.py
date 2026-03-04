import argparse
import logging
from pathlib import Path
from typing import List, Optional
import mpyq

# Configuración del registro (logging) para un entorno de producción o desarrollo profesional
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def extract_game_strings(mpq_path: Path, output_base_dir: Path) -> bool:
    """
    Abre un archivo MPQ (SC2Mod/SC2Map), busca GameStrings.txt en las carpetas enUS y esES,
    y extrae estos documentos al directorio indicado manteniendo la estructura base.

    Args:
        mpq_path (Path): Ruta al contenedor MPQ.
        output_base_dir (Path): Directorio donde se almacenarán las extracciones.

    Returns:
        bool: True si se extrajo al menos un archivo válido, False en caso contrario o error.
    """
    logging.info(f"Procesando contenedor: {mpq_path}")
    
    try:
        archive = mpyq.MPQArchive(str(mpq_path))
    except Exception as e:
        logging.error(f"No se pudo abrir el contenedor MPQ '{mpq_path}': {e}")
        return False

    try:
        output_base_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"No se pudo crear el directorio de salida '{output_base_dir}': {e}")
        return False

    locales_comunes = ['enUS', 'esES']
    archivos_encontrados = False
    archivos_internos: List[str] = []

    # Intento 1: Leer el listfile interno
    try:
        listfile_data = archive.read_file('(listfile)')
        if listfile_data:
            archivos_internos.extend(listfile_data.decode('utf-8').splitlines())
    except Exception:
        pass

    # Intento 2: Búsqueda manual (hardcoded) para MPQs sin listfile
    if not archivos_internos:
        for locale in locales_comunes:
            archivos_internos.extend([
                f"{locale}.SC2Data\\LocalizedData\\GameStrings.txt",
                f"{locale}.SC2Data/LocalizedData/GameStrings.txt",
            ])

    # Filtrar solo archivos GameStrings.txt enUS/esES
    for ruta_interna in set(archivos_internos):
        ruta_lower = ruta_interna.lower()
        if 'gamestrings.txt' in ruta_lower:
            locale_detectado = 'enUS' if 'enus' in ruta_lower else ('esES' if 'eses' in ruta_lower else None)
            
            if locale_detectado:
                logging.info(f"  Encontrado en MPQ: {ruta_interna}")
                try:
                    file_data = archive.read_file(ruta_interna)
                    if file_data:
                        salida_carpeta = output_base_dir / locale_detectado
                        salida_carpeta.mkdir(parents=True, exist_ok=True)
                        
                        # Prevenir colisiones de nombres anteponiendo el archivo origen
                        mpq_nombre = mpq_path.name.replace('.', '_')
                        ruta_salida = salida_carpeta / f"{mpq_nombre}_GameStrings.txt"
                        
                        ruta_salida.write_bytes(file_data)
                        logging.info(f"  Guardado en local: {ruta_salida}")
                        archivos_encontrados = True
                    else:
                        logging.warning(f"  El archivo '{ruta_interna}' está vacío o inaccesible.")
                except Exception as e:
                    logging.error(f"  Falló la extracción de '{ruta_interna}': {e}")

    if not archivos_encontrados:
        logging.warning(f"No se extrajo ningún archivo GameStrings.txt válido de '{mpq_path}'.")
    return archivos_encontrados

def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae textos de localización (enUS, esES) de contenedores MPQ.")
    parser.add_argument(
        "mpq_paths", 
        nargs="+", 
        type=Path, 
        help="Rutas a los archivos MPQ / .SC2Mod / .SC2Map."
    )
    parser.add_argument(
        "-o", "--output", 
        type=Path,
        default=Path("../extracciones_oficiales"), 
        help="Directorio base de salida."
    )
    args = parser.parse_args()

    for path in args.mpq_paths:
        if path.is_dir():
            logging.warning(f"Se omitió el directorio '{path}'. Proporcione rutas a archivos.")
            continue
        if not path.exists():
            logging.error(f"La ruta especificada no existe: '{path}'.")
            continue
            
        extract_game_strings(path, args.output)

if __name__ == "__main__":
    main()
