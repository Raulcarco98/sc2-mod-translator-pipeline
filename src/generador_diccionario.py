import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, Tuple

# Configuración de registro estilo SysAdmin
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%H:%M:%S"
)

def clean_sc2_text(text: str) -> str:
    """
    Sanea una cadena nativa de SC2.
    Ya no eliminamos tags XML ni códigos de color/salto de línea a petición del usuario.
    Preservamos íntegramente la sintaxis nativa de Blizzard para inyecciones correctas 1:1.
    """
    if not isinstance(text, str):
        return ""
    
    return text.strip()

def parse_gamestrings_file(filepath: Path) -> Dict[str, str]:
    """
    Lee un archivo GameStrings.txt o similar y extrae las parejas clave-valor limpias.
    Soporta formato UTF-8 con BOM.
    """
    strings = {}
    try:
        with filepath.open('r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    strings[key] = clean_sc2_text(val)
    except Exception as e:
        logging.error(f"No se pudo procesar el archivo '{filepath}': {e}")
    
    return strings

def procesar_rutas_recursivas(bases_roots: list[Path]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Recorre recursivamente directorios raiz. Entra en sus ramas 'ingles', busca archivos .txt
    con rglob y deduce matemáticamente la ruta de su pareja española para emparejamiento simultáneo.
    """
    en_dict = {}
    es_dict = {}
    
    for base_dir in bases_roots:
        if not base_dir.exists():
            logging.warning(f"Se saltará la fuente '{base_dir.name}' porque no existe.")
            continue
            
        en_root = base_dir / 'ingles'
        
        if not en_root.exists():
            logging.warning(f"La carpeta '{en_root}' no existe. Saltando rama.")
            continue
            
        logging.info(f"Escaneando árbol recursivo y calculando emparejamientos en: {en_root}")
        
        # Iterador recursivo nativo en toda la profundidad del árbol inglés
        for en_txt_file in en_root.rglob("*.txt"):
            filename_lower = en_txt_file.name.lower()
            
            # FILTRO QUIRÚRGICO DE RUIDO: Ignoramos todo lo que no sea estricto Game/ObjectStrings
            if filename_lower not in ["gamestrings.txt", "objectstrings.txt"]:
                continue
                
            # --- LÓGICA DE ENRUTAMIENTO SIMÉTRICO (ROUTING POR REEMPLAZO STRING) ---
            str_en_path = str(en_txt_file)
            
            # 1. Pivotar la rama del lenguaje principal
            str_es_path = str_en_path.replace("\\ingles\\", "\\espanol\\").replace("/ingles/", "/espanol/")
            
            # 2. Pivotar asunciones de carpetas de localización incrustadas (Sensibilidad mixta)
            str_es_path = str_es_path.replace("enUS", "esES")
            str_es_path = str_es_path.replace("enus", "eses")
            
            es_txt_file = Path(str_es_path)
            
            if es_txt_file.exists():
                # Extracción atómica simultánea con Tolerancia a Fallos
                try:
                    bloque_ingles = parse_gamestrings_file(en_txt_file)
                    bloque_espanol = parse_gamestrings_file(es_txt_file)
                    
                    en_dict.update(bloque_ingles)
                    es_dict.update(bloque_espanol)
                except Exception as e:
                    logging.warning(f"Error parseando el par '{en_txt_file.name}': {e}. Se ignora para no detener el volcado.")
                    continue
                    
    return en_dict, es_dict

def consolidate_glossary(bases_roots: list[Path], output_file: Path) -> None:
    """
    Empareja las claves extraídas y genera el JSON optimizado (O(1)).
    """
    logging.info(f"Iniciando consolidación de datos dinámicos...")
    
    en_dict, es_dict = procesar_rutas_recursivas(bases_roots)
    
    if not en_dict or not es_dict:
        logging.warning("El escáner terminó pero no volcó ninguna métrica a memoria. Revisa las rutas.")
        return

    logging.info(f"Cadenas inglesas en memoria cruzada: {len(en_dict)}")
    logging.info(f"Cadenas españolas en memoria cruzada: {len(es_dict)}")

    # Estructuras de datos puras de tiempo de búsqueda constante
    optimized_by_key = {}
    optimized_by_english = {}
    
    matched_keys = 0
    duplicates_removed = 0
    
    for key, en_text in en_dict.items():
        es_text = es_dict.get(key)
        
        # Solo procesamos si hay match en español y los textos no están vacíos
        if es_text and (en_text or es_text):
            matched_keys += 1
            
            # El valor a inyectar será el Español puro sumado a un delimitador y el Inglés puro
            valor_concatenado = f"{es_text} /// {en_text}"
            
            # 1. Hash por Clave
            optimized_by_key[key] = valor_concatenado
            
            # 2. Hash por Traducción (English -> Spanish)
            if en_text and en_text not in optimized_by_english:
                optimized_by_english[en_text] = valor_concatenado
            else:
                duplicates_removed += 1

    final_estructura = {
        "por_clave": optimized_by_key,
        "por_texto_ingles": optimized_by_english
    }

    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(final_estructura, f, indent=4, ensure_ascii=False)
            
        logging.info("=" * 50)
        logging.info(f"[+] Glosario generado y optimizado con éxito.")
        logging.info(f" -> Guardado en: {output_file}")
        logging.info(f" -> Total claves únicas indexadas: {matched_keys}")
        logging.info(f" -> Índice por ID original: {len(optimized_by_key)} entradas")
        logging.info(f" -> Índice Invertido (EN->ES): {len(optimized_by_english)} entradas únicas")
        logging.info(f" -> Evitadas {duplicates_removed} redundancias exactas de texto inglés.")
        logging.info("=" * 50)
        
    except Exception as e:
        logging.error(f"Fallo grave guardando el glosario resultante: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador inmutable del diccionario oficial de traducciones SC2 consolidado.")
    
    # Resolver rutas relativas por defecto al workspace actual de forma estructurada
    default_campanas = Path(__file__).resolve().parent.parent / "extracciones_campanas"
    default_mapas = Path(__file__).resolve().parent.parent / "extracciones_mapas"
    default_mods = Path(__file__).resolve().parent.parent / "extracciones_mods"
    default_output = Path(__file__).resolve().parent.parent / "glosario_oficial.json"
    
    parser.add_argument(
        "--campanas", 
        type=Path,
        default=default_campanas, 
        help="Directorio raíz para las campañas narrativas extraídas."
    )
    parser.add_argument(
        "--mapas", 
        type=Path,
        default=default_mapas, 
        help="Directorio forestal de extracciones de mapas individuales/arcade."
    )
    parser.add_argument(
        "--mods", 
        type=Path,
        default=default_mods, 
        help="Directorio de extracciones de mods y paquetes de recursos genéricos."
    )
    parser.add_argument(
        "-o", "--output", 
        type=Path,
        default=default_output, 
        help="Archivo JSON consolidado de salida."
    )
    
    args = parser.parse_args()
    
    fuentes_activas = [args.campanas, args.mapas, args.mods]

    consolidate_glossary(fuentes_activas, args.output)

if __name__ == "__main__":
    main()
