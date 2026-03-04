import sys
import shutil
import winreg
import logging
from pathlib import Path

# Configuración del logueo estilo SysAdmin
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%H:%M:%S"
)

def find_sc2_install_path() -> Path:
    logging.info("Iniciando búsqueda automática de StarCraft II en el sistema...")
    paths_to_check = []
    
    # 1. Búsqueda en el Registro de Windows (Sistemas de 64 bits)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Blizzard Entertainment\StarCraft II") as key:
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            if install_path:
                paths_to_check.append(Path(install_path))
                logging.info("Registro encontrado en WOW6432Node.")
    except Exception:
        pass
        
    # 2. Búsqueda en el Registro de Windows (Sistemas de 32 bits)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Blizzard Entertainment\StarCraft II") as key:
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            if install_path:
                paths_to_check.append(Path(install_path))
                logging.info("Registro encontrado en nodo nativo.")
    except Exception:
        pass

    # 3. Rutas de contingencia estándar y discos alternativos
    paths_to_check.extend([
        Path(r"C:\Program Files (x86)\StarCraft II"),
        Path(r"C:\Program Files\StarCraft II"),
        Path(r"D:\Program Files (x86)\StarCraft II"),
        Path(r"D:\Juegos\StarCraft II"),
        Path(r"E:\Games\StarCraft II"),
        Path(r"E:\StarCraft II"),
        Path(r"F:\Juegos\StarCraft II")
    ])

    # Validación de directorio base
    for path in paths_to_check:
        try:
            if path.exists() and path.is_dir():
                # Verificar heurísticamente que es SC2 comprobando carpetas o binarios internos
                if (path / "Versions").exists() or (path / "StarCraft II.exe").exists() or (path / "Support64").exists():
                    logging.info(f"Directorio raíz validado exitosamente en: {path}")
                    return path
        except Exception:
            continue

    return None

def main():
    # Resolver ruta destino de la carpeta mapas_originales
    dest_dir = Path(__file__).resolve().parent.parent / "mapas_originales"
    
    sc2_path = find_sc2_install_path()
    
    if not sc2_path:
        logging.warning("Búsqueda automática fallida. Requisito de intervención manual (TTY).")
        try:
            user_input = input("\n[INPUT REQUERIDO] Por favor, inserte la ruta absoluta a la carpeta de StarCraft II: ").strip()
            # Limpiar comillas si el usuario copia la ruta como string
            user_input = user_input.strip('"').strip("'")
            sc2_path = Path(user_input)
            
            if not sc2_path.exists() or not sc2_path.is_dir():
                logging.error("La ruta manual proporcionada es inválida o no existe. Abortando sistema.")
                sys.exit(1)
        except EOFError:
            logging.error("Petición de entrada cancelada por falta de consola interactiva. Abortando.")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Excepción controlada procesando TTY: {e}")
            sys.exit(1)
            
    logging.info(f"Comenzando exploración de paquetes de localización en: {sc2_path}")
    
    # Archivos fundamentales del juego base y expansiones
    target_names = [
        "Core.SC2Mod",
        "Liberty.SC2Mod",
        "Swarm.SC2Mod",
        "Void.SC2Mod",
        "Liberty.SC2Campaign",
        "Swarm.SC2Campaign",
        "Void.SC2Campaign"
    ]
    
    items_to_copy = []
    
    try:
        # Exploramos las subcarpetas Mods y Campaigns de la instalación oficial
        for subdirectory in ["Mods", "Campaigns"]:
            search_path = sc2_path / subdirectory
            if search_path.exists() and search_path.is_dir():
                for item in search_path.iterdir():
                    if item.name in target_names:
                        items_to_copy.append(item)
                        
    except Exception as e:
        logging.error(f"Fallo críptico al explorar el sistema de archivos de origen: {e}")
        sys.exit(1)
        
    if not items_to_copy:
        logging.warning("No se encontraron los paquetes maestros (.SC2Mod/.SC2Campaign) en la ruta designada.")
        sys.exit(0)
        
    logging.info(f"Identificados {len(items_to_copy)} paquetes binarios candidatos para la transferencia.")
    
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"Derechos de escritura insuficientes en directorio de destino '{dest_dir}': {e}")
        sys.exit(1)
        
    archivos_procesados = 0
    # Copia segura
    for src_item in items_to_copy:
        dest_item = dest_dir / src_item.name
        logging.info(f"  -> Extrayendo volumen: {src_item.name} ...")
        try:
            if src_item.is_dir():
                # En sistemas modernos (post-patch 3.0), SC2Mod son directorios
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(src_item, dest_item)
            else:
                # Modos legado o MPQs empacados individualmente
                shutil.copy2(src_item, dest_item)
            archivos_procesados += 1
        except Exception as e:
            logging.error(f"IOError: Fallo asíncrono copiando {src_item.name}: {e}")
            
    logging.info(f"")
    logging.info(f"[+] Tarea finalizada con éxito: {archivos_procesados} paquetes transferidos de forma segura a 'mapas_originales/'.")

if __name__ == "__main__":
    main()
