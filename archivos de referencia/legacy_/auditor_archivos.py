import pandas as pd
import os
import warnings

# Ocultar advertencias molestas en la terminal
warnings.filterwarnings('ignore')

def analizar_archivos_correcciones():
    carpeta = 'correcciones'
    
    print("===================================================")
    print(f"📊 INICIANDO AUDITORÍA DE LA CARPETA '{carpeta.upper()}'")
    print("===================================================")
    
    if not os.path.exists(carpeta):
        print(f"❌ La carpeta '{carpeta}' no existe. Por favor créala y añade archivos.")
        return
        
    # Buscar archivos de datos válidos
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith(('.csv', '.xlsx', '.xlsm', '.xls'))]
    
    if not archivos:
        print(f"📭 No se encontraron archivos de datos (CSV o Excel) en '{carpeta}'.")
        return
        
    for archivo in archivos:
        ruta_archivo = os.path.join(carpeta, archivo)
        print(f"\n📄 Archivo: {archivo}")
        print("-" * 50)
        
        try:
            # 1. Leer el archivo dependiendo de su formato
            if archivo.lower().endswith('.csv'):
                df = pd.read_csv(ruta_archivo, encoding='utf-8-sig', low_memory=False)
            else:
                df = pd.read_excel(ruta_archivo)
            
            # ---------------------------------------------------------
            # 🧹 MAGIA: ELIMINAR FILAS Y COLUMNAS 100% FANTASMAS
            # ---------------------------------------------------------
            # Elimina filas donde ABSOLUTAMENTE TODOS los valores son nulos/vacíos
            df = df.dropna(how='all')
            
            # (Opcional) Elimina columnas que también estén 100% vacías
            df = df.dropna(axis=1, how='all')
            # ---------------------------------------------------------
                
            # 2. Extraer dimensiones reales
            filas, columnas = df.shape
            print(f"   🔹 Filas con datos reales: {filas:,}")
            print(f"   🔹 Total de Columnas:      {columnas}")
            
            # 3. Mostrar los nombres de las columnas
            columnas_lista = df.columns.tolist()
            print("   🔹 Nombres de Columnas:")
            
            # Si hay más de 15 columnas, muestra un resumen para no saturar la terminal
            if columnas > 15:
                print(f"      {columnas_lista[:10]} ... \n      [+ {columnas - 10} columnas adicionales ocultas por espacio]")
            else:
                print(f"      {columnas_lista}")
            
            # 4. Información extra de calidad de datos (celdas vacías internas)
            vacios_totales = df.isna().sum().sum()
            print(f"   🔹 Celdas vacías (internas): {vacios_totales:,} espacios nulos en la data")
            
        except Exception as e:
            print(f"   ❌ Error al intentar leer este archivo: {e}")
            
    print("\n===================================================")
    print("🚀 AUDITORÍA FINALIZADA")
    print("===================================================")

if __name__ == "__main__":
    analizar_archivos_correcciones()