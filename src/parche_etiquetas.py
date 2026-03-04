import json
import logging
import argparse
import os
import shutil
import tempfile
from pathlib import Path

# Configuración de registro
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def main():
    parser = argparse.ArgumentParser(description="Parche táctico para restaurar etiquetas XML y saltos de línea en el estado de traducción.")
    parser.add_argument(
        "--estado", 
        type=Path, 
        default=Path("estado_traduccion.json"), 
        help="Ruta al archivo de caché JSON que queremos reparar."
    )
    parser.add_argument(
        "--glosario", 
        type=Path, 
        default=Path("glosario_oficial.json"), 
        help="Ruta al glosario maestro con los tags puros restaurados."
    )
    args = parser.parse_args()

    archivo_estado = args.estado.resolve()
    archivo_glosario = args.glosario.resolve()

    if not archivo_estado.exists():
        logging.error(f"El archivo origen '{archivo_estado.name}' no existe en la ruta.")
        return
        
    if not archivo_glosario.exists():
        logging.error(f"El archivo maestro '{archivo_glosario.name}' no existe en la ruta.")
        return

    logging.info(f"Cargando {archivo_glosario.name} en RAM...")
    try:
        with archivo_glosario.open('r', encoding='utf-8') as f:
            glosario_datos = json.load(f)
            # Extraemos concretamente la vertiente 'por_clave' que es la mapeable nativamente
            glosario_claves = glosario_datos.get("por_clave", {})
    except Exception as e:
        logging.error(f"No se pudo cargar el glosario maestro: {e}")
        return

    logging.info(f"Cargando {archivo_estado.name} en RAM...")
    try:
        with archivo_estado.open('r', encoding='utf-8') as f:
            estado_datos = json.load(f)
    except Exception as e:
        logging.error(f"No se pudo cargar el estado de traducción: {e}")
        return

    total_estado_inicial = len(estado_datos)
    logging.info(f"Iniciando cruce de claves... (Caché actual: {total_estado_inicial} elementos)")

    claves_parcheadas = 0

    # Estrategia dictado por usuario: 
    # Moverse por todas las keys del GLOSARIO OFICIAL y machacar si hacen match en la CACHE.
    for clave_maestra, valor_compuesto in glosario_claves.items():
        # Verificamos si esta traducción exacta existe y está siendo mutilada en nuestro estado actual
        if clave_maestra in estado_datos:
            # Separamos la parte en español intacta de la parte inglesa añadida: "ES /// EN"
            partes = valor_compuesto.split(" /// ")
            if len(partes) >= 1:
                espanol_puro = partes[0]
                
                # Para evitar reescrituras innecesarias
                if estado_datos[clave_maestra] != espanol_puro:
                    estado_datos[clave_maestra] = espanol_puro
                    claves_parcheadas += 1

    logging.info("-" * 40)
    logging.info(f"Cruce Finalizado. Se han restaurado exitosamente {claves_parcheadas} strings rotas.")
    
    if claves_parcheadas > 0:
        logging.info("Grabando matriz reparada al disco duro mediante Escritura Atómica...")
        
        # Mecánica de Escritura Atómica para evitar corrupciones catastróficas del historial
        fd, ruta_temporal = tempfile.mkstemp(suffix=".json", text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(estado_datos, f, indent=4, ensure_ascii=False)
            
            shutil.move(ruta_temporal, archivo_estado)
            logging.info(f"[✔] {archivo_estado.name} parcheado exitosamente y blindado.")
        except Exception as e:
            logging.error(f"Fallo durante la escritura atómica: {e}")
            if Path(ruta_temporal).exists():
                os.unlink(ruta_temporal)
    else:
        logging.info("No se encontraron discrepancias. La caché está en perfecta sincronía formal.")

if __name__ == "__main__":
    main()
