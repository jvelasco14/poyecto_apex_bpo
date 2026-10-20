import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from supabase import create_client, Client
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Conexión a Supabase
SUPABASE_URL = "https://vdvmyueufdfviztmribf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdm15dWV1ZmRmdml6dG1yaWJmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MzI2MTAsImV4cCI6MjA5NjEwODYxMH0.JHxc5WePZakQq1TzjtCYP3GpEp09tjIMRIe13eUwqSo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_excel_time(val):
    try:
        if pd.isna(val) or val == '': return np.nan
        val_str = str(val).strip()
        if ':' in val_str:
            parts = val_str.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return float(val) * 86400
    except: return 0

def ejecutar_backfill():
    fecha_objetivo = "2025-06-25"
    fecha_ejecucion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alertas_micro_totales = []
    alertas_macro_totales = []

    print(f"🚀 INICIANDO VIAJE EN EL TIEMPO: BACKFILL DE IA PARA EL DÍA {fecha_objetivo}")

    # ==========================================================
    # 1. MIGRACIONES - MICRO Y MACRO
    # ==========================================================
    print("\n[1/3] Procesando MIGRACIONES INBOUND...")
    try:
        # --- MICRO ALERTAS ---
        resp_mig = supabase.table("hist_base_llamadas_migraciones").select("call_id, agent, talk_time, disposition, date, time").eq("date", fecha_objetivo).execute()
        df_live = pd.DataFrame(resp_mig.data)
        
        if not df_live.empty:
            df_live['segundos_hablados'] = pd.to_timedelta(df_live['talk_time'], errors='coerce').dt.total_seconds()
            df_live = df_live.dropna(subset=['segundos_hablados']) 
            
            if len(df_live) >= 10:
                modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
                df_live['prediccion_ia'] = modelo.fit_predict(df_live[['segundos_hablados']])
                
                for _, row in df_live.iterrows():
                    segundos = row['segundos_hablados']
                    disp = str(row['disposition']).upper()
                    es_outlier_matematico = row['prediccion_ia'] == -1
                    
                    es_venta_expres = ("VENTA" in disp or "ACEPTA" in disp) and segundos < 30
                    es_buzon_largo = ("BUZON" in disp or "ANSWERING MACHINE" in disp or "NO ANSWER" in disp) and segundos > 45
                    es_anomalia_extrema = es_outlier_matematico and (segundos > 900 or segundos < 5)

                    if es_venta_expres or es_buzon_largo or es_anomalia_extrema:
                        tipo_desc = "Venta Exprés Atípica (<30s)" if es_venta_expres else ("Buzón/No Contesta Prolongado" if es_buzon_largo else "Desviación Extrema de TMO")
                        
                        alertas_micro_totales.append({
                            "identificador_registro": str(row['call_id']),
                            "origen_datos": "Migraciones",
                            "tipo_alerta": tipo_desc,
                            "severidad": "ALTA" if es_venta_expres else "MEDIA",
                            "descripcion": f"Agente {row['agent']} tipificó '{row['disposition']}' con duración de {segundos} seg.",
                            "fecha_deteccion": fecha_ejecucion,
                            "call_date": row['date'],
                            "call_time": row['time']
                        })

        # --- MACRO ALERTAS ---
        df_macro_base = df_live.copy()
        if not df_macro_base.empty:
            # Función robusta para extracción de hora
            def extraer_solo_hora(t):
                try:
                    t_str = str(t).strip()
                    if ':' in t_str: return t_str.split(':')[0].zfill(2)
                    if t_str.replace('.', '', 1).isdigit(): return f"{int(float(t_str) * 24):02d}"
                    return None
                except: return None

            df_macro_base['hora'] = df_macro_base['time'].apply(extraer_solo_hora)
            df_macro_base = df_macro_base.dropna(subset=['hora'])
            
            df_macro = df_macro_base.groupby('hora').agg(volumen_llamadas=('call_id', 'count'), tmo_promedio=('segundos_hablados', 'mean')).reset_index()
            
            if len(df_macro) >= 3:
                modelo_macro = IsolationForest(n_estimators=100, contamination=0.25, random_state=42)
                df_macro['anomalia_hora'] = modelo_macro.fit_predict(df_macro[['volumen_llamadas', 'tmo_promedio']])
                
                horas_anomalas = df_macro[df_macro['anomalia_hora'] == -1]
                for _, row in horas_anomalas.iterrows():
                    alertas_macro_totales.append({
                        "identificador_registro": f"MACRO-{fecha_objetivo}-{row['hora']}",
                        "origen_datos": "Migraciones - Macro Tráfico",
                        "tipo_alerta": "Saturación / Anomalía Sistémica",
                        "severidad": "ALTA",
                        "descripcion": f"Franja horaria {row['hora']}:00 hrs presentó un flujo atípico con {int(row['volumen_llamadas'])} llamadas y TMO de {round(row['tmo_promedio'], 1)} seg.",
                        "fecha_deteccion": fecha_ejecucion,
                        "call_date": fecha_objetivo,
                        "call_time": f"{row['hora']}:00:00"
                    })
        
        print(f"   ✅ Migraciones: Analizado correctamente.")
    except Exception as e: print(f"❌ Error en Migraciones: {e}")

    # ==========================================================
    # 2. RETENCIONES OUTBOUND - MICRO
    # ==========================================================
    print("\n[2/3] Procesando RETENCIONES OUTBOUND...")
    try:
        resp_ret = supabase.table("hist_base_rete_out").select("id, date, time, agent, talk_time, disposition").eq("date", fecha_objetivo).execute()
        df_ret = pd.DataFrame(resp_ret.data)
        
        if not df_ret.empty:
            df_ret['segundos_hablados'] = df_ret['talk_time'].apply(parse_excel_time)
            df_live = df_ret.dropna(subset=['segundos_hablados', 'agent']).copy()
            df_live = df_live[df_live['segundos_hablados'] > 2]
            
            if not df_live.empty and len(df_live) >= 5:
                modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
                df_live['prediccion_ia'] = modelo.fit_predict(df_live[['segundos_hablados']])
                
                anomalias = df_live[df_live['prediccion_ia'] == -1]
                for _, row in anomalias.iterrows():
                    tip = row['disposition'] if pd.notna(row['disposition']) else 'Desconocida'
                    alertas_micro_totales.append({
                        "identificador_registro": str(row['id']),
                        "origen_datos": "Retenciones Outbound",
                        "tipo_alerta": "Anomalía TMO vs Tipificación",
                        "severidad": "MEDIA",
                        "descripcion": f"Agente {row['agent']} registró {round(row['segundos_hablados'])}s tipificando '{tip}'.",
                        "fecha_deteccion": fecha_ejecucion,
                        "call_date": row['date'],
                        "call_time": row['time']
                    })
            print(f"   ✅ Retenciones: Analizado correctamente.")
    except Exception as e: print(f"❌ Error en Retenciones: {e}")

    # ==========================================================
    # 3. REDES SOCIALES - MICRO
    # ==========================================================
    print("\n[3/3] Procesando REDES SOCIALES...")
    try:
        resp_chats = supabase.table("hist_chats_monetizacion_rrss").select("id_conversación, fecha_inicio, agente, tiempo_conversacion").like("fecha_inicio", f"{fecha_objetivo}%").execute()
        resp_tips = supabase.table("hist_base_tipificaciones_rrss").select("id_conversación, ekia_código").execute()
        
        df_chats = pd.DataFrame(resp_chats.data)
        if not df_chats.empty:
            df_chats.rename(columns={'id_conversación': 'id_conversacion'}, inplace=True)
            df_chats['fecha_dt'] = pd.to_datetime(df_chats['fecha_inicio'], errors='coerce')
            df_chats['date'] = df_chats['fecha_dt'].dt.strftime('%Y-%m-%d')
            df_chats['time'] = df_chats['fecha_dt'].dt.strftime('%H:%M:%S')
            
        df_tips = pd.DataFrame(resp_tips.data)
        if not df_tips.empty:
            df_tips.rename(columns={'id_conversación': 'id_conversacion', 'ekia_código': 'tipificacion'}, inplace=True)
        
        if not df_chats.empty and not df_tips.empty:
            df_master = pd.merge(df_chats, df_tips, on='id_conversacion', how='left')
            df_master['segundos_hablados'] = pd.to_timedelta(df_master['tiempo_conversacion'], errors='coerce').dt.total_seconds()
            df_live = df_master.dropna(subset=['segundos_hablados', 'agente']).copy()
            
            if not df_live.empty and len(df_live) >= 5:
                modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
                df_live['prediccion_ia'] = modelo.fit_predict(df_live[['segundos_hablados']])
                
                anomalias = df_live[df_live['prediccion_ia'] == -1]
                for _, row in anomalias.iterrows():
                    tip = row['tipificacion'] if pd.notna(row['tipificacion']) else 'Sin Tipificar'
                    
                    alertas_micro_totales.append({
                        "identificador_registro": str(row['id_conversacion']),
                        "origen_datos": "Redes Sociales",
                        "tipo_alerta": "Anomalía TMO en Chat (Posible Evasión)",
                        "severidad": "MEDIA",
                        "descripcion": f"Agente {row['agente']} registró un tiempo de {row['segundos_hablados']}s tipificando '{tip}'.",
                        "fecha_deteccion": fecha_ejecucion,
                        "call_date": row['date'],
                        "call_time": row['time']
                    })
            print(f"   ✅ Redes Sociales: Analizado correctamente.")
    except Exception as e: print(f"❌ Error en RRSS: {e}")

    # ==========================================================
    # 💾 INYECCIÓN EN BASE DE DATOS
    # ==========================================================
    print("\n💾 Inyectando datos en Supabase...")
    if alertas_micro_totales:
        print(f"   Inyectando {len(alertas_micro_totales)} micro-alertas a ml_alertas_globales...")
        supabase.table("ml_alertas_globales").upsert(alertas_micro_totales).execute()
        print("   ✔️ Micro-Alertas guardadas exitosamente.")
    else:
        print("   ✔️ 0 Micro-Alertas para guardar.")
    
    if alertas_macro_totales:
        print(f"   Inyectando {len(alertas_macro_totales)} macro-alertas a ml_alertas_macro...")
        supabase.table("ml_alertas_macro").upsert(alertas_macro_totales).execute()
        print("   ✔️ Macro-Alertas guardadas exitosamente.")
    else:
        print("   ✔️ 0 Macro-Alertas para guardar.")

    print("\n🏁 VIAJE EN EL TIEMPO COMPLETADO EXITOSAMENTE.")

if __name__ == "__main__":
    ejecutar_backfill()