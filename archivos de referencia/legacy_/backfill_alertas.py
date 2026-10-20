import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ CONFIGURACIÓN DE CONEXIÓN
# ==========================================
DB_URL = "postgresql://postgres.vdvmyueufdfviztmribf:Velasco14062000**@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
engine = create_engine(DB_URL)

def limpiar_tiempo(val):
    if pd.isna(val) or val == '': return 0
    val = str(val).strip()
    try:
        if ':' in val:
            h, m, s = map(int, val.split(':'))
            return h * 3600 + m * 60 + s
        if '.' in val or val.isdigit():
            num = float(val)
            if num < 1: return num * 86400
            return num
    except:
        pass
    return 0

print("🚀 Iniciando Máquina del Tiempo: Backfill de Anomalías (Isolation Forest)")

# ==========================================
# 1. PROCESAR HISTÓRICO DE MIGRACIONES
# ==========================================
print("\n📦 Extrayendo histórico de Migraciones...")
df_mig = pd.read_sql_query("SELECT call_id, agent, talk_time, disposition, date, time FROM hist_base_llamadas_migraciones WHERE date IS NOT NULL AND date != ''", engine)

if not df_mig.empty:
    df_mig['tmo_segundos'] = df_mig['talk_time'].apply(limpiar_tiempo)
    alertas_mig = []
    fechas = df_mig['date'].unique()
    
    for fecha in fechas:
        df_dia = df_mig[df_mig['date'] == fecha].copy()
        if len(df_dia) < 10: continue
        
        # 1. Isolation Forest (Desviación TMO)
        iso_forest = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
        df_dia['anomalia_if'] = iso_forest.fit_predict(df_dia[['tmo_segundos']])
        
        anomalos = df_dia[df_dia['anomalia_if'] == -1]
        for _, row in anomalos.iterrows():
            alertas_mig.append({
                "fecha_deteccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tipo_alerta": "Anomalía TMO vs Tipificación",
                "descripcion": f"Agente {row['agent']} registró {round(row['tmo_segundos'],1)}s tipificando '{row['disposition']}'.",
                "severidad": "MEDIA",
                "origen_datos": "Migraciones",
                "identificador_registro": row['call_id'],
                "call_date": row['date'],
                "call_time": row['time'],
                "asesor_id": row['agent']
            })
            
        # 2. Ventas Exprés
        ventas = df_dia[df_dia['disposition'].str.contains('Venta Facturada', case=False, na=False)]
        ventas_expres = ventas[ventas['tmo_segundos'] < 30]
        for _, row in ventas_expres.iterrows():
            alertas_mig.append({
                "fecha_deteccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tipo_alerta": "Venta Exprés Atípica (<30s)",
                "descripcion": f"Agente {row['agent']} tipificó 'Venta Facturada' en solo {round(row['tmo_segundos'],1)}s.",
                "severidad": "CRÍTICA",
                "origen_datos": "Migraciones",
                "identificador_registro": row['call_id'],
                "call_date": row['date'],
                "call_time": row['time'],
                "asesor_id": row['agent']
            })
    
    if alertas_mig:
        df_alertas_mig = pd.DataFrame(alertas_mig)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM hist_ml_alertas_globales WHERE origen_datos = 'Migraciones'"))
        df_alertas_mig.to_sql('hist_ml_alertas_globales', engine, if_exists='append', index=False)
        print(f"   ✅ Se inyectaron {len(alertas_mig)} micro-anomalías históricas de Migraciones.")

# ==========================================
# 2. PROCESAR HISTÓRICO DE RETENCIONES
# ==========================================
print("\n📦 Extrayendo histórico de Retenciones...")
df_ret = pd.read_sql_query("SELECT call_id, agent, talk_time, disposition, date, time FROM hist_base_rete_out WHERE date IS NOT NULL AND date != ''", engine)

if not df_ret.empty:
    df_ret['tmo_segundos'] = df_ret['talk_time'].apply(limpiar_tiempo)
    alertas_ret = []
    fechas = df_ret['date'].unique()
    
    for fecha in fechas:
        df_dia = df_ret[df_ret['date'] == fecha].copy()
        if len(df_dia) < 10: continue
        
        iso_forest = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
        df_dia['anomalia_if'] = iso_forest.fit_predict(df_dia[['tmo_segundos']])
        
        anomalos = df_dia[df_dia['anomalia_if'] == -1]
        for _, row in anomalos.iterrows():
            alertas_ret.append({
                "fecha_deteccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tipo_alerta": "Anomalía TMO vs Tipificación",
                "descripcion": f"Agente {row['agent']} registró {round(row['tmo_segundos'],1)}s tipificando '{row['disposition']}'.",
                "severidad": "MEDIA",
                "origen_datos": "Retenciones Outbound",
                "identificador_registro": row['call_id'],
                "call_date": row['date'],
                "call_time": row['time'],
                "asesor_id": row['agent']
            })
    
    if alertas_ret:
        df_alertas_ret = pd.DataFrame(alertas_ret)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM hist_ml_alertas_globales WHERE origen_datos = 'Retenciones Outbound'"))
        df_alertas_ret.to_sql('hist_ml_alertas_globales', engine, if_exists='append', index=False)
        print(f"   ✅ Se inyectaron {len(alertas_ret)} micro-anomalías históricas de Retenciones.")

print("\n🏁 Backfill Histórico completado con éxito. Tus tablas están listas para el dashboard.")