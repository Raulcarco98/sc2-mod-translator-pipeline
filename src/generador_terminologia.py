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
    Sanea una cadena nativa de SC2, removiendo tags XML/HTML invisibles 
    y caracteres de escape escapados.
    """
    if not isinstance(text, str):
        return ""
    
    text_clean = re.sub(r'<[^>]+>', '', text)
    text_clean = text_clean.replace('\\n', ' ').replace('\n', ' ')
    text_clean = text_clean.replace('\\r', '').replace('\r', '')
    text_clean = text_clean.replace('\\t', ' ').replace('\t', ' ')
    text_clean = re.sub(r'\s+', ' ', text_clean)
    
    return text_clean.strip()

def parse_terminology_file(filepath: Path) -> Dict[str, str]:
    """
    Lee un archivo GameStrings.txt o ObjectStrings.txt y extrae EXCLUSIVAMENTE
    las líneas cuya clave contenga explícitamente la palabra 'Name'.
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
                    
                    # Filtro Estricto de Claves: Solo donde la clave contenga 'Name'
                    if 'Name' in key:
                        # Purgado de envenenamiento de datos: Comentarios en-linea
                        if '///' in val:
                            val = val.split('///', 1)[0]
                            
                        cleaned = clean_sc2_text(val)
                        if cleaned:
                            strings[key] = cleaned
    except Exception as e:
        logging.error(f"No se pudo procesar el archivo '{filepath}': {e}")
    
    return strings

def process_terminology_recursively(bases_roots: list[Path]) -> Dict[str, str]:
    """
    Recorre recursivamente directorios raiz, busca archivos y deduce la matemática.
    Cruza el contenido Inglés -> Español y descarta redundancias.
    """
    en_dict_full = {}
    es_dict_full = {}
    
    for base_dir in bases_roots:
        if not base_dir.exists():
            logging.warning(f"Se saltará la fuente '{base_dir.name}' porque no existe.")
            continue
            
        en_root = base_dir / 'ingles'
        
        if not en_root.exists():
            logging.warning(f"La carpeta '{en_root}' no existe. Saltando rama.")
            continue
            
        logging.info(f"Escaneando árbol terminológico dinámico en: {en_root}")
        
        for en_txt_file in en_root.rglob("*.txt"):
            filename_lower = en_txt_file.name.lower()
            
            # FILTRO DE ARCHIVO: Solo las minas de nombres propios
            if filename_lower not in ["gamestrings.txt", "objectstrings.txt"]:
                continue
                
            str_en_path = str(en_txt_file)
            
            str_es_path = str_en_path.replace("\\ingles\\", "\\espanol\\").replace("/ingles/", "/espanol/")
            str_es_path = str_es_path.replace("enUS", "esES")
            str_es_path = str_es_path.replace("enus", "eses")
            
            es_txt_file = Path(str_es_path)
            
            if es_txt_file.exists():
                try:
                    bloque_ingles = parse_terminology_file(en_txt_file)
                    bloque_espanol = parse_terminology_file(es_txt_file)
                    
                    en_dict_full.update(bloque_ingles)
                    es_dict_full.update(bloque_espanol)
                except Exception as e:
                    logging.warning(f"Error parseando terminología en '{en_txt_file.name}': {e}. Se ignora.")
                    continue
                    
    # Cruzamos ambas estructuras por Clave ID para generar el diccionario en RAM
    terminologia_final = {}
    
    for key, en_text in en_dict_full.items():
        es_text = es_dict_full.get(key)
        
        # Filtro de Ahorro de RAM: Ingresamos si ambos existen y si el texto difiere
        if es_text and en_text and en_text != es_text:
            terminologia_final[en_text] = es_text
            
    return terminologia_final

def generate_terminology(bases_roots: list[Path], output_file: Path) -> None:
    logging.info(f"Iniciando consolidación léxica de nombres propios...")
    
    terminologia = process_terminology_recursively(bases_roots)
    
    if not terminologia:
        logging.warning("El escáner terminó pero no volcó ninguna terminología válida a memoria.")
        return

    logging.info(f"Términos dinámicos únicos capturados: {len(terminologia)}")

    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(terminologia, f, indent=4, ensure_ascii=False)
            
        logging.info("=" * 50)
        logging.info(f"[+] Glosario Terminológico Dinámico (Nombres Propios) generado.")
        logging.info(f" -> Guardado en: {output_file}")
        logging.info(f" -> Términos mapeados [Inglés -> Español]: {len(terminologia)}")
        logging.info("=" * 50)
        
    except Exception as e:
        logging.error(f"Fallo grave guardando la terminología resultante: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Inyector Táctil: Genera Diccionario en RAM de Nombres Propios.")
    
    default_campanas = Path(__file__).resolve().parent.parent / "extracciones_campanas"
    default_mapas = Path(__file__).resolve().parent.parent / "extracciones_mapas"
    default_mods = Path(__file__).resolve().parent.parent / "extracciones_mods"
    default_output = Path(__file__).resolve().parent.parent / "glosario_terminologico.json"
    
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
        help="Archivo JSON terminológico resultante para inyección a LLM."
    )
    
    args = parser.parse_args()
    
    fuentes_activas = [args.campanas, args.mapas, args.mods]

    generate_terminology(fuentes_activas, args.output)

if __name__ == "__main__":
    main()
