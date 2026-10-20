import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

def analizar_rrss(engine, modo, tz_colombia):
    """Módulo de Inteligencia Artificial exclusivo para Redes Sociales (100% Automatizado)"""
    fecha_actual_completa = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")

    # ==========================================================
    # ⏱️ ANÁLISIS 1: TIEMPO REAL (HORA A HORA) - RADAR
    # ==========================================================
    if modo == 'horario':
        print("\n🔍 [RRSS - LIVE] Cruzando bases crudas y buscando anomalías...")
        
        try:
            query_chats = """
                SELECT 
                    "id_conversación" as id_conversacion, 
                    fecha_inicio,
                    agente, 
                    tiempo_conversacion 
                FROM hist_chats_monetizacion_rrss 
                WHERE tiempo_conversacion IS NOT NULL
            """
            query_tip = 'SELECT "id_conversación" as id_conversacion, "ekia_código" as tipificacion FROM hist_base_tipificaciones_rrss'
            
            df_chats = pd.read_sql_query(query_chats, engine)
            df_tip = pd.read_sql_query(query_tip, engine)

            if len(df_chats) < 5:
                print("   ⚠️ Datos insuficientes en RRSS en esta hora para entrenar IA. Esperando más chats...")
                return

            df_chats['fecha_dt'] = pd.to_datetime(df_chats['fecha_inicio'], errors='coerce')
            df_chats['date'] = df_chats['fecha_dt'].dt.strftime('%Y-%m-%d')
            df_chats['time'] = df_chats['fecha_dt'].dt.strftime('%H:%M:%S')

            df_master = pd.merge(df_chats, df_tip, on='id_conversacion', how='left')

            df_master['segundos_hablados'] = pd.to_timedelta(df_master['tiempo_conversacion'], errors='coerce').dt.total_seconds()
            df_master = df_master.dropna(subset=['segundos_hablados', 'agente'])

            if df_master.empty:
                print("   ⚠️ No hay datos de tiempo válidos para analizar tras la conversión.")
                return

            modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
            df_master['prediccion_ia'] = modelo.fit_predict(df_master[['segundos_hablados']])
            
            anomalias = df_master[df_master['prediccion_ia'] == -1].copy()

            if not anomalias.empty:
                print(f"   🚨 ¡Se detectaron {len(anomalias)} chats con comportamiento anómalo!")
                
                alertas_df = pd.DataFrame()
                alertas_df['origen_datos'] = ['Redes Sociales'] * len(anomalias)
                alertas_df['tipo_alerta'] = ['Anomalía TMO en Chat (Posible Evasión)'] * len(anomalias)
                alertas_df['severidad'] = ['MEDIA'] * len(anomalias)
                alertas_df['call_date'] = anomalias['date'].values
                alertas_df['call_time'] = anomalias['time'].values
                
                descripciones = []
                for _, row in anomalias.iterrows():
                    tip = row['tipificacion'] if pd.notna(row['tipificacion']) else 'Sin Tipificar'
                    descripciones.append(f"Agente {row['agente']} registró un tiempo de {row['segundos_hablados']}s tipificando '{tip}'.")
                alertas_df['descripcion'] = descripciones
                
                alertas_df['identificador_registro'] = anomalias['id_conversacion'].astype(str).values
                alertas_df['fecha_deteccion'] = fecha_actual_completa

                query_exist = "SELECT identificador_registro FROM ml_alertas_globales WHERE origen_datos = 'Redes Sociales'"
                try:
                    df_exist = pd.read_sql_query(query_exist, engine)
                    existentes = df_exist['identificador_registro'].tolist()
                    alertas_nuevas = alertas_df[~alertas_df['identificador_registro'].isin(existentes)]
                except Exception:
                    alertas_nuevas = alertas_df

                if not alertas_nuevas.empty:
                    alertas_nuevas.to_sql('ml_alertas_globales', engine, if_exists='append', index=False)
                    print(f"   💾 {len(alertas_nuevas)} alertas de RRSS disparadas al Radar.")
                else:
                    print("   ℹ️ Las anomalías de RRSS ya estaban reportadas.")
            else:
                print("   ✅ Operación de RRSS fluyendo con normalidad.")

        except Exception as e:
            print(f"   ❌ Error en análisis horario de RRSS: {e}")

    # ==========================================================
    # 🧠 ANÁLISIS 2: CIERRE DE JORNADA (AUTOMATIZADO ÚLTIMO DÍA)
    # ==========================================================
    elif modo == 'cierre':
        print("\n🧠 [RRSS - DEEP INSIGHTS] Ejecutando análisis de cierre para el último día consolidado...")
        try:
            # 1. Identificar dinámicamente cuál fue el último día ingresado al histórico
            query_max_date = """
                SELECT MAX(SUBSTRING(fecha_inicio FROM 1 FOR 10)) as ultima_fecha 
                FROM hist_chats_monetizacion_rrss 
                WHERE fecha_inicio IS NOT NULL AND fecha_inicio != ''
            """
            df_max = pd.read_sql_query(query_max_date, engine)
            ultima_fecha = df_max['ultima_fecha'].iloc[0]

            if not ultima_fecha:
                print("   ⚠️ No se encontraron fechas válidas en el histórico de RRSS.")
                return

            print(f"   📅 Procesando el consolidado de RRSS del día: {ultima_fecha}")

            # 2. Extraer SOLO la data de ese último día
            query_hist_chats = f"""
                SELECT "id_conversación" as id_conversacion, agente, tiempo_conversacion, fecha_inicio 
                FROM hist_chats_monetizacion_rrss 
                WHERE agente IS NOT NULL 
                  AND agente != '[None]' 
                  AND SUBSTRING(fecha_inicio FROM 1 FOR 10) = '{ultima_fecha}'
            """
            query_hist_nps = 'SELECT * FROM hist_base_nps_rrss'
            query_dim = "SELECT asesor, wave FROM dim_agentes"

            df_chats = pd.read_sql_query(query_hist_chats, engine)
            df_nps = pd.read_sql_query(query_hist_nps, engine)
            df_dim = pd.read_sql_query(query_dim, engine)

            if len(df_chats) < 5:
                print(f"   ⚠️ No hay suficiente volumen de chats ({len(df_chats)}) en el día {ultima_fecha} para ejecutar K-Means.")
                return

            # Conversión de tiempos
            df_chats['tmo_segundos'] = pd.to_timedelta(df_chats['tiempo_conversacion'], errors='coerce').dt.total_seconds().fillna(0)

            # Estandarización de cruce con NPS
            id_nps_col = 'id_de_conversación' if 'id_de_conversación' in df_nps.columns else 'id_conversación'
            if id_nps_col in df_nps.columns:
                df_nps.rename(columns={id_nps_col: 'id_conversacion'}, inplace=True)

            columna_nota = 'recomendación' if 'recomendación' in df_nps.columns else None

            if columna_nota and 'id_conversacion' in df_nps.columns:
                df_nps['nota_numerica'] = pd.to_numeric(df_nps[columna_nota], errors='coerce')
                df_nps['es_promotor'] = df_nps['nota_numerica'].apply(lambda x: 1 if x >= 9 else 0)
                df_nps['es_encuesta'] = 1

                df_master = pd.merge(df_chats, df_nps[['id_conversacion', 'es_promotor', 'es_encuesta']], on='id_conversacion', how='left')
                df_master['es_promotor'] = df_master['es_promotor'].fillna(0)
                df_master['es_encuesta'] = df_master['es_encuesta'].fillna(0)
            else:
                df_master = df_chats
                df_master['es_promotor'] = 0
                df_master['es_encuesta'] = 0

            df_master['agente_norm'] = df_master['agente'].astype(str).str.lower().str.strip()
            df_dim['asesor_norm'] = df_dim['asesor'].astype(str).str.lower().str.strip()

            # Agrupación por asesor
            agentes_kpi = df_master.groupby('agente_norm').agg(
                nombre_original=('agente', 'first'),
                total_chats=('id_conversacion', 'count'),
                tmo_promedio=('tmo_segundos', 'mean'),
                total_encuestas=('es_encuesta', 'sum'),
                total_promotores=('es_promotor', 'sum')
            ).reset_index()

            agentes_filtrados = agentes_kpi[agentes_kpi['total_chats'] > 3].copy()

            agentes_filtrados['porcentaje_promotores'] = np.where(
                agentes_filtrados['total_encuestas'] > 0,
                (agentes_filtrados['total_promotores'] / agentes_filtrados['total_encuestas']) * 100,
                0
            )

            agentes_filtrados = pd.merge(agentes_filtrados, df_dim[['asesor_norm', 'wave']], left_on='agente_norm', right_on='asesor_norm', how='left')
            agentes_filtrados['wave'] = agentes_filtrados['wave'].fillna('Desconocida')

            # Entrenamiento y asignación de K-Means
            if len(agentes_filtrados) >= 3:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(agentes_filtrados[['porcentaje_promotores', 'tmo_promedio']])

                kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
                agentes_filtrados['cluster_id'] = kmeans.fit_predict(X_scaled)

                cluster_medias = agentes_filtrados.groupby('cluster_id')['porcentaje_promotores'].mean().sort_values()

                nombres_clusters = {
                    cluster_medias.index[0]: 'Riesgo de Calidad (Bajo NPS)',
                    cluster_medias.index[1]: 'Estándar (Calidad Media)',
                    cluster_medias.index[2]: 'Resolutivos Estrella (Alto NPS)'
                }
                agentes_filtrados['cluster_nombre'] = agentes_filtrados['cluster_id'].map(nombres_clusters)

                # Construcción del DataFrame para base de datos
                insights_df = pd.DataFrame()
                insights_df['fecha_analisis'] = [ultima_fecha] * len(agentes_filtrados)
                insights_df['tipo_insight'] = ['Perfilamiento K-Means (Calidad vs TMO)'] * len(agentes_filtrados)
                insights_df['agente'] = agentes_filtrados['nombre_original'].values
                insights_df['wave'] = agentes_filtrados['wave'].values
                insights_df['cluster_nombre'] = agentes_filtrados['cluster_nombre'].values
                insights_df['metrica_principal'] = round(agentes_filtrados['porcentaje_promotores'], 2).values
                insights_df['metrica_secundaria'] = round(agentes_filtrados['tmo_promedio'], 2).values

                descripciones = []
                for _, row in agentes_filtrados.iterrows():
                    descripciones.append(
                        f"Agente de {row['wave']} agrupado en '{row['cluster_nombre']}' con {round(row['porcentaje_promotores'], 2)}% de Promotores y TMO de {round(row['tmo_promedio'], 1)} seg."
                    )
                insights_df['descripcion_insight'] = descripciones
                insights_df['fecha_ejecucion'] = fecha_actual_completa

                # Evitar duplicados si se vuelve a correr el proceso en la misma fecha
                try:
                    with engine.begin() as conn:
                        conn.execute(f"DELETE FROM ml_insights_rrss WHERE fecha_analisis = '{ultima_fecha}'")
                except Exception:
                    pass

                insights_df.to_sql('ml_insights_rrss', engine, if_exists='append', index=False)
                print(f"   ✅ Se clasificaron {len(insights_df)} agentes de RRSS para el día {ultima_fecha}.")
            else:
                print(f"   ⚠️ Agentes insuficientes para K-Means en el día {ultima_fecha}.")

        except Exception as e:
            print(f"   ❌ Error en análisis de cierre RRSS: {e}")