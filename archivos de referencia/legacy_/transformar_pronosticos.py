import pandas as pd
import numpy as np

# 1. Cargar el archivo original
file_path = "pronosticos_cd.xlsx"
df_raw = pd.read_excel(file_path, sheet_name=0, header=None)

# 2. Inicializar la lista maestra donde guardaremos todo en vertical
registros_limpios = []
canal_actual = "Desconocido"
fechas_columnas = []

# 3. Recorrer el Excel fila por fila para desarmar los bloques
for index, row in df_raw.iterrows():
    val_primera_celda = str(row[0]).strip()
    
    # Si la primera celda dice algo como "RRSS Unicos" o "WhatsApp Unicos", ese es el Canal
    if val_primera_celda and not val_primera_celda.replace(':', '').isdigit() and val_primera_celda not in ['Fecha', 'nan']:
        canal_actual = val_primera_celda
        continue
        
    # Si la primera celda dice "Fecha", extraemos las fechas de esa fila
    if val_primera_celda == "Fecha":
        # Tomamos todas las columnas de la fila actual (saltando la primera que dice "Fecha")
        fechas_columnas = row[1:].values
        continue
        
    # Si la primera celda tiene un formato de hora (ej: "00:30:00")
    if ":" in val_primera_celda:
        hora_actual = val_primera_celda
        
        # Iteramos sobre las celdas de esa fila (los valores numéricos pronosticados)
        for col_idx in range(1, len(row)):
            valor_pronostico = row[col_idx]
            fecha_correspondiente = fechas_columnas[col_idx - 1]
            
            # Filtramos basuras (NaN, nulos o fechas vacías)
            if pd.notna(valor_pronostico) and pd.notna(fecha_correspondiente):
                
                # Limpiar Fecha (Convertir a YYYY-MM-DD puro)
                try:
                    fecha_limpia = pd.to_datetime(fecha_correspondiente).strftime('%Y-%m-%d')
                except:
                    continue # Si la columna no era fecha (Ej: "INTERVALO HORA"), la saltamos
                
                # Limpiar y redondear pronóstico (1.59 -> 2)
                volumen_redondeado = int(round(float(valor_pronostico)))
                
                registros_limpios.append({
                    "fecha": fecha_limpia,
                    "hora": hora_actual,
                    "canal": canal_actual,
                    "volumen_esperado": volumen_redondeado
                })

# 4. Crear el DataFrame final limpio
df_final = pd.DataFrame(registros_limpios)

# 5. Exportar el CSV (Listo para Supabase)
nombre_salida = "pronosticos_rrss_listo.csv"
df_final.to_csv(nombre_salida, index=False)

print(f"✅ ¡Éxito! El archivo se transformó de matriz horizontal a formato vertical.")
print(f"💾 Guardado como: {nombre_salida} con {len(df_final)} registros.")
print(df_final.head(10))