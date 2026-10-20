import pandas as pd
import os
from datetime import datetime
import pytz
from sqlalchemy import create_engine
import warnings

# Importamos tu función estrella (con la guillotina original)
from motor_etl import normalizar_y_limpiar_datos 

warnings.filterwarnings('ignore')

def subir_historico_antiguo():
    print("===================================================")
    print("🕰️ INICIANDO INGESTA DE HISTÓRICO (CORTADO Y CRUDO)")
    print("===================================================")
    
    carpeta_origen = 'correcciones'
    if not os.path.exists(carpeta_origen):
        print(f"❌ La carpeta '{carpeta_origen}' no existe.")
        return

    # Conexión a Supabase
    db_url = "postgresql://postgres.vdvmyueufdfviztmribf:Velasco14062000**@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    engine = create_engine(db_url)
    
    archivos_csv = [f for f in os.listdir(carpeta_origen) if f.endswith('.csv')]
    tz_colombia = pytz.timezone('America/Bogota')

    for archivo in archivos_csv:
        ruta_archivo = os.path.join(carpeta_origen, archivo)
        print(f"\n⏳ Procesando archivo histórico: {archivo}...")
        
        try:
            # Intentar primero con UTF-8
            try:
                df = pd.read_csv(ruta_archivo, encoding='utf-8-sig', low_memory=False)
            except UnicodeDecodeError:
                # Si Excel lo guardó en formato Windows antiguo (ANSI/Latin-1), usamos este salvavidas
                df = pd.read_csv(ruta_archivo, encoding='latin1', low_memory=False)
                
            print(f"   📊 Filas iniciales leídas por Pandas: {len(df)}")
            
            # --- LIMPIEZA UNIVERSAL (CON GUILLOTINA) ---
            # Para evitar que la regla de "dropna" borre chats de Bot, lo hacemos manual aquí:
            
            # 1. Normalización de Nombres
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            df.columns = df.columns.str.replace('.', '').str.replace('(', '').str.replace(')', '')
            df.columns = df.columns.str.replace('unnamed:_', 'unnamed_')
            df.columns = df.columns.str.replace('__', '_')

            if 'id' in df.columns:
                df.rename(columns={'id': 'id_original'}, inplace=True)
                
            # 2. Borrado Quirúrgico de Filas Vacías de Excel
            df_antes = len(df)
            if 'id_original' in df.columns:
                df = df.dropna(subset=['id_original'])
            elif 'cedula_del_cliente' in df.columns: # Alternativa para ventas
                df = df.dropna(subset=['cedula_del_cliente'])
            print(f"   🧹 Se limpiaron {df_antes - len(df)} filas vacías generadas por Excel.")
                
            # 3. Guillotina de Columnas Calculadas
            columna_corte = 'cuenta_atendido'
            if columna_corte in df.columns:
                indice = df.columns.get_loc(columna_corte)
                df = df.iloc[:, :indice]
                print(f"   🔪 Guillotina aplicada: Solo se conservan datos crudos (hasta '{columna_corte}').")

            # 4. Parche de Fechas Rebeldes (Forzamos al día 26) - (Aplica más a RRSS)
            columnas_de_fecha = ['fecha_inicio', 'fecha_asignación', 'fecha_atención', 'fecha_finalización']
            for col in columnas_de_fecha:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace('2025-06-22', '2025-06-26', regex=False)
                    df[col] = df[col].str.replace('22/06/2025', '26/06/2025', regex=False)
                    df[col] = df[col].str.replace('2025/06/22', '2025/06/26', regex=False)
                    df[col] = df[col].replace(['nan', 'NaN', 'None', 'NaT', ''], None)

            # 5. Gobernanza
            fecha_actual = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")
            df['etl_origen_archivo'] = f"HISTORICO_{archivo}"
            df['etl_lote_ejecucion'] = "CARGA_HISTORICA"
            df['etl_fecha_carga_col'] = fecha_actual
            
            # 6. Ruteo y Escudo de Seguridad Final
            archivo_lower = archivo.lower()
            
            if 'chats_monetizacion' in archivo_lower or 'chats_rrss' in archivo_lower:
                tabla = 'hist_chats_monetizacion_rrss'
                columnas_permitidas = [
                    'id_original', 'cola_de_atención', 'id_conversación', 'bot', 'canal', 
                    'nombre_del_cliente', 'identificacion_del_cliente', 'tipo_de_cliente', 
                    'fecha_inicio', 'fecha_asignación', 'fecha_atención', 'tiempo_en_espera', 
                    'tiempo_primera_respuesta', 'tiempo_de_asignación', 'tiempo_conversacion', 
                    'fecha_finalización', 'duración', 'cerrado_por', 'agente', 'skill', 
                    'recibida_por', 'login_agente',
                    'etl_origen_archivo', 'etl_lote_ejecucion', 'etl_fecha_carga_col'
                ]
                df = df[[c for c in df.columns if c in columnas_permitidas]]
                
            elif 'base_nps' in archivo_lower:
                tabla = 'hist_base_nps_rrss' 
                
            elif 'base_tipificaciones' in archivo_lower:
                tabla = 'hist_base_tipificaciones_rrss' 

            # 🌟 NUEVA RUTA PARA EL HISTÓRICO DE VENTAS
            elif 'ventas' in archivo_lower:
                tabla = 'hist_base_ventas_migraciones'
                
                # Renombrar columnas para alinear con Supabase
                renombres_ventas = {
                    'cédula_del_agente': 'cedula_del_agente',
                    'cédula_del_cliente': 'cedula_del_cliente',
                    'número_de_la_línea_a_portar,_migrar_o_línea_nueva_activada': 'numero_linea_gestionada',
                    'día': 'dia' 
                }
                df.rename(columns=renombres_ventas, inplace=True)
                
                if 'gestion' not in df.columns:
                    df['gestion'] = 'Migración Inbound'
                
                # Columnas permitidas incluyendo 'time'
                columnas_permitidas_ventas = [
                    'marca_temporal', 'nombre_del_asesor', 'cedula_del_agente', 'msisdn',
                    'cedula_del_cliente', 'numero_linea_gestionada', 'gestion', 'contactado',
                    'plan_vendido', 'canal_de_venta', 'supervisor', 'base_de_gestion', 'fecha_de_venta',
                    'mes', 'dia', 'time', 'etl_origen_archivo', 'etl_lote_ejecucion', 'etl_fecha_carga_col'
                ]
                
                df = df[[c for c in df.columns if c in columnas_permitidas_ventas]]
            else:
                print(f"   ⚠️ Archivo no reconocido para ruteo: {archivo}. Se ignora.")
                continue 

            # 7. Inyección
            df.to_sql(tabla, engine, if_exists='append', index=False)
            print(f"   ✅ Se inyectaron {len(df)} registros crudos en la tabla '{tabla}'.")

            
        except Exception as e:
            print(f"   ❌ Error al procesar {archivo}: {e}")

    print("\n🚀 PROCESO DE CARGA HISTÓRICA FINALIZADO.")

if __name__ == "__main__":
    subir_historico_antiguo()