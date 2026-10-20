import pandas as pd
import os

def convertir_a_csv():
    # Carpeta donde están los archivos Excel originales
    carpeta_origen = 'correcciones' # CÁMBIALO a 'data_historico_antiguo' si tienes los archivos ahí

    # Verificar si la carpeta existe
    if not os.path.exists(carpeta_origen):
        print(f"❌ La carpeta '{carpeta_origen}' no existe. Por favor créala y pon tus Excel ahí.")
        return

    # Buscar todos los archivos Excel sin importar su formato (.xlsx, .xlsm, .xls)
    try:
        archivos_en_carpeta = os.listdir(carpeta_origen)
        archivos_excel = [
            os.path.join(carpeta_origen, f) 
            for f in archivos_en_carpeta 
            if f.lower().endswith(('.xlsx', '.xlsm', '.xls','.csv'))
        ]
    except FileNotFoundError:
        print(f"❌ Error al leer la carpeta '{carpeta_origen}'.")
        return

    if not archivos_excel:
        print(f"⚠️ No se encontraron archivos Excel (.xlsx, .xlsm, .xls) en '{carpeta_origen}'.")
        return

    print(f"📁 Iniciando conversión en '{carpeta_origen}'...")
    print("-" * 40)

    # Procesar cada archivo
    for ruta_excel in archivos_excel:
        nombre_archivo = os.path.basename(ruta_excel)
        
        # Cambiar de forma segura cualquier extensión de Excel a .csv
        # os.path.splitext separa el nombre de la extensión, ej: ('chats', '.xlsm')
        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        nombre_csv = f"{nombre_sin_ext}.csv"
        ruta_csv = os.path.join(carpeta_origen, nombre_csv)

        print(f"⏳ Convirtiendo: {nombre_archivo} ...")

        try:
            # 1. Leer el Excel tal cual está (Pandas lee .xlsm sin problemas con openpyxl)
            df = pd.read_excel(ruta_excel)
            
            # 2. Guardarlo como CSV delimitado por comas sin hacerle nada más
            df.to_csv(ruta_csv, index=False, encoding='utf-8-sig')
            
            print(f"  ✅ Creado: {nombre_csv}")
            
        except Exception as e:
            print(f"  ❌ Error al convertir {nombre_archivo}: {e}")

    print("-" * 40)
    print(f"🚀 CONVERSIÓN FINALIZADA. Tus archivos .csv están listos en la carpeta '{carpeta_origen}'.")

if __name__ == "__main__":
    convertir_a_csv()