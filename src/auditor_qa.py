import json
import logging
import urllib.request
import urllib.error
import tempfile
import shutil
import os
import argparse
from pathlib import Path

# Configuración de registro QA
logging.basicConfig(
    level=logging.INFO,
    format="[QA AUDITOR] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

PROMPT_SISTEMA_QA = """Eres un auditor de control de calidad gramatical para el videojuego StarCraft. Tu unico objetivo es detectar errores de concordancia provocados por inyecciones literales de diccionarios, especialmente verbos en infinitivo que deberian estar conjugados, por ejemplo cuando el texto dice Los Murcielagos Atacar en lugar de atacan. Reglas absolutas: 1. Si la frase tiene sentido gramatical basico y los verbos concuerdan, aunque el estilo sea un poco robotico, responde unicamente con la palabra OK. 2. Si detectas un verbo en infinitivo mal encajado o una palabra que rompe claramente la gramatica de la oracion, responde unicamente con la frase corregida, manteniendo las etiquetas de formato originales si las hubiera. 3. Tienes prohibido dar explicaciones o justificar tus respuestas.

Texto Analizado: "{espanol}"
Veredicto:
"""

def evaluar_con_ollama(texto_esp: str, modelo: str = "llama3.2") -> str:
    """Ejecuta una llamada simple a la API local de Ollama para auditar la traducción."""
    url = "http://localhost:11434/api/generate"
    prompt_dinamico = PROMPT_SISTEMA_QA.format(espanol=texto_esp)
    
    payload = {
        "model": modelo,
        "prompt": prompt_dinamico,
        "stream": False,
        "options": {
            "temperature": 0.1 # Muy consistente y objetivo
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            res_json = json.loads(res_body)
            # Retorna la respuesta generada convertida a mayúsculas para facilitar regex o detección
            return res_json.get("response", "").strip()
    except Exception as e:
        logging.error(f"Fallo de conexión con Ollama Local: {e}")
        return "ERROR_API"

def read_english_context(keys: list[str]) -> dict[str, str]:
    """
    Intenta reconstruir rudimentariamente el texto original en inglés.
    Idealmente necesitamos la clave del JSON para emparejarla.
    Dado que solo tenemos la base de datos de traducciones completa, el usuario 
    solicitó pasar par 'inglés y español'. Sin la base original en inglés a mano,
    extraemos la estructura.
    """
    # Para poder enviarle a Ollama el texto original en inglés, debemos extraerlo.
    # Como estado_traduccion.json es solo "Clave" : "Traducción Español",
    # vamos a asumir que para evaluar la naturalidad, O bien usamos la clave como aproximación,
    # O bien el usuario asume que disponemos de un diccionario inglés original.
    # De hecho, cargaremos el glosario_oficial.json para el contexto inverso si es posible.
    pass

def main():
    parser = argparse.ArgumentParser(description="Analista QA de Traducciones usando Ollama Local.")
    parser.add_argument(
        "--estado", 
        type=Path, 
        default=Path("estado_traduccion.json"), 
        help="Ruta al archivo de caché JSON a sobrescribir."
    )
    parser.add_argument(
        "--modelo", 
        type=str, 
        default="llama3.1", 
        help="Nombre del modelo Ollama local a usar (ej: llama3.1, mistral, gemma2)."
    )
    parser.add_argument(
        "--inicio", 
        type=int, 
        default=0, 
        help="Índice de inicio para el tramo a procesar."
    )
    parser.add_argument(
        "--limite", 
        type=int, 
        default=None, 
        help="Límite máximo de elementos a procesar en esta ejecución."
    )
    args = parser.parse_args()

    archivo_estado = args.estado.resolve()

    if not archivo_estado.exists():
        logging.error(f"El archivo base '{archivo_estado}' no existe.")
        return

    logging.info(f"Cargando {archivo_estado.name} en memoria RAM...")
    try:
        with archivo_estado.open('r', encoding='utf-8') as f:
            datos_ram = json.load(f)
    except Exception as e:
        logging.error(f"No se pudo cargar el archivo: {e}")
        return

    total_lineas = len(datos_ram)
    
    inicio_slice = args.inicio
    limite_slice = args.limite if args.limite is not None else total_lineas
    
    lista_claves = list(datos_ram.items())
    tramo_procesar = lista_claves[inicio_slice:limite_slice]
    total_tramo = len(tramo_procesar)
    
    logging.info(f"Cargadas {total_lineas} claves totales.")
    logging.info(f"Iniciando auditoría del TRAMO [{inicio_slice}:{limite_slice}] ({total_tramo} frases) con {args.modelo}...")

    flags_anadidos = 0
    reporte_errores = {}
    
    # Iteración exhaustiva del tramo en RAM
    n_actual = 0
    for key, text_es in tramo_procesar:
        n_actual += 1
        
        # Saltamos las que ya están omitidas por fallo o salto de la IA general
        if text_es.startswith("[HTTP_FAIL]") or text_es.startswith("[SKIP_LLM]"):
            continue
            
        # Bypass de rendimiento: saltar cadenas vacías, solo espacios o muy cortas
        if not text_es or not text_es.strip() or len(text_es.strip()) < 4:
            continue
            
        print(f"\rAuditoría Tramo [{n_actual}/{total_tramo}] (Índice Global: {inicio_slice + n_actual - 1})...", end="", flush=True)
            
        respuesta_qa = evaluar_con_ollama(text_es, modelo=args.modelo)
        
        if respuesta_qa == "ERROR_API":
            logging.error("\nConexión con Ollama interrumpida. Guardando progreso y abortando auditoría.")
            break
            
        if not ("OK" in respuesta_qa.upper() and len(respuesta_qa) < 5):
            # Falló el test de naturalidad. Añadir al reporte de revisión final
            logging.warning(f"\n[!] INFRACCIÓN QA DETECTADA -> Clave: {key}")
            logging.warning(f"  > Texto Español: {text_es}")
            logging.warning(f"  > Sugerencia Ollama: {respuesta_qa}")
            
            reporte_errores[key] = {
                "original_espanol": text_es,
                "sugerencia_ia": respuesta_qa
            }
            flags_anadidos += 1

    print("\n")
    logging.info(f"Auditoría de Tramo Finalizada. Infracciones generadas: {flags_anadidos}.")
    
    if flags_anadidos > 0:
        output_report = Path("reporte_auditoria.json").resolve()
        
        # Si el reporte ya existe de ejecuciones por tramos anteriores, lo unimos
        if output_report.exists():
            try:
                with output_report.open('r', encoding='utf-8') as f:
                    reporte_existente = json.load(f)
                    reporte_existente.update(reporte_errores)
                    reporte_errores = reporte_existente
            except Exception as e:
                logging.warning(f"No se pudo cargar reporte previo, se sobrescribirá. Error: {e}")
                
        logging.info("Guardando Reporte de Auditoría (Solo Lectura) a disco duro...")
        try:
            with output_report.open('w', encoding='utf-8') as f:
                json.dump(reporte_errores, f, indent=4, ensure_ascii=False)
            logging.info(f"[✔] Reporte generado exitosamente en: {output_report.name}")
        except Exception as e:
            logging.error(f"Fallo durante la escritura del reporte: {e}")
    else:
        logging.info("Ollama no encontró errores en las traducciones auditadas. No se generó reporte.")

if __name__ == "__main__":
    main()
