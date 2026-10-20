import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

def parse_excel_time(val):
    """Parche para convertir formatos mixtos de tiempo (HH:MM:SS o decimal Excel) a segundos"""
    try:
        if pd.isna(val) or val == '': return np.nan
        val_str = str(val).strip()
        if ':' in val_str:
            parts = val_str.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return float(val) * 86400
    except:
        return 0

def analizar_retenciones(engine, modo, tz_colombia):
    """Módulo de IA para Retenciones Outbound (100% Automatizado)"""
    fecha_actual_completa = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")
    fecha_analisis_fija = '2025-06-26'

    # ==========================================================
    # ⏱️ ANÁLISIS 1: TIEMPO REAL (HORA A HORA) - RADAR
    # ==========================================================
    if modo == 'horario':
        print("\n🔍 [RETENCIONES - LIVE] Evaluando tiempos y tipificaciones...")
        
        try:
            # 🔧 CORRECCIÓN: Extraemos el 'id' único de la DB, 'date' y 'time'
            query_live = """
                SELECT 
                    id as db_id,
                    date,
                    time,
                    agent as agente, 
                    talk_time, 
                    disposition as tipificacion 
                FROM base_rete_out 
                WHERE talk_time IS NOT NULL
            """
            df_live = pd.read_sql_query(query_live, engine)

            if len(df_live) < 5:
                print("   ⚠️ Datos insuficientes en Retenciones en esta hora.")
                return

            df_live['segundos_hablados'] = df_live['talk_time'].apply(parse_excel_time)
            df_live = df_live.dropna(subset=['segundos_hablados', 'agente'])
            
            df_live = df_live[df_live['segundos_hablados'] > 2]

            if df_live.empty:
                print("   ⚠️ No hay llamadas con tiempo válido para analizar.")
                return

            modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
            df_live['prediccion_ia'] = modelo.fit_predict(df_live[['segundos_hablados']])
            
            anomalias = df_live[df_live['prediccion_ia'] == -1].copy()

            if not anomalias.empty:
                print(f"   🚨 ¡Se detectaron {len(anomalias)} llamadas anómalas en Retenciones!")
                
                alertas_df = pd.DataFrame()
                alertas_df['origen_datos'] = ['Retenciones Outbound'] * len(anomalias)
                alertas_df['tipo_alerta'] = ['Anomalía TMO vs Tipificación'] * len(anomalias)
                alertas_df['severidad'] = ['MEDIA'] * len(anomalias)
                
                descripciones = []
                for _, row in anomalias.iterrows():
                    tip = row['tipificacion'] if pd.notna(row['tipificacion']) else 'Desconocida'
                    descripciones.append(f"Agente {row['agente']} registró {round(row['segundos_hablados'])}s tipificando '{tip}'.")
                alertas_df['descripcion'] = descripciones
                
                # 🔧 CORRECCIÓN PANDAS: Agregar .values para evitar el desajuste de índices (NaN)
                alertas_df['identificador_registro'] = anomalias['db_id'].astype(str).values
                alertas_df['call_date'] = anomalias['date'].values
                alertas_df['call_time'] = anomalias['time'].values
                
                alertas_df['fecha_deteccion'] = fecha_actual_completa

                query_exist = "SELECT identificador_registro FROM ml_alertas_globales WHERE origen_datos = 'Retenciones Outbound'"
                try:
                    df_exist = pd.read_sql_query(query_exist, engine)
                    alertas_nuevas = alertas_df[~alertas_df['identificador_registro'].isin(df_exist['identificador_registro'].tolist())]
                except Exception:
                    alertas_nuevas = alertas_df

                if not alertas_nuevas.empty:
                    alertas_nuevas.to_sql('ml_alertas_globales', engine, if_exists='append', index=False)
                    print(f"   💾 {len(alertas_nuevas)} alertas de Retenciones disparadas.")
                else:
                    print("   ℹ️ Anomalías de Retenciones ya reportadas.")
            else:
                print("   ✅ Operación de Retenciones fluyendo con normalidad.")

        except Exception as e:
            print(f"   ❌ Error en análisis horario Retenciones: {e}")

    # 🧠 ANÁLISIS 2: CIERRE DE JORNADA (AUTOMATIZADO ÚLTIMO DÍA)
    # ==========================================================
    elif modo == 'cierre':
        print("\n🧠 [RETENCIONES - DEEP INSIGHTS] Ejecutando clustering para el último día consolidado...")

    try:
        # 1. Identificar dinámicamente cuál fue el último día
        query_max_date = "SELECT MAX(date) as ultima_fecha FROM hist_base_rete_out WHERE date IS NOT NULL AND date != ''"
        df_max = pd.read_sql_query(query_max_date, engine)
        ultima_fecha = df_max['ultima_fecha'].iloc[0]

        if not ultima_fecha:
            print("   ⚠️ No se encontraron fechas válidas en el histórico de Retenciones.")
            return

        print(f"   📅 Procesando el consolidado de Retenciones del día: {ultima_fecha}")

        # 2. Extraer SOLO la data de ese último día
        query_hist = f"""
            SELECT agent as agente, talk_time, disposition as tipificacion, date
            FROM hist_base_rete_out
            WHERE agent IS NOT NULL AND agent != '[None]' AND date = '{ultima_fecha}'
        """
        df_hist = pd.read_sql_query(query_hist, engine)

        if df_hist.empty:
            print("   ⚠️ No hay datos suficientes en Retenciones para este día.")
            return

        df_hist['tmo_segundos'] = df_hist['talk_time'].apply(parse_excel_time).fillna(0)

        no_efectivas = ['no answer', 'buzon', 'hangup', 'abandon', 'machine', 'muda']
        df_hist['es_efectiva'] = df_hist['tipificacion'].astype(str).str.lower().apply(
            lambda x: 0 if any(b in x for b in no_efectivas) else 1
        )
        df_hist['es_retencion'] = df_hist['tipificacion'].astype(str).str.lower().apply(
            lambda x: 1 if 'retenci' in x else 0
        )

        agentes_kpi = df_hist.groupby('agente').agg(
            total_llamadas=('agente', 'count'),
            llamadas_efectivas=('es_efectiva', 'sum'),
            total_retenciones=('es_retencion', 'sum'),
            tmo_promedio=('tmo_segundos', 'mean')
        ).reset_index()

        agentes_kpi = agentes_kpi[agentes_kpi['llamadas_efectivas'] > 3].copy()

        if agentes_kpi.empty:
            print(f"   ⚠️ Ningún agente cumplió el mínimo de llamadas efectivas el {ultima_fecha}.")
            return

        agentes_kpi['efectividad'] = (agentes_kpi['total_retenciones'] / agentes_kpi['llamadas_efectivas']) * 100

        if len(agentes_kpi) >= 3:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(agentes_kpi[['efectividad', 'tmo_promedio']])

            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            agentes_kpi['cluster_id'] = kmeans.fit_predict(X_scaled)

            cluster_medias = agentes_kpi.groupby('cluster_id')['efectividad'].mean().sort_values()
            nombres_clusters = {
                cluster_medias.index[0]: 'Área de Oportunidad (Baja Retención)',
                cluster_medias.index[1]: 'Estándar (Cierre Medio)',
                cluster_medias.index[2]: 'Top Performers (Cerradores Estrella)'
            }
            agentes_kpi['cluster_nombre'] = agentes_kpi['cluster_id'].map(nombres_clusters)

            insights_df = pd.DataFrame()
            insights_df['fecha_analisis'] = [ultima_fecha] * len(agentes_kpi)
            insights_df['tipo_insight'] = ['K-Means (Efectividad vs TMO)'] * len(agentes_kpi)
            insights_df['agente'] = agentes_kpi['agente'].astype(str).values
            insights_df['cluster_nombre'] = agentes_kpi['cluster_nombre'].values
            insights_df['metrica_principal'] = round(agentes_kpi['efectividad'], 2).values
            insights_df['metrica_secundaria'] = round(agentes_kpi['tmo_promedio'], 2).values
            insights_df['fecha_ejecucion'] = fecha_actual_completa

            # Evitar duplicados
            try:
                with engine.begin() as conn:
                    conn.execute(f"DELETE FROM ml_insights_retenciones WHERE fecha_analisis = '{ultima_fecha}'")
            except Exception:
                pass

            insights_df.to_sql('ml_insights_retenciones', engine, if_exists='append', index=False)
            print(f"   ✅ [{ultima_fecha}] Perfilados {len(insights_df)} agentes de Retenciones.")
        else:
            print(f"   ⚠️ Agentes insuficientes en Retenciones para K-Means en el día {ultima_fecha}.")

    except Exception as e:
        print(f"   ❌ Error en análisis de cierre Retenciones: {e}")