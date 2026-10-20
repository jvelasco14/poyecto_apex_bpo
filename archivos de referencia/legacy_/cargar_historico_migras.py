import pandas as pd
import os
from datetime import datetime
import pytz
from sqlalchemy import create_engine
import warnings

# Importamos tu función estrella para garantizar que la limpieza sea idéntica al ETL en vivo
from motor_etl import normalizar_y_limpiar_datos 

warnings.filterwarnings('ignore')

def subir_historico_antiguo():
    print("===================================================")
    print("🕰️ INICIANDO INGESTA DE HISTÓRICO ANTIGUO")
    print("===================================================")
    
    carpeta_origen = 'correcciones'
    if not os.path.exists(carpeta_origen):
        print(f"❌ La carpeta '{carpeta_origen}' no existe. Créala y coloca los archivos .csv allí.")
        return

    # Conexión a Supabase
    db_url = "postgresql://postgres.vdvmyueufdfviztmribf:Velasco14062000**@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    engine = create_engine(db_url)
    
    archivos_csv = [f for f in os.listdir(carpeta_origen) if f.endswith('.csv')]
    
    if not archivos_csv:
        print(f"📭 No hay archivos CSV en la carpeta '{carpeta_origen}'.")
        return

    # Establecer la zona horaria de Colombia
    tz_colombia = pytz.timezone('America/Bogota')

    for archivo in archivos_csv:
        ruta_archivo = os.path.join(carpeta_origen, archivo)
        print(f"\n⏳ Procesando archivo histórico: {archivo}...")
        
        try:
            df = pd.read_csv(ruta_archivo, encoding='utf-8-sig', low_memory=False)
            
            # --- LIMPIEZA UNIVERSAL EXACTAMENTE IGUAL AL ETL EN VIVO ---
            df = normalizar_y_limpiar_datos(df)

            # ---------------------------------------------------------
            # 🗑️ IGNORAR COLUMNAS FANTASMAS DE EXCEL (llave, cc)
            # ---------------------------------------------------------
            columnas_fantasmas = ['llave', 'cc']
            df = df.drop(columns=[col for col in columnas_fantasmas if col in df.columns], errors='ignore')

            # ---------------------------------------------------------
            # 🛠️ PARCHE: CORRECCIÓN DE FORMATOS RAROS DE TIEMPO
            # ---------------------------------------------------------
            # Estandarizamos minúsculas primero para evitar fallos de case sensitivity
            df.columns = df.columns.str.strip().str.lower()
            
            if 'día' in df.columns:
                df['día'] = df['día'].astype(str).str.extract(r'(\d+)')[0]
                df['día'] = pd.to_numeric(df['día'], errors='coerce').fillna(0).astype(int)
                
            if 'mes' in df.columns:
                df['mes'] = pd.to_numeric(df['mes'], errors='coerce').fillna(0).astype(int)
                
            if 'año' in df.columns:
                df['año'] = pd.to_numeric(df['año'], errors='coerce').fillna(0).astype(int)

            # ---------------------------------------------------------
            # 🔄 MAPEO DE COLUMNAS A REGLAS DE GOBERNANZA SUPABASE
            # ---------------------------------------------------------
            mapeo_columnas = {
                'cédula_del_agente': 'cedula_del_agente',
                'cédula_del_cliente': 'cedula_del_cliente',
                'número_de_la_línea_a_portar,_migrar_o_línea_nueva_activada': 'numero_linea_gestionada',
                'número_de_la_línea_a_portar_migrar_o_línea_nueva_activada': 'numero_linea_gestionada', # Por si viene sin la coma
                'gestión': 'gestion',
                'base_de_gestión': 'base_de_gestion',
                'día': 'dia'
            }
            df = df.rename(columns=mapeo_columnas)

            # Capturar la fecha y hora exacta del sistema en este momento
            fecha_actual = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")

            # --- GOBERNANZA DE DATOS ---
            df['etl_origen_archivo'] = f"HISTORICO_{archivo}"
            df['etl_lote_ejecucion'] = "CARGA_HISTORICA_MASIVA"
            df['etl_fecha_carga_col'] = fecha_actual
            
            # --- RUTEO EXCLUSIVO A TABLAS HISTÓRICAS (hist_) ---
            archivo_lower = archivo.lower()
            if 'ventas_26_06_2025' in archivo_lower:
                tabla = 'hist_base_ventas_migraciones'
            else:
                print(f"   ⚠️ Archivo no reconocido para ruteo: {archivo}. Se ignora.")
                continue 

            # Inyectar a la base de datos
            df.to_sql(tabla, engine, if_exists='append', index=False)
            print(f"   ✅ Se inyectaron {len(df)} registros semilla en la tabla '{tabla}'.")

        except Exception as e:
            print(f"   ❌ Error al procesar {archivo}: {e}")

    print("\n🚀 PROCESO DE CARGA HISTÓRICA FINALIZADO.")

if __name__ == "__main__":
    subir_historico_antiguo()