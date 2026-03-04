import json
import os
import shutil

def main():
    estado_path = "estado_traduccion.json"
    errores_path = "errores_traduccion.json"

    if not os.path.exists(estado_path):
        print(f"File not found: {estado_path}")
        return
        
    if not os.path.exists(errores_path):
        print(f"File not found: {errores_path}")
        return

    # 1. Load both JSONs
    print(f"Cargando {estado_path}...")
    with open(estado_path, "r", encoding="utf-8") as f:
        estado_dict = json.load(f)
        
    print(f"Cargando {errores_path}...")
    with open(errores_path, "r", encoding="utf-8") as f:
        errores_dict = json.load(f)

    # 2. Iterate and apply fixes
    aplicados = 0
    claves_a_borrar = []

    for clave, datos in errores_dict.items():
        nueva_traduccion = datos.get("nueva_traduccion")
        
        # Si el usuario ha añadido el campo "nueva_traduccion" (y no está vacío o solo espacios)
        if nueva_traduccion is not None and str(nueva_traduccion).strip():
            # Apply to main database
            if clave in estado_dict:
                estado_dict[clave] = str(nueva_traduccion) # no hacer trim, dejalo tal cual por si hay espacios intencionales
                claves_a_borrar.append(clave)
                aplicados += 1
            else:
                print(f"Advertencia: La clave {clave} no existe en estado_traduccion.json. Ignorando.")

    # 3. Borrar del JSON de revisión
    for c in claves_a_borrar:
        del errores_dict[c]

    # 4. Save results safely
    if aplicados > 0:
        print(f"Se han aplicado {aplicados} correcciones. Guardando archivos...")
        
        # Save estado_traduccion.json
        temp_estado = estado_path + ".tmp"
        with open(temp_estado, "w", encoding="utf-8") as f:
            json.dump(estado_dict, f, indent=2, ensure_ascii=False) # Mantener identacion de 2 tipica
        shutil.move(temp_estado, estado_path)
        
        # Save errores_traduccion.json
        temp_errores = errores_path + ".tmp"
        with open(temp_errores, "w", encoding="utf-8") as f:
            json.dump(errores_dict, f, indent=4, ensure_ascii=False)
        shutil.move(temp_errores, errores_path)
        
        print(f"¡Éxito! {aplicados} líneas actualizadas en estado_traduccion.json y eliminadas de errores_traduccion.json.")
    else:
        print("No se encontraron campos 'nueva_traduccion' válidos para aplicar. No se modificó ningún archivo.")

if __name__ == "__main__":
    main()
