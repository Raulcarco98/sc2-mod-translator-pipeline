import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import threading
import sys
import os
# --- INYECCIÓN DIRECTA DE LA API KEY PROPORCIONADA ---
os.environ["GEMINI_API_KEY"] = "AIzaSyCRspgMqwDDUsY5R0iiFA7a1JQuYgLb0Ao"
# -----------------------------------------------------

import subprocess
from pathlib import Path

class StdoutRedirector:
    """Clase personalizada para redirigir stdout/stderr a un widget de texto Tkinter."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        # Utilizar after para asegurar que la actualización se hace en el hilo principal
        self.text_widget.after(0, self._append_text, string)

    def _append_text(self, string):
        self.text_widget.configure(state=tk.NORMAL)
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state=tk.DISABLED)

    def flush(self):
        pass


class TraductorModsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Traductor de Mods StarCraft II")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Tema minimalista oscuro/moderno
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.accent_color = "#007acc"
        self.root.configure(bg=self.bg_color)
        
        self.selected_file = None
        
        self._setup_ui()
        self._setup_logging()

    def _setup_ui(self):
        # Frame superior para los controles
        controls_frame = tk.Frame(self.root, bg=self.bg_color, pady=15, padx=15)
        controls_frame.pack(fill=tk.X)
        
        # Botón para seleccionar archivo
        self.btn_select = tk.Button(
            controls_frame, 
            text="Seleccionar Directorio", 
            command=self.select_directory,
            font=("Segoe UI", 10, "bold"),
            bg="#333333", 
            fg="white", 
            activebackground="#4d4d4d",
            activeforeground="white",
            relief=tk.FLAT,
            padx=10, pady=5
        )
        self.btn_select.pack(side=tk.LEFT, padx=5)
        
        # Etiqueta de la ruta seleccionada
        self.lbl_path = tk.Label(
            controls_frame, 
            text="Ningún archivo seleccionado...", 
            bg=self.bg_color, 
            fg="#808080",
            font=("Segoe UI", 10, "italic")
        )
        self.lbl_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        # Botón de Iniciar Traducción
        self.btn_start = tk.Button(
            controls_frame, 
            text="Iniciar Traducción", 
            command=self.start_translation,
            state=tk.DISABLED,
            font=("Segoe UI", 10, "bold"),
            bg=self.accent_color, 
            fg="white",
            activebackground="#005999",
            activeforeground="white",
            relief=tk.FLAT,
            padx=10, pady=5
        )
        self.btn_start.pack(side=tk.RIGHT, padx=5)
        
        # Frame inferior para la consola
        console_frame = tk.Frame(self.root, bg=self.bg_color, padx=15, pady=5)
        console_frame.pack(fill=tk.BOTH, expand=True)
        
        lbl_console = tk.Label(
            console_frame, 
            text="Registro de Ejecución (Consola):", 
            bg=self.bg_color, 
            fg=self.fg_color,
            font=("Segoe UI", 10, "bold")
        )
        lbl_console.pack(anchor=tk.W, pady=(0, 5))
        
        # Área de texto ScrolledText (Consola virtual)
        self.console_text = scrolledtext.ScrolledText(
            console_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 10),
            bg="#000000", 
            fg="#00ff00",
            insertbackground="white",
            state=tk.DISABLED
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)

    def _setup_logging(self):
        """Redirige sys.stdout y sys.stderr a nuestra consola virtual"""
        self.redirector = StdoutRedirector(self.console_text)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        
        print("=== Traductor de Mods StarCraft II ===")
        print("Interfaz iniciada correctamente. Esperando archivo...")
        if not os.environ.get("GEMINI_API_KEY"):
            print("[ADVERTENCIA] No se ha detectado GEMINI_API_KEY en variables de entorno.")

    def select_directory(self):
        dirpath = filedialog.askdirectory(
            title="Seleccionar directorio de StarCraft 2 (Lote de Mods/Mapas)"
        )
        if dirpath:
            self.selected_file = Path(dirpath)
            self.lbl_path.config(text=str(self.selected_file), fg=self.fg_color, font=("Segoe UI", 10))
            self.btn_start.config(state=tk.NORMAL)

    def start_translation(self):
        if not self.selected_file or not self.selected_file.is_dir():
            messagebox.showwarning("Aviso", "Por favor, selecciona un directorio válido primero.")
            return
            
        # Deshabilitar botones para evitar ejecuciones paralelas
        self.btn_start.config(state=tk.DISABLED, bg="gray")
        self.btn_select.config(state=tk.DISABLED)
        print("\n" + "="*60)
        print(f"[*] Iniciando ejecución masiva en lote (Batch Mode) para el directorio:\n    {self.selected_file.name}")
        print("="*60 + "\n")
        
        # Lanzar proceso en un hilo secundario
        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()

    def _run_pipeline_thread(self):
        """Función que recaba todos los mapas del directorio y los ejecuta en bloque tolerando fallos."""
        base_target_dir = self.selected_file
        root_dir = Path(__file__).resolve().parent
        
        target_files = []
        target_files.extend(list(base_target_dir.rglob("*.SC2Map")))
        target_files.extend(list(base_target_dir.rglob("*.SC2Mod")))
        
        if not target_files:
            print("\n[-] No se encontró ningún archivo .SC2Map o .SC2Mod en este directorio.")
            self.root.after(0, self._restore_ui_state)
            return
            
        print(f"[+] Se han detectado {len(target_files)} proyectos para traducir.")
        archivos_exitosos = 0
        archivos_fallidos = 0
        
        for idx, current_file in enumerate(target_files, 1):
            mod_path = str(current_file.resolve())
            print("\n" + "*"*60)
            print(f"[*] LOTE [{idx}/{len(target_files)}] -> {current_file.name}")
            print("*"*60)
            
            # Preparamos las llamadas secuenciales asegurando salida no-buferizada con python -u
            pasos = [
                ("Stage 1 - Extracción de Textos", ["python", "-u", "src/extractor_mod.py", mod_path]),
                ("Stage 2 - Traducción con IA", ["python", "-u", "src/motor_traduccion.py"]),
                ("Stage 3 - Empaquetador", ["python", "-u", "src/empaquetador_mod.py", mod_path])
            ]
            
            hubo_error_archivo_actual = False
            
            for nombre_paso, cmd in pasos:
                print(f"\n>>> INICIANDO: {nombre_paso}")
                try:
                    # Ejecutamos el módulo capturando stdout/stderr combinado
                    proceso = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.STDOUT, 
                        text=True, 
                        bufsize=1, 
                        universal_newlines=True,
                        cwd=root_dir
                    )
                    
                    for linea in proceso.stdout:
                        print(linea, end="")
                        
                    proceso.wait()
                    
                    if proceso.returncode != 0:
                        print(f"\n[ERROR CRÍTICO] El proceso '{nombre_paso}' finalizó con código {proceso.returncode}.")
                        hubo_error_archivo_actual = True
                        break # Salimos del bucle de pasos de ESTE archivo, pasamos al siguiente archivo
                        
                except Exception as e:
                    print(f"\n[EXCEPCIÓN EN EL HILO EJECUTOR] {e}")
                    hubo_error_archivo_actual = True
                    break
                    
            if not hubo_error_archivo_actual:
                print(f"\n[+] Archivo {current_file.name} empaquetado correctamente.")
                archivos_exitosos += 1
            else:
                print(f"\n[-] Archivo {current_file.name} descartado por errores en el pipeline. Continuando con el lote...")
                archivos_fallidos += 1
                
        # Fin de Batch
        print("\n" + "="*60)
        print("[+] BATCH COMPLETADO")
        print(f" -> Éxitos: {archivos_exitosos}/{len(target_files)}")
        print(f" -> Fallos: {archivos_fallidos}/{len(target_files)}")
        print("="*60 + "\n")
            
        # Rehabilitar interfaz llamando de forma segura a Tkinter
        self.root.after(0, self._restore_ui_state)

    def _restore_ui_state(self):
        self.btn_start.config(state=tk.NORMAL, bg=self.accent_color)
        self.btn_select.config(state=tk.NORMAL)


def main():
    root = tk.Tk()
    app = TraductorModsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
