import json
import re
import argparse
import logging
import time
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, List

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# Configuración básica de registro
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# === SISTEMA DE CHECKPOINTING ===
CHECKPOINT_FILE = Path("estado_traduccion.json")

def cargar_checkpoint() -> Dict[str, str]:
    if CHECKPOINT_FILE.exists():
        try:
            with CHECKPOINT_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Filtrar entradas que fallaron en ejecuciones anteriores para que se reintenten
                filtros_error = ["[HTTP_FAIL]", "[API ERROR]", "[SKIP_LLM]", "[AI_ERROR]"]
                datos_validos = {}
                reintentos_necesarios = 0
                
                for k, v in data.items():
                    if any(v.startswith(error) for error in filtros_error):
                        reintentos_necesarios += 1
                    else:
                        datos_validos[k] = v
                        
                logging.info(f"[*] Checkpoint recuperado: {len(datos_validos)} líneas ya traducidas correctamente.")
                if reintentos_necesarios > 0:
                    logging.warning(f"[*] Se han descartado {reintentos_necesarios} entradas de la caché con errores para reintentarlas.")
                    
                return datos_validos
        except Exception as e:
            logging.error(f"Error leyendo el checkpoint (corrupto): {e}")
    return {}

def guardar_checkpoint(datos: Dict[str, str], datos_originales: Dict[str, str] = None) -> None:
    # Fusionamos con los datos originales del disco (si los hay) para no perder nada sobreescrito en el aire
    estado_total = cargar_checkpoint() if not datos_originales else datos_originales
    estado_total.update(datos)
    
    try:
        with CHECKPOINT_FILE.open('w', encoding='utf-8') as f:
            json.dump(estado_total, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Fallo crítico guardando checkpoint: {e}")

# === INTEGRACIÓN LLM (GEMINI 2.0 FLASH / google.genai SDK) ===

SYSTEM_PROMPT = """Eres un traductor experto del videojuego StarCraft II. 
Tu objetivo es traducir literales del inglés al Español de España (Castellano).
Sigue estrictamente estas reglas inquebrantables:
1. Mantén un tono militar y de ciencia ficción oscura, fiel al universo de StarCraft (Zerg, Protoss, Terran).
2. NUNCA traduzcas ni alteres las etiquetas HTML de color, por ejemplo: <c val="00FF00"> o </c>.
3. NUNCA traduzcas ni alteres las variables encerradas entre virgulillas, por ejemplo: ~trainCar~ o ~Target_Name~.
4. NUNCA traduzcas los separadores estructurales del motor, por ejemplo: ///.
5. Devuelve la respuesta exactamente en el mismo formato en el que se te entregó: 'ClaveOriginal|TextoTraducido'.
6. REGLA DE INTERFAZ: Si traduces una cadena muy corta que actúe como instrucción o botón (ej. "Freeze Talent", "Build Drone"), priorizaSIEMPRE el uso de VERBOS EN IMPERATIVO o INFINITIVO DIRECTO (Ej: "Congelar talento", "Construir zángano"), en lugar de traducciones literales o sustantivos.
7. REGLA DE STOP WORDS: La palabra inglesa 'Unit' o 'Units' NO es un nombre propio bajo ninguna circunstancia. Debes traducirla siempre como 'unidad' o 'unidades' en minúscula, o preferiblemente eliminarla de la traducción si resulta redundante para que la frase suene natural en español.
No añadas saludos, ni explicaciones, ni bloques Markdown de código. Solo el texto traducido.
"""

def traducir_textos_batch(lote: List[Tuple[str, str]], terminologia: Dict[str, str], intentos_maximos: int = 4) -> Dict[str, str]:
    """
    Envía un lote de textos a Gemini 2.0 Flash usando el SDK (google.genai).
    """
    if not HAS_GENAI:
        logging.error("El paquete 'google-genai' no está instalado. Instalalo usando 'pip install google-genai'.")
        return {key: f"[AI] {text}" for key, text in lote}
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.error("La variable GEMINI_API_KEY no está configurada.")
        return {key: f"[AI_ERROR] {text}" for key, text in lote}

    # Instanciamos el cliente oficial
    client = genai.Client(api_key=api_key)
    
    # Configuramos los ajustes del modelo
    config_generacion = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.3,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]
    )

    traducciones_procesadas = {}
    
    # 1. Escaneo Términológico Dinámico (Context Injection)
    terminos_detectados = {}
    prompt_textos = "Traduce las siguientes líneas:\n"
    
    for key, text in lote:
        prompt_textos += f"{key}|{text}\n"
        for term_en, term_es in terminologia.items():
            # Patrón de límite de palabra (\b) y tolerancia a plurales ingleses (s/es) opcionales.
            # Ejemplo: si term_en="Diamondback", cazaría "Diamondback", "Diamondbacks", "Diamondbackes".
            if term_en not in terminos_detectados and re.search(r'\b' + re.escape(term_en) + r'(?:s|es)?\b', text, flags=re.IGNORECASE):
                terminos_detectados[term_en] = term_es
                
    # 2. Generación del Sistema de Prompt Dinámico Multi-Capa
    directiva_sistema_dinamica = SYSTEM_PROMPT
    if terminos_detectados:
        directiva_sistema_dinamica += "\n\nREGLA DE TERMINOLOGÍA INYECTADA:\nPara este lote específico, SE EXIGE que utilices EXACTAMENTE las siguientes traducciones oficiales para estos nombres propios si aparecen en el texto:\n"
        for en, es in terminos_detectados.items():
            directiva_sistema_dinamica += f"- {en} -> {es}\n"
            
    # Re-configuramos la variable Instruction del motor con el System Prompt enriquecido
    config_generacion = types.GenerateContentConfig(
        system_instruction=directiva_sistema_dinamica,
        temperature=0.3,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]
    )

    intento_actual = 0
    tiempo_espera = 2.0 

    while intento_actual < intentos_maximos:
        try:
            # === PATRÓN FALLBACK ROUTING ===
            # Intentos 1, 2 y 3 (índices 0, 1, 2) van a gemini-2.0-flash
            # El Intento Final (índice 3) escala dinámicamente a gemini-2.5-flash
            modelo_actual = 'gemini-2.0-flash' if intento_actual < (intentos_maximos - 1) else 'gemini-2.5-flash'
            
            if intento_actual == (intentos_maximos - 1):
                logging.warning(f"¡Activando Fallback Routing! Redirigiendo el Lote hacia el modelo de contingencia: {modelo_actual}")
            
            response = client.models.generate_content(
                model=modelo_actual,
                contents=prompt_textos,
                config=config_generacion
            )
            
            texto_respuesta = response.text.strip()
            lineas_respuesta = texto_respuesta.split('\n')
            
            for linea in lineas_respuesta:
                if '|' in linea:
                    partes = linea.split('|', 1)
                    if len(partes) == 2:
                        k = partes[0].strip()
                        v = partes[1].strip()
                        traducciones_procesadas[k] = v
            
            for key, original_text in lote:
                if key not in traducciones_procesadas:
                    traducciones_procesadas[key] = f"[SKIP_LLM] {original_text}"

            return traducciones_procesadas

        except Exception as e:
            intento_actual += 1
            logging.error(f"Detalle crudo de la API: {e}") # Auditoría profunda exigida
            logging.warning(f"Error HTTP 429 API o desconexión (Intento {intento_actual}/{intentos_maximos})")
            
            if intento_actual < intentos_maximos:
                logging.info(f"Aplicando Backoff Exponencial. Esperando {tiempo_espera}s...")
                time.sleep(tiempo_espera)
                tiempo_espera *= 2
            else:
                logging.error("Se agotaron los intentos para este lote. Marcando como erróneos temporales.")
                break
                
    for key, text in lote:
        traducciones_procesadas[key] = f"[HTTP_FAIL] {text}"
        
    return traducciones_procesadas

def procesar_lotes_ia(textos_ineditos: Dict[str, str], terminologia: Dict[str, str], batch_size: int = 50) -> Dict[str, str]:
    """
    Filtra los traducidos, trocea inteligentemente en bloques chicos (50) y estrangula los envíos.
    """
    if not textos_ineditos:
        return {}
        
    # Recuperación con filtrado activo (re-petición si falló)
    estado_actual = cargar_checkpoint()
    
    pendientes = {k: v for k, v in textos_ineditos.items() if k not in estado_actual}
    
    total_pendientes = len(pendientes)
    total_historico = len(estado_actual)
    
    if total_pendientes == 0:
        logging.info("[*] El checkpoint tiene todas las traducciones válidas. Subiendo datos desde la caché directamente.")
        return estado_actual
        
    logging.info(f"[*] Total en Caché local validado: {total_historico} | Restantes por procesar en API: {total_pendientes}")
    logging.info(f"[*] Configuración estricta de Lotes (Batching): {batch_size} líneas por petición HTTP.")
    
    items = list(pendientes.items())
    total_lotes = (total_pendientes + batch_size - 1) // batch_size
    
    for indice_lote, i in enumerate(range(0, total_pendientes, batch_size), 1):
        lote = items[i:i + batch_size]
        logging.info(f"  -> Lote LLM {indice_lote}/{total_lotes} | Solicitando {len(lote)} cadenas contiguas...")
        
        traducciones_lote = traducir_textos_batch(lote, terminologia)
        
        estado_actual.update(traducciones_lote)
        guardar_checkpoint(estado_actual)
        
        # Estrangulamiento obligatorio (throttling) de 2 segundos
        if indice_lote < total_lotes:
            logging.info("  [Throttling] Bloque completado. Esperando 2.0s para evitar ráfagas excesivas (Quota 429)...")
            time.sleep(2.0)
        
    return estado_actual

def run_translation_engine(workdir: Path, json_path: Path, json_terms_path: Path = None) -> None:
    logging.info("-" * 50)
    logging.info("INICIANDO MOTOR DE TRADUCCIÓN (BATCHING HÍBRIDO)")
    logging.info(f"Target Working Directory: {workdir}")
    logging.info("-" * 50)
    
    if not json_path.exists():
        logging.error(f"Falta el Glosario Oficial: No se encontró la base de datos en '{json_path}'.")
        return
        
    logging.info("Cargando base de datos lexicográfica de SC2 en memoria RAM (O(1))...")
    try:
        with json_path.open('r', encoding='utf-8') as f:
            db = json.load(f)
            idx_keys = db.get("por_clave", {})
            idx_english = db.get("por_texto_ingles", {})
    except Exception as e:
        logging.error(f"Fallo al cargar el JSON central: {e}")
        return
        
    logging.info(f"OK - Índices ensamblados: {len(idx_keys)} IDs directas, {len(idx_english)} valores mapeables.")
    
    terminologia_db = {}
    if json_terms_path and json_terms_path.exists():
        logging.info("Cargando inyector de terminología propia ligero en RAM...")
        try:
            with json_terms_path.open('r', encoding='utf-8') as f:
                terminologia_db = json.load(f)
            logging.info(f"OK - Terminología cargada: {len(terminologia_db)} nombres propios activos.")
        except Exception as e:
            logging.warning(f"No se pudo cargar la terminología secundaria, se omite inyección contextual: {e}")
    else:
        logging.warning(f"No se halló el glosario terminológico [{json_terms_path}], omisión de inyecciones dinámicas.")
    
    input_locale_dir = workdir / "enUS"
    output_locale_dir = workdir / "esES.SC2Data" / "LocalizedData"
    
    if not input_locale_dir.exists():
        logging.error("Directorio de trabajo inglés inexistente. El Extractor (Stage 1) debe ejecutarse primero.")
        return
        
    txt_files = list(input_locale_dir.glob("*.txt"))
    if not txt_files:
        logging.warning("No hay archivos colgando en la carpeta inglesa. Abortando motor.")
        return
        
    logging.info(f"Detectados {len(txt_files)} documentos. Iniciando Fase 1: Análisis y Emparejamiento...")
    
    memoria_archivos = {}
    diccionario_para_ia = {}
    
    total_oficiales_id = 0
    total_oficiales_texto = 0
    
    # Conjunto de archivos que SI deben ser inyectados masivamente al LLM
    archivos_ia = {"GameStrings.txt", "ObjectStrings.txt", "ConversationStrings.txt"}
    
    for txt_path in txt_files:
        # === PATRÓN DE ENRUTAMIENTO DIRECTO (BYPASS) ===
        if txt_path.name not in archivos_ia:
            logging.info(f"Bypass [ROUTING]: Copiando el archivo secundario '{txt_path.name}' sin procesar.")
            try:
                output_locale_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(txt_path, output_locale_dir / txt_path.name)
            except Exception as e:
                logging.error(f"Error copiando archivo secundario '{txt_path.name}': {e}")
            continue
            
        estructura_archivo = []
        try:
            with txt_path.open('r', encoding='utf-8-sig') as f:
                for line in f:
                    raw_line = line.strip()
                    
                    if not raw_line or raw_line.startswith('//'):
                        estructura_archivo.append({"tipo": "comentario", "raw": line})
                        continue
                        
                    parts = raw_line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0]
                        en_val = parts[1]
                        
                        if key in idx_keys:
                            estructura_archivo.append({"tipo": "traduccion_oficial", "key": key, "val": idx_keys[key]})
                            total_oficiales_id += 1
                            
                        elif en_val in idx_english:
                            estructura_archivo.append({"tipo": "traduccion_oficial", "key": key, "val": idx_english[en_val]})
                            total_oficiales_texto += 1
                            
                        else:
                            diccionario_para_ia[key] = en_val
                            estructura_archivo.append({"tipo": "pendiente_llm", "key": key})
                            
                    else:
                        estructura_archivo.append({"tipo": "comentario", "raw": line})
                        
            memoria_archivos[txt_path.name] = estructura_archivo
        except Exception as e:
            logging.error(f"Fallo crítico descifrando '{txt_path.name}': {e}")
            return
            
    # LLAMADA CORREGIDA: Fuerza estrictamente un tamaño de batch = 50 y pasa la terminología
    traducciones_ia = procesar_lotes_ia(diccionario_para_ia, terminologia_db, batch_size=50)
    
    logging.info("Iniciando Fase 3: Ensamblaje de archivos Inyectados (Re-Link)...")
    
    try:
        output_locale_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"Error creando carpetas de exportación: {e}")
        return
        
    for filename, macro_estructura in memoria_archivos.items():
        output_path = output_locale_dir / filename
        line_buffer = []
        
        for nodo in macro_estructura:
            node_type = nodo["tipo"]
            
            if node_type == "comentario":
                line_buffer.append(nodo["raw"])
                
            elif node_type == "traduccion_oficial":
                line_buffer.append(f"{nodo['key']}={nodo['val']}\n")
                
            elif node_type == "pendiente_llm":
                key = nodo["key"]
                es_val = traducciones_ia.get(key, f"[API ERROR FORMAT] {diccionario_para_ia.get(key, '')}")
                line_buffer.append(f"{key}={es_val}\n")
                
        try:
            with output_path.open('w', encoding='utf-8-sig') as f:
                f.writelines(line_buffer)
        except Exception as e:
            logging.error(f"Error grave escribiendo '{filename}': {e}")
            
    logging.info("=" * 45)
    logging.info("[+] TRADUCCIÓN HÍBRIDA COMPLETADA")
    logging.info(f" -> Tasa Oficial (Match Exacto de ID): {total_oficiales_id}")
    logging.info(f" -> Tasa Oficial (Match Inverso): {total_oficiales_texto}")
    logging.info(f" -> Tasa IA Generativa (Requerida/Total): {len(diccionario_para_ia)}")
    logging.info(f" -> Directorio Inyectado en: {output_locale_dir}")
    logging.info("=" * 45)

def main() -> None:
    parser = argparse.ArgumentParser(description="2ª Etapa: Inyector Oficial y Desvío IA Masivo (Batching).")
    parser.add_argument(
        "--workdir", 
        type=Path, 
        default=Path("../temp_workdir"), 
        help="Directorio de las extracciones temporales (por defecto: '../temp_workdir')."
    )
    parser.add_argument(
        "--db", 
        type=Path, 
        default=Path("../glosario_oficial.json"), 
        help="Base de datos oficial consolidada (por defecto: '../glosario_oficial.json')."
    )
    parser.add_argument(
        "--terms", 
        type=Path, 
        default=Path("../glosario_terminologico.json"), 
        help="Base de datos ligera de nombres propios a inyectar."
    )
    
    args = parser.parse_args()
    
    workdir_res = args.workdir if args.workdir.is_absolute() else Path(__file__).resolve().parent / args.workdir
    db_res = args.db if args.db.is_absolute() else Path(__file__).resolve().parent / args.db
    terms_res = args.terms if args.terms.is_absolute() else Path(__file__).resolve().parent / args.terms
    
    run_translation_engine(workdir_res, db_res, terms_res)

if __name__ == "__main__":
    main()
