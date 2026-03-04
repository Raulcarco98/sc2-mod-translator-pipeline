import os
import shutil
import argparse
import logging
import subprocess
from pathlib import Path

# Configuración básica de registro
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def inject_translations_with_mpqeditor(
    original_mod_path: Path, 
    translated_locale_path: Path, 
    output_dir: Path
) -> bool:
    """
    Crea una copia del archivo binario original en dist_comercial y utiliza
    un subproceso invocando MPQEditor.exe para inyectar recursivamente la carpeta
    traducida esES.SC2Data directamente en la raíz lógica del contenedor.
    """
    logging.info("-" * 45)
    logging.info("INICIANDO EMPAQUETADOR BINARIO (MPQEditor.exe)")
    logging.info("-" * 45)
    
    if not original_mod_path.exists():
        logging.error(f"El mod origen '{original_mod_path}' no existe.")
        return False
        
    if not translated_locale_path.exists():
        logging.error(f"La carpeta '{translated_locale_path}' no se encuentra. Ejecuta el Motor primero.")
        return False

    basename = original_mod_path.stem
    # Conservar exactamente el mismo nombre y extensión
    new_mod_name = original_mod_path.name
    final_mod_path = output_dir / new_mod_name
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not original_mod_path.is_dir():
            logging.info(f" -> Clonando contenedor maestro: {new_mod_name}")
            shutil.copy2(original_mod_path, final_mod_path)
            
    except Exception as e:
        logging.error(f"Error copiando el archivo original hacia el destino: {e}")
        return False
        
    # Flujo para archivos MPQ comprimidos (.SC2Mod o .SC2Map binario cerrado)
    if not original_mod_path.is_dir():
        logging.info(f" -> Lanzando subproceso MPQEditor para inyectar localización estructural...")
        
        logging.info(f" -> Generando script temporal para consola de MPQEditor...")
        
        script_file_path = Path("mpq_script.txt").resolve()
        
        # Sintaxis interna de MPQEditor: a "ModOriginal" "CarpetaAMeter" "Destino" /r
        comando_interno = f'a "{final_mod_path}" "{translated_locale_path}" "esES.SC2Data" /r\n'
        
        try:
            script_file_path.write_text(comando_interno, encoding="utf-8")
        except Exception as e:
            logging.error(f"Error grave escribiendo el script temporal '{script_file_path.name}': {e}")
            return False

        comando_externo = [
            "MPQEditor.exe",
            "/console",
            str(script_file_path)
        ]
        
        try:
            logging.info(f" -> Lanzando MPQEditor en modo Script...")
            # Capturamos stdout y stderr de manera separada para leer de forma cristalina
            proceso = subprocess.run(
                comando_externo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # MPQEditor es una herramienta heredada que a menudo devuelve exit code 0 
            # aunque haya fallado silenciosamente al añadir los archivos.
            # Por tanto, obligamos al log a escupir SIEMPRE su salida estándar para auditoría.
            logging.info("--- [OUTPUT MPQEDITOR] ---")
            stdo = proceso.stdout.strip()
            stde = proceso.stderr.strip()
            if stdo: logging.info(f"\n{stdo}")
            if stde: logging.warning(f"STDERR Detectado:\n{stde}")
            logging.info("--------------------------")
            
            if proceso.returncode == 0:
                logging.info("[+] SECUENCIA BINARIA COMPLETADA.")
                logging.info(f"[+] El paquete finalizado se encuentra en: {final_mod_path}")
                resultado_final = True
            else:
                logging.error(f"MPQEditor.exe devolvió un código de error fatal: {proceso.returncode}.")
                resultado_final = False
                
        except FileNotFoundError:
            logging.error("No se ha encontrado 'MPQEditor.exe' en el PATH del sistema.")
            logging.error("Por favor, asegúrate de haber descargado MPQEditor y colocarlo en un directorio visible o en la raíz de la app.")
            resultado_final = False
        except Exception as e:
            logging.error(f"Lanzamiento de MPQEditor.exe experimentó una excepción imprevista: {e}")
            resultado_final = False
        finally:
            # Limpieza higiénica del script de texto
            if script_file_path.exists():
                try:
                    os.remove(script_file_path)
                    logging.info(f" -> Script temporal '{script_file_path.name}' limpiado de la raíz.")
                except Exception as e:
                    logging.warning(f"No se pudo borrar el archivo temporal '{script_file_path.name}': {e}")
                    
        return resultado_final

    if original_mod_path.is_dir():
        logging.info(" -> [SC2 COMPONENT DIRECTORY DETECTADO]")
        logging.info(" -> Compilando a Archivo Binario (.SC2Mod/.SC2Map) desde cero...")
        
        # Eliminamos la carpeta clonada cruda si pre-existe, porque la meta es crear un archivo
        if final_mod_path.exists() and final_mod_path.is_dir():
            shutil.rmtree(final_mod_path)
            
        script_file_path = Path("mpq_script.txt").resolve()
        
        # Comandos MPQEditor de creación estructurada:
        # 1. 'n' = Crear nuevo MPQ vacío
        # 2. 'a' (con comodin) = Añadir el contenido completo original
        # 3. 'a' = Inyectar a posteriori la traducción
        comandos_compilacion = (
            f'n "{final_mod_path}"\n'
            f'a "{final_mod_path}" "{original_mod_path}\\*" "" /r\n'
            f'a "{final_mod_path}" "{translated_locale_path}" "esES.SC2Data" /r\n'
        )
        
        try:
            script_file_path.write_text(comandos_compilacion, encoding="utf-8")
        except Exception as e:
            logging.error(f"Error grave escribiendo script de compilación: {e}")
            return False
            
        comando_externo = [
            "MPQEditor.exe",
            "/console",
            str(script_file_path)
        ]
        
        try:
            logging.info(f" -> Ejecutando Compilador MPQEditor...")
            proceso = subprocess.run(
                comando_externo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
            
            logging.info("--- [OUTPUT COMPILADOR MPQEDITOR] ---")
            stdo = proceso.stdout.strip()
            stde = proceso.stderr.strip()
            if stdo: logging.info(f"\n{stdo}")
            if stde: logging.warning(f"STDERR Detectado:\n{stde}")
            logging.info("--------------------------")
            
            if proceso.returncode == 0:
                logging.info("[+] SECUENCIA DE COMPILACIÓN DE DIRECTORIO COMPLETADA.")
                logging.info(f"[+] El paquete finalizado se encuentra en: {final_mod_path}")
                return True
            else:
                logging.error(f"MPQEditor.exe devolvió un código de error fatal: {proceso.returncode}.")
                return False
        except Exception as e:
            logging.error(f"Lanzamiento de MPQEditor.exe falló: {e}")
            return False
        finally:
            if script_file_path.exists():
                try: os.remove(script_file_path)
                except: pass

def main() -> None:
    parser = argparse.ArgumentParser(description="3ª Etapa del Pipeline: Empaquetador Binario con MPQEditor.")
    parser.add_argument(
        "mod_path", 
        type=Path, 
        help="Ruta inicial al archivo sólido .SC2Mod o .SC2Map original."
    )
    parser.add_argument(
        "--workdir", 
        type=Path, 
        default=Path("../temp_workdir"), 
        help="Directorio temporal de trabajo (por defecto '../temp_workdir')."
    )
    parser.add_argument(
        "--output", 
        type=Path, 
        default=Path("../dist_comercial"), 
        help="Directorio de exportación (por defecto '../dist_comercial')."
    )
    
    args = parser.parse_args()
    
    mod_resolved = args.mod_path if args.mod_path.is_absolute() else Path(__file__).resolve().parent / args.mod_path
    workdir_res = args.workdir if args.workdir.is_absolute() else Path(__file__).resolve().parent / args.workdir
    out_res = args.output if args.output.is_absolute() else Path(__file__).resolve().parent / args.output
    
    locale_dir = workdir_res / "esES.SC2Data"
    
    inject_translations_with_mpqeditor(mod_resolved, locale_dir, out_res)
        
if __name__ == "__main__":
    main()
