import argparse
import logging
import tempfile
import shutil
import mpyq
from pathlib import Path

# Configuración del logging básico para el sistema
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def extract_mod_text(mod_path: Path, output_dir: Path) -> bool:
    """
    Descomprime y extrae los documentos de texto traducibles (.txt)
    de un mod/mapa personalizado de StarCraft 2 usando mpyq.
    
    Args:
        mod_path (Path): La ruta hacia el contenedor .SC2Mod o .SC2Map.
        output_dir (Path): El directorio temporal de trabajo destino.
        
    Returns:
        bool: True si la operación fue un éxito y extrajo datos, False en error.
    """
    logging.info(f"Montando contenedor objetivo: {mod_path}")
    
    # === LIMPIEZA PRE-VUELO ESTRICTA ===
    if output_dir.exists():
        logging.info(f"Vaciando directorio de trabajo temporal residual: {output_dir}")
        try:
            shutil.rmtree(output_dir)
        except Exception as e:
            logging.error(f"No se pudo limpiar la carpeta temporal anterior: {e}")
            return False
            
    # Garantizar que el cascarón de la carpeta existe limpio de cara a la extracción
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if not mod_path.exists():
            logging.error(f"El archivo especificado no existe: {mod_path}")
            return False
            
        archive = mpyq.MPQArchive(str(mod_path))
    except Exception as e:
        logging.error(f"No se pudo cargar el contenedor binario usando mpyq: {e}")
        return False

    internal_files = []
    
    # 1. Intentar leer la tabla índice (listfile)
    try:
        listfile_data = archive.read_file('(listfile)')
        if listfile_data:
            internal_files.extend(listfile_data.decode('utf-8').splitlines())
    except Exception:
        pass

    # Plan de contingencia si el listfile está ofuscado o ausente
    if not internal_files:
        logging.warning("No se encontró '(listfile)' en el contenedor. Empleando heurística de búsqueda pasiva...")
        # Extraemos heurísticamente todos los archivos de texto probables
        fallback_strings = [
            "GameStrings.txt", "ObjectStrings.txt", "TriggerStrings.txt", 
            "ButtonStrings.txt", "SoundStrings.txt", "ShortcutStrings.txt",
            "RaceStrings.txt", "UIStrings.txt", "MathStrings.txt", "MapStrings.txt",
            "ConversationStrings.txt"
        ]
        for locale in ["enUS", "enGB"]:
            for fname in fallback_strings:
                internal_files.extend([
                    f"{locale}.SC2Data\\LocalizedData\\{fname}",
                    f"{locale}.SC2Data/LocalizedData/{fname}"
                ])
                
    # 2. Reclutar absolutamente todos los documentos de texto (.txt) ingleses
    text_files = set()
    for internal_path in internal_files:
        path_lower = internal_path.lower()
        if ('enus.sc2data' in path_lower or 'engb.sc2data' in path_lower) and \
           'localizeddata' in path_lower and path_lower.endswith('.txt'):
            text_files.add(internal_path)
            
    if not text_files:
        logging.warning("El escáner no encontró ninguna carpeta inglesa válida de LocalizedData en este Mod.")
        return False
        
    extracted_count = 0
    
    # 3. Preparar la estructura robusta del directorio temporal de trabajo
    temp_locale_dir = output_dir / "enUS"
    try:
        # Volcar permisos y limpiar/crear la carpeta de destino
        temp_locale_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"No se tienen derechos para crear el directorio de trabajo [{temp_locale_dir}]: {e}")
        return False
        
    logging.info(f"Directorio temporal configurado en: {temp_locale_dir}")
    
    # 4. Extracción individual controlada por bloque Exception
    for txt_file in text_files:
        try:
            file_data = archive.read_file(txt_file)
            if file_data:
                # Aislar el nombre base del archivo para evitar rutas relativas corruptas de Windows
                basename = Path(txt_file.replace('\\', '/')).name
                dest_path = temp_locale_dir / basename
                
                dest_path.write_bytes(file_data)
                logging.info(f"  [+] Documento extraído correctamente: {basename}")
                extracted_count += 1
            else:
                logging.warning(f"  [-] Archivo listado '{txt_file}' está vacío o corrupto internamente.")
        except Exception as e:
            logging.error(f"  [ERROR] Fallo IO crítico extrayendo la ruta interna '{txt_file}': {e}")
            
    logging.info(f"Proceso completado: Se volcaron {extracted_count} recursos para su traducción.")
    return extracted_count > 0

def main() -> None:
    parser = argparse.ArgumentParser(description="1ª Etapa del Pipeline: Extractor de textos base desde Mods/Mapas SC2.")
    parser.add_argument(
        "mod_path", 
        type=Path, 
        help="Ruta absoluta o relativa hacia el archivo .SC2Mod o .SC2Map a analizar."
    )
    parser.add_argument(
        "--workdir", 
        type=Path, 
        default=Path("../temp_workdir"), 
        help="Directorio temporal de volcado (por defecto: ../temp_workdir)."
    )
    args = parser.parse_args()
    
    # Cómputo de la ruta absoluta para el directorio de trabajo (Workdir)
    if args.workdir.is_absolute():
        workdir_resolved = args.workdir
    else:
        workdir_resolved = Path(__file__).resolve().parent / args.workdir
    
    logging.info("-" * 40)
    logging.info("INICIANDO MOTOR EXTRACCIÓN DE MODS")
    logging.info("-" * 40)
    
    extract_mod_text(args.mod_path, workdir_resolved)
    
if __name__ == "__main__":
    main()
