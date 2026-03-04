import json
import logging
import argparse
import os
import shutil
import tempfile
import mpyq
from pathlib import Path

# Configuración de registro
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def extraer_textos_mpq(archivo_sc2: Path, temp_dir: Path) -> list[Path]:
    """Extrae documentos de texto traducibles (.txt) de un mod/mapa SC2 usando mpyq."""
    export_path = temp_dir / archivo_sc2.name
    
    # Manejar Component Directories (Carpetas) copiándolas directamente
    if archivo_sc2.is_dir():
        logging.info(f"Detectado Component Directory (Directorio Puro): {archivo_sc2.name}")
        rutas_extraidas = []
        for locale in ["enUS", "enGB"]:
            origen_en = archivo_sc2 / f"{locale}.SC2Data" / "LocalizedData"
            if origen_en.exists():
                destino_en = export_path / f"{locale}.SC2Data" / "LocalizedData"
                destino_en.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(origen_en, destino_en, dirs_exist_ok=True)
                rutas_extraidas.extend(list(destino_en.glob("*.txt")))
                logging.info(f"Copiado árbol de localización local: {origen_en}")
        if not rutas_extraidas:
            logging.warning(f"No se encontró estructura enUS/enGB en la carpeta {archivo_sc2.name}.")
        return rutas_extraidas
            
    # Manejar archivos MPQ nativos (.SC2Mod o .SC2Map binario)
    logging.info(f"Extrayendo archivo MPQ comprimido mediante mpyq: {archivo_sc2.name}")
    try:
        archive = mpyq.MPQArchive(str(archivo_sc2))
    except Exception as e:
        logging.error(f"Fallo grave cargando MPQArchive en {archivo_sc2.name}: {e}")
        return []

    internal_files = []
    
    try:
        listfile_data = archive.read_file('(listfile)')
        if listfile_data:
            internal_files.extend(listfile_data.decode('utf-8').splitlines())
    except Exception:
        pass

    if not internal_files:
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
                
    text_files = set()
    for internal_path in internal_files:
        path_lower = internal_path.lower()
        if ('enus.sc2data' in path_lower or 'engb.sc2data' in path_lower) and \
           'localizeddata' in path_lower and path_lower.endswith('.txt'):
            text_files.add(internal_path)
            
    if not text_files:
        logging.warning(f"  -> El contenedor {archivo_sc2.name} no devolvió localizaciones en inglés.")
        return []
        
    destino_en = export_path / "enUS.SC2Data" / "LocalizedData"
    destino_en.mkdir(parents=True, exist_ok=True)
    rutas_extraidas = []
    
    extracted_count = 0
    for txt_file in text_files:
        try:
            file_data = archive.read_file(txt_file)
            if file_data:
                basename = Path(txt_file.replace('\\', '/')).name
                dest_path = destino_en / basename
                dest_path.write_bytes(file_data)
                rutas_extraidas.append(dest_path)
                extracted_count += 1
        except Exception as e:
            logging.error(f"Error extrayendo '{txt_file}': {e}")
            
    if extracted_count > 0:
        logging.info(f"  [+] Documentos extraídos con éxito: {extracted_count}")
            
    return rutas_extraidas

def cosechar_claves(archivos_txt: list[Path]) -> set[str]:
    """Descifra los archivos TXT y genera un Set matemático único de las llaves."""
    conjunto_claves = set()
    for txt in archivos_txt:
        try:
            with txt.open('r', encoding='utf-8-sig') as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("//"):
                        parts = line.strip().split("=", 1)
                        if len(parts) == 2:
                            conjunto_claves.add(parts[0].strip())
        except Exception as e:
            logging.error(f"Error procesando el archivo de texto {txt.name}: {e}")
    return conjunto_claves

def main():
    parser = argparse.ArgumentParser(description="Purgador Quirúrgico de Caché por Extracción MPQ")
    parser.add_argument(
        "--target", 
        type=Path, 
        default=Path("Nueva carpeta"), 
        help="Directorio que contiene los .SC2Mod o .SC2Map objetivos."
    )
    parser.add_argument(
        "--estado", 
        type=Path, 
        default=Path("estado_traduccion.json"), 
        help="Ruta a la caché JSON de traducciones."
    )
    args = parser.parse_args()

    directorio_target = args.target.resolve()
    archivo_estado = args.estado.resolve()

    if not directorio_target.exists() or not directorio_target.is_dir():
        logging.error(f"El directorio objetivo '{directorio_target}' no existe o no es una carpeta.")
        return
        
    if not archivo_estado.exists():
        logging.error(f"El caché '{archivo_estado}' no se pudo localizar.")
        return

    # Buscar mods y mapas
    archivos_sc2 = list(directorio_target.glob("*.SC2Mod")) + list(directorio_target.glob("*.SC2Map"))
    if not archivos_sc2:
        logging.warning("No se detectaron archivos SC2Mod o SC2Map en la carpeta especificada.")
        return

    # Iniciar la infraestructura temporal
    dir_temporal_extraccion = Path(tempfile.mkdtemp(prefix="sc2_limpiador_"))
    logging.info(f"Directorio temporal orquestado en: {dir_temporal_extraccion}")
    
    todas_las_claves = set()

    # Fase 1: Extracción y Cosecha
    logging.info(f"==== FASE 1: DESCOMPRESIÓN MPYQ y OBTENCIÓN DE CLAVES ====")
    for sc2_file in archivos_sc2:
        textos_extraidos = extraer_textos_mpq(sc2_file, dir_temporal_extraccion)
        if textos_extraidos:
            claves_locales = cosechar_claves(textos_extraidos)
            todas_las_claves.update(claves_locales)
            logging.info(f" -> Cosechadas {len(claves_locales)} llaves únicas de {sc2_file.name}")

    total_claves_objetivo = len(todas_las_claves)
    logging.info(f"[+] Reestructuración finalizada. Pool maestro a purgar: {total_claves_objetivo} IDs.")

    if total_claves_objetivo == 0:
        logging.info("No hay claves que purgar. Abortando limpieza segura.")
        shutil.rmtree(dir_temporal_extraccion)
        return

    # Fase 2: Purgado de Memoria RAM
    logging.info("==== FASE 2: PURGA QUIRÚRGICA DE LA CACHÉ JSON ====")
    try:
        with archivo_estado.open('r', encoding='utf-8') as f:
            datos_ram = json.load(f)
    except Exception as e:
        logging.error(f"Fallo cargando estado_traduccion.json en RAM: {e}")
        shutil.rmtree(dir_temporal_extraccion)
        return

    peso_inicial = len(datos_ram)
    logging.info(f"Caché cargada: {peso_inicial} lineas.")
    
    claves_removidas_count = 0
    # Borrado por coincidencia pura
    for id_a_exterminar in todas_las_claves:
        if id_a_exterminar in datos_ram:
            del datos_ram[id_a_exterminar]
            claves_removidas_count += 1

    peso_final = len(datos_ram)

    # Fase 3: Sellado Atómico
    logging.info("==== FASE 3: ESCRITURA ATÓMICA DE SEGURIDAD ====")
    if claves_removidas_count > 0:
        fd, ruta_temporal_json = tempfile.mkstemp(suffix=".json", text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(datos_ram, f, indent=4, ensure_ascii=False)
            
            shutil.move(ruta_temporal_json, archivo_estado)
            logging.info("[✔] Nueva Caché Escrita Atómicamente.")
        except Exception as e:
            logging.error(f"Fallo durante la escritura atómica: {e}")
            if Path(ruta_temporal_json).exists():
                os.unlink(ruta_temporal_json)
    else:
        logging.info("No se hallaron coincidencias. JSON original inalterado.")

    # Fase 4: Autolimpieza de Basura
    logging.info("==== FASE 4: AUTOLIMPIEZA Y RESUMEN ====")
    try:
        shutil.rmtree(dir_temporal_extraccion)
        logging.info(f"Borrado forestal de temporales (TXT/XML) en: {dir_temporal_extraccion}")
    except Exception as e:
        logging.error(f"Advertencia: No se pudo eliminar el directorio temporal: {e}")

    logging.info("=" * 45)
    logging.info("[REPORTE DE PURGA COMPLETADO]")
    logging.info(f" => Base de datos originaria: {peso_inicial} claves")
    logging.info(f" => Eliminaciones exactas: {claves_removidas_count} claves")
    logging.info(f" => Base de datos resultante: {peso_final} claves")
    logging.info("=" * 45)

if __name__ == "__main__":
    main()
