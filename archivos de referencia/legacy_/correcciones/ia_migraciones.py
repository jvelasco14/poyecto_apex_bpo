import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

def analizar_tendencia_horaria(engine, fecha_solo_dia, fecha_actual_completa):
    """🧠 MACRO-IA: Análisis de Series Temporales Multivariadas por Hora (Volumen vs TMO)"""
    print("\n📈 [MACRO-IA] Evaluando comportamiento macro del embudo por hora...")
    
    try:
        # Consulta robusta adaptada para leer cualquier registro disponible en la tabla base
        query_macro = """
            SELECT 
                SUBSTRING(CAST(time AS TEXT), 1, 2) AS hora,
                COUNT(call_id) as volumen_llamadas,
                AVG(CASE WHEN talk_time IS NOT NULL THEN EXTRACT(EPOCH FROM CAST(talk_time AS INTERVAL)) ELSE 0 END) as tmo_promedio
            FROM base_llamadas_migraciones
            WHERE time IS NOT NULL
            GROUP BY SUBSTRING(CAST(time AS TEXT), 1, 2)
            ORDER BY hora;
        """
        df_macro = pd.read_sql_query(query_macro, engine)
        
        # Imprimamos cuántas horas encontró para depurar de inmediato
        print(f"   📊 Filas horarias detectadas para macro-análisis: {len(df_macro)}")

        if len(df_macro) < 1:
            print("   ⚠️ Datos horarios insuficientes para análisis macro de tendencias.")
            return
        
        # ==========================================================
        # 🚀 APLICACIÓN DE ISOLATION FOREST MULTIVARIADO (MACRO)
        # ==========================================================
        X_macro = df_macro[['volumen_llamadas', 'tmo_promedio']]
        modelo_macro = IsolationForest(n_estimators=100, contamination=0.25, random_state=42)
        df_macro['anomalia_hora'] = modelo_macro.fit_predict(X_macro)
        
        horas_anomalas = df_macro[df_macro['anomalia_hora'] == -1]
        
        if not horas_anomalas.empty:
            print(f"   🚨 ¡Se detectaron {len(horas_anomalas)} anomalías macro en el flujo horario!")
            
            alertas_macro_df = pd.DataFrame()
            alertas_macro_df['origen_datos'] = ['Migraciones - Macro Tráfico'] * len(horas_anomalas)
            alertas_macro_df['tipo_alerta'] = ['Saturación / Anomalía Sistémica'] * len(horas_anomalas)
            alertas_macro_df['severidad'] = ['ALTA'] * len(horas_anomalas)
            
            descripciones = []
            for _, row in horas_anomalas.iterrows():
                descripciones.append(f"Franja horaria {row['hora']}:00 hrs presentó un flujo atípico con {row['volumen_llamadas']} llamadas y TMO de {round(row['tmo_promedio'], 1)} seg.")
            alertas_macro_df['descripcion'] = descripciones
            
            alertas_macro_df['identificador_registro'] = [f"MACRO-{fecha_solo_dia}-{row['hora']}" for _, row in horas_anomalas.iterrows()]
            alertas_macro_df['call_date'] = [fecha_solo_dia] * len(horas_anomalas)
            alertas_macro_df['call_time'] = [f"{row['hora']}:00:00" for _, row in horas_anomalas.iterrows()]
            alertas_macro_df['fecha_deteccion'] = fecha_actual_completa

            # Guardar en la NUEVA tabla ml_alertas_macro
            query_exist = "SELECT identificador_registro FROM ml_alertas_macro"
            try:
                df_exist = pd.read_sql_query(query_exist, engine)
                existentes = df_exist['identificador_registro'].tolist()
                alertas_nuevas = alertas_macro_df[~alertas_macro_df['identificador_registro'].isin(existentes)]
            except Exception:
                alertas_nuevas = alertas_macro_df

            if not alertas_nuevas.empty:
                alertas_nuevas.to_sql('ml_alertas_macro', engine, if_exists='append', index=False)
                print(f"   💾 {len(alertas_nuevas)} macro-alertas guardadas en la tabla dedicada 'ml_alertas_macro'.")
            else:
                print("   ℹ️ Las macro-alertas ya estaban reportadas.")
        else:
            print("   ✅ Tráfico macro por hora dentro de parámetros normales.")

    except Exception as e:
        print(f"   ❌ Error en análisis macro de series temporales: {e}")


def analizar_migraciones(engine, modo, tz_colombia):
    """Módulo de Inteligencia Artificial exclusivo para Migraciones"""
    fecha_actual_completa = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")
    fecha_solo_dia = "2025-06-26" 

    if modo == 'horario':
        print("\n🔍 [MIGRACIONES - LIVE] Buscando micro-anomalías operativas...")
        
        try:
            query_live = """
                SELECT call_id, agent, talk_time, disposition, date, time 
                FROM base_llamadas_migraciones 
                WHERE talk_time IS NOT NULL AND talk_time != 'NaN'
            """
            df_live = pd.read_sql_query(query_live, engine)

            if len(df_live) >= 10:
                df_live['segundos_hablados'] = pd.to_timedelta(df_live['talk_time'], errors='coerce').dt.total_seconds()
                df_live = df_live.dropna(subset=['segundos_hablados']) 

                modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
                df_live['prediccion_ia'] = modelo.fit_predict(df_live[['segundos_hablados']])
                
                anomalias_filtradas = []
                for _, row in df_live.iterrows():
                    segundos = row['segundos_hablados']
                    disp = str(row['disposition']).upper()
                    es_outlier_matematico = row['prediccion_ia'] == -1
                    
                    es_venta_expres = ("VENTA" in disp or "ACEPTA" in disp) and segundos < 30
                    es_buzon_largo = ("BUZON" in disp or "ANSWERING MACHINE" in disp or "NO ANSWER" in disp) and segundos > 45
                    es_anomalia_extrema = es_outlier_matematico and (segundos > 900 or segundos < 5)

                    if es_venta_expres or es_buzon_largo or es_anomalia_extrema:
                        tipo_desc = "Venta Exprés Atípica (<30s)" if es_venta_expres else ("Buzón/No Contesta Prolongado" if es_buzon_largo else "Desviación Extrema de TMO")
                        
                        anomalias_filtradas.append({
                            'call_id': row['call_id'], 'agent': row['agent'], 'disposition': row['disposition'],
                            'segundos': segundos, 'tipo_alerta': tipo_desc, 'severidad': 'ALTA' if es_venta_expres else 'MEDIA',
                            'date': row['date'], 'time': row['time']
                        })

                anomalias = pd.DataFrame(anomalias_filtradas)

                if not anomalias.empty:
                    alertas_df = pd.DataFrame()
                    alertas_df['origen_datos'] = ['Migraciones'] * len(anomalias)
                    alertas_df['tipo_alerta'] = anomalias['tipo_alerta']
                    alertas_df['severidad'] = anomalias['severidad']
                    alertas_df['descripcion'] = [f"Agente {r['agent']} tipificó '{r['disposition']}' con duración de {r['segundos']} seg." for _, r in anomalias.iterrows()]
                    alertas_df['identificador_registro'] = anomalias['call_id'].astype(str)
                    alertas_df['call_date'] = anomalias['date'].values
                    alertas_df['call_time'] = anomalias['time'].values
                    alertas_df['fecha_deteccion'] = fecha_actual_completa

                    query_exist = "SELECT identificador_registro FROM ml_alertas_globales WHERE origen_datos = 'Migraciones'"
                    try:
                        df_exist = pd.read_sql_query(query_exist, engine)
                        existentes = df_exist['identificador_registro'].tolist()
                        alertas_nuevas = alertas_df[~alertas_df['identificador_registro'].isin(existentes)]
                    except Exception:
                        alertas_nuevas = alertas_df

                    if not alertas_nuevas.empty:
                        alertas_nuevas.to_sql('ml_alertas_globales', engine, if_exists='append', index=False)
                        print(f"   💾 {len(alertas_nuevas)} micro-alertas de agentes registradas.")

            # 🚀 LLAMADO AL ANÁLISIS MACRO DE SERIES TEMPORALES
            analizar_tendencia_horaria(engine, fecha_solo_dia, fecha_actual_completa)

        except Exception as e:
            print(f"   ❌ Error en análisis horario de Migraciones: {e}")

    # ==========================================================
    # 🧠 ANÁLISIS 2: CIERRE DE JORNADA (AUTOMATIZADO ÚLTIMO DÍA)
    # ==========================================================
    elif modo == 'cierre':
        print("\n🧠 [MIGRACIONES - DEEP INSIGHTS] Ejecutando análisis de cierre para el último día consolidado...")
        try:
            # 1. Identificar dinámicamente cuál fue el último día que entró al histórico
            query_max_date = "SELECT MAX(date) as ultima_fecha FROM hist_base_llamadas_migraciones WHERE date IS NOT NULL AND date != ''"
            df_max = pd.read_sql_query(query_max_date, engine)
            ultima_fecha = df_max['ultima_fecha'].iloc[0]

            if not ultima_fecha:
                print("   ⚠️ No se encontraron fechas válidas en el histórico.")
                return

            print(f"   📅 Procesando el consolidado de Migraciones del día: {ultima_fecha}")

            # 2. Extraer SOLO la data de ese último día
            query_hist = f"""
                SELECT call_id, agent, talk_time, disposition, date, time
                FROM hist_base_llamadas_migraciones
                WHERE agent IS NOT NULL AND agent != '[None]' AND date = '{ultima_fecha}'
            """
            df_hist = pd.read_sql_query(query_hist, engine)

            if len(df_hist) < 50:
                print("   ⚠️ No hay suficiente volumen de llamadas en este día para ejecutar K-Means.")
                return

            df_hist['segundos_hablados'] = pd.to_timedelta(df_hist['talk_time'], errors='coerce').dt.total_seconds().fillna(0)
            df_hist['es_venta'] = df_hist['disposition'].str.contains('Venta Facturada', case=False, na=False).astype(int)

            agentes_kpi = df_hist.groupby('agent').agg(
                total_llamadas=('call_id', 'count'),
                tmo_promedio=('segundos_hablados', 'mean'),
                total_ventas=('es_venta', 'sum')
            ).reset_index()

            agentes_kpi['efectividad'] = (agentes_kpi['total_ventas'] / agentes_kpi['total_llamadas']) * 100
            agentes_filtrados = agentes_kpi[agentes_kpi['total_llamadas'] > 5].copy()

            if len(agentes_filtrados) >= 3:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(agentes_filtrados[['efectividad', 'tmo_promedio']])

                kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
                agentes_filtrados['cluster_id'] = kmeans.fit_predict(X_scaled)

                cluster_medias = agentes_filtrados.groupby('cluster_id')['efectividad'].mean().sort_values()

                nombres_clusters = {
                    cluster_medias.index[0]: 'Área de Oportunidad (Bajo Cierre)',
                    cluster_medias.index[1]: 'Estándar (Conversadores)',
                    cluster_medias.index[2]: 'Francotiradores (Alta Efectividad)'
                }
                agentes_filtrados['cluster_nombre'] = agentes_filtrados['cluster_id'].map(nombres_clusters)

                insights_df = pd.DataFrame()
                insights_df['fecha_analisis'] = [ultima_fecha] * len(agentes_filtrados)
                insights_df['tipo_insight'] = ['Perfilamiento K-Means'] * len(agentes_filtrados)
                insights_df['agente'] = agentes_filtrados['agent'].values
                insights_df['cluster_nombre'] = agentes_filtrados['cluster_nombre'].values
                insights_df['metrica_principal'] = round(agentes_filtrados['efectividad'], 2).values
                insights_df['metrica_secundaria'] = round(agentes_filtrados['tmo_promedio'], 2).values
                insights_df['fecha_ejecucion'] = fecha_actual_completa

                # Evitar duplicados si el script se corre dos veces el mismo día
                try:
                    with engine.begin() as conn:
                        conn.execute(f"DELETE FROM ml_insights_migraciones WHERE fecha_analisis = '{ultima_fecha}'")
                except Exception:
                    pass

                insights_df.to_sql('ml_insights_migraciones', engine, if_exists='append', index=False)
                print(f"   ✅ Se clasificaron {len(insights_df)} agentes de Migraciones para el día {ultima_fecha}.")
            else:
                print(f"   ⚠️ Agentes insuficientes para K-Means en el día {ultima_fecha}.")

        except Exception as e:
            print(f"   ❌ Error en análisis de cierre Migraciones: {e}")