import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, Any

# Configuración de registro
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def clean_sc2_text(text: str) -> str:
    """
    Sanea una cadena nativa de SC2, removiendo tags XML/HTML invisibles 
    y caracteres de escape escapados.
    
    Args:
        text (str): La cadena cruda a limpiar.
        
    Returns:
        str: Cadena formateada para su inserción rápida.
    """
    if not isinstance(text, str):
        return ""
    
    # Expresión regular para borrar tags de colores/estilos: <c val="ffffff"> ... </c>
    text_clean = re.sub(r'<[^>]+>', '', text)
    
    # Manejar secuencias de escape codificadas como subcadenas reales en el textfile
    text_clean = text_clean.replace('\\n', ' ').replace('\n', ' ')
    text_clean = text_clean.replace('\\r', '').replace('\r', '')
    text_clean = text_clean.replace('\\t', ' ').replace('\t', ' ')
    
    # Quitar dobles espacios
    text_clean = re.sub(r'\s+', ' ', text_clean)
    
    return text_clean.strip()

def sanitize_and_optimize_glossary(input_path: Path, output_path: Path) -> None:
    """
    Lee el diccionario "crudo" oficial para su sanitización rápida. 
    Estructura la base de datos resultante en una tabla Hash (dict de Python) para
    acceso en tiempo constante O(1), con un índice directo y un índice invertido.

    Args:
        input_path (Path): El archivo JSON bruto generado.
        output_path (Path): El archivo JSON de destino saneado.
    """
    if not input_path.exists():
        logging.error(f"El glosario origen '{input_path}' no fue encontrado.")
        return

    logging.info(f"Cargando el archivo diccionario fuente en memoria: {input_path}")
    
    try:
        with input_path.open('r', encoding='utf-8') as f:
            raw_glossary = json.load(f)
    except Exception as e:
        logging.error(f"Error parseando el JSON raíz: {e}")
        return

    # Estructuras de datos puras de tiempo de búsqueda constante
    optimized_by_key = {}
    optimized_by_english = {}
    
    duplicates_removed = 0
    
    for key, data in raw_glossary.items():
        clean_en = clean_sc2_text(data.get("enUS", ""))
        clean_es = clean_sc2_text(data.get("esES", ""))
        
        if not clean_en and not clean_es:
            continue

        # Hash por Clave (Reescritura de duplicados asegurada)
        optimized_by_key[key] = clean_es
        
        # Hash por Traducción (El primero que se mapea gana, evita indexados fantasma)
        if clean_en and clean_en not in optimized_by_english:
            optimized_by_english[clean_en] = clean_es
        else:
            duplicates_removed += 1

    final_estructura = {
        "por_clave": optimized_by_key,
        "por_texto_ingles": optimized_by_english
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(final_estructura, f, indent=4, ensure_ascii=False)
            
        logging.info(f"Optimización completada y volcada a: {output_path}")
        logging.info(f" -> Indice por ID original: {len(optimized_by_key)} entradas")
        logging.info(f" -> Indice Invertido (EN-ES): {len(optimized_by_english)} entradas")
        logging.info(f" -> Eficiencia: Eliminadas {duplicates_removed} superposiciones de string.")
        
    except Exception as e:
        logging.error(f"Fallo grave guardando el diccionario resultante: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Purgador y optimizador de búsquedas O(1) de Textos SC2.")
    parser.add_argument(
        "-i", "--input", 
        type=Path,
        default=Path("../glosario_oficial.json"), 
        help="Fichero JSON matriz origen."
    )
    parser.add_argument(
        "-o", "--output", 
        type=Path,
        default=Path("../glosario_saneado.json"), 
        help="Destino del fichero optimizado definitivo."
    )
    
    args = parser.parse_args()
    sanitize_and_optimize_glossary(args.input, args.output)

if __name__ == "__main__":
    main()
