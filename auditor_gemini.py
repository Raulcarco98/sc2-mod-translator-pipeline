import json
import os
import sys
import urllib.request
import urllib.error
import time

def load_env_key():
    env_path = ".env"
    if not os.path.exists(env_path):
        print("No .env file found.")
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

def main():
    api_key = load_env_key()
    if not api_key:
        print("No API key found in .env")
        return

    json_path = "estado_traduccion.json"
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        datos = json.load(f)

    # Filtrar vacíos
    datos = {k: v for k, v in datos.items() if v.strip() and not v.startswith("[HTTP_FAIL]") and not v.startswith("[SKIP_LLM]")}
    claves = list(datos.keys())
    total = len(claves)
    print(f"Total non-empty translations to review: {total}")

    chunk_size = 200 # Reducido a 200 para evitar agotar el modelo o generar JSON rotos
    resultado_final = {}
    output_path = "errores_traduccion.json"
    
    # Cargar anterior si existe (para reanudar)
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                resultado_final = json.load(f)
        except:
            pass

    # Calcular índice procesado (rudimentario)
    # Por el bien de la limitación del tiempo, tal vez solo procesemos unos 2000 items (10 chunks) o los que queramos.
    # El usuario dijo "aunque sea troceado, revises ese json", voy a hacer el script completo que se puede reanudar.
    
    # Encontrar desde dónde empezar:
    # Si tenemos chunks ya analizados, para no ser perfectos, solo iteraremos desde 0 o desde donde nos manden.
    # Para ser ágil, y dar un primer reporte:
    
    inicio = 0
    llamadas_hechas = 0

    # Usaremos estado de reanudación usando un archivo .progress_gemini
    progreso = 0
    if os.path.exists(".progress_gemini"):
        with open(".progress_gemini", "r") as p:
            progreso = int(p.read().strip())
    
    if progreso >= total:
        print("El archivo ya fue completamente revisado.")
        return

    inicio = progreso

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    motivo_prompt = (
        "Eres un editor experto corrigiendo textos en español de un videojuego. "
        "Te proporcionaré un JSON literal. Debes identificar traducciones "
        "que estén notablemente mal: líneas sin sentido, verbos en infinitivo (ej: 'Ellos atacar' en vez de 'atacan'), "
        "palabras en mayúsculas sin razón, o sintaxis rota. "
        "Ignora los que tengan fallos de estilo si son inteligibles y pasables. "
        "Ignora variables (ej: ~A~ o <c val=\"xxx\">). "
        "IMPORTante: Devuelve EXCLUSIVAMENTE un bloque de código JSON con este formato exacto:\n"
        "{\n"
        "  \"KEY\": {\"traduccion_actual\": \"...\", \"problema\": \"...\"}\n"
        "}\n\n"
        "No incluyas MD ````json ``` ni otros comentarios fuera del JSON. Si no hay errores evidentes, devuelve {}."
    )

    while inicio < total:
        fin = min(inicio + chunk_size, total)
        chunk = {k: datos[k] for k in claves[inicio:fin]}
        
        cuerpo = {
            "contents": [
                {
                    "parts": [
                        {"text": motivo_prompt},
                        {"text": "Aquí tienes el JSON a evaluar:\n" + json.dumps(chunk, ensure_ascii=False, indent=2)}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            }
        }
        
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode('utf-8'), headers={'Content-Type': 'application/json'})
        print(f"Enviando chunk [{inicio}:{fin}]...")
        
        try:
            with urllib.request.urlopen(req) as response:
                res_body = response.read()
                res_json = json.loads(res_body)
                
                # extraer texto
                text_response = res_json['candidates'][0]['content']['parts'][0]['text']
                # limpiar markdown si lo puso
                text_response = text_response.strip()
                if text_response.startswith('```json'): text_response = text_response[7:]
                if text_response.startswith('```'): text_response = text_response[3:]
                if text_response.endswith('```'): text_response = text_response[:-3]
                text_response = text_response.strip()

                if text_response:
                    try:
                        analisis_chunk = json.loads(text_response)
                        resultado_final.update(analisis_chunk)
                    except json.JSONDecodeError:
                        print(f"Error parseando JSON de respuesta chunk [{inicio}:{fin}]:")
                        print(text_response)
        
        except urllib.error.HTTPError as e:
            print(f"HTTPError: {e.code} - {e.read().decode('utf-8')}")
            break
        except Exception as e:
            print(f"Error inesperado: {e}")
            break
            
        inicio = fin
        llamadas_hechas += 1
        with open(".progress_gemini", "w") as p:
            p.write(str(inicio))
            
        # Guardado incremental
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(resultado_final, f, indent=4, ensure_ascii=False)
            
        time.sleep(4) # rate limit safe

    print(f"Progreso actual: {inicio}/{total}. Se hicieron {llamadas_hechas} peticiones a Gemini.")
    print(f"Revisa '{output_path}' para ver los problemas.")

if __name__ == "__main__":
    main()
