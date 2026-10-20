import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

def analizar_cddiario(engine, modo, tz_colombia):
    """Módulo de IA para CD Diario (Chats y Encuestas)"""
    fecha_actual_completa = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")
    # Fijamos la fecha de análisis al 26-06-2025 ya que es el único día en el histórico
    fecha_analisis_fija = '2025-06-26'

    # ==========================================================
    # ⏱️ ANÁLISIS 1: TIEMPO REAL (HORA A HORA) - RADAR
    # ==========================================================
    if modo == 'horario':
        print("\n🔍 [CD DIARIO - LIVE] Evaluando tiempos de atención en tiempo real...")
        
        try:
            query_chats = """
                SELECT 
                    id, 
                    "id_conversación" as id_conversacion, 
                    fecha_inicio,
                    agente, 
                    "cola_de_atención" as cola_de_atencion, 
                    tiempo_conversacion 
                FROM base_chat_cddiario 
                WHERE tiempo_conversacion IS NOT NULL
            """
            df_chats = pd.read_sql_query(query_chats, engine)

            if len(df_chats) < 5:
                print("   ⚠️ Datos insuficientes en CD Diario en esta hora.")
                return

            df_chats['fecha_dt'] = pd.to_datetime(df_chats['fecha_inicio'], errors='coerce')
            df_chats['date'] = df_chats['fecha_dt'].dt.strftime('%Y-%m-%d')
            df_chats['time'] = df_chats['fecha_dt'].dt.strftime('%H:%M:%S')

            # Convertir formato de tiempo de Cari AI a segundos
            df_chats['segundos_hablados'] = pd.to_timedelta(df_chats['tiempo_conversacion'], errors='coerce').dt.total_seconds()
            df_chats = df_chats.dropna(subset=['segundos_hablados', 'agente'])

            # Detección de Anomalías Intradía
            modelo = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
            df_chats['prediccion_ia'] = modelo.fit_predict(df_chats[['segundos_hablados']])
            
            anomalias = df_chats[df_chats['prediccion_ia'] == -1].copy()

            if not anomalias.empty:
                print(f"   🚨 ¡Se detectaron {len(anomalias)} chats anómalos en CD Diario!")
                
                alertas_df = pd.DataFrame()
                alertas_df['origen_datos'] = ['CD Diario'] * len(anomalias)
                alertas_df['tipo_alerta'] = ['Anomalía TMO Intradía'] * len(anomalias)
                alertas_df['severidad'] = ['MEDIA'] * len(anomalias)
                
                # 🔧 CORRECCIÓN PANDAS: Inyección de la fecha y hora reales extraídas del registro con .values
                alertas_df['call_date'] = anomalias['date'].values
                alertas_df['call_time'] = anomalias['time'].values
                
                descripciones = []
                for _, row in anomalias.iterrows():
                    cola = row['cola_de_atencion'] if pd.notna(row['cola_de_atencion']) else 'Desconocida'
                    descripciones.append(f"Agente {row['agente']} en la cola '{cola}' registró {row['segundos_hablados']}s, desviándose del promedio.")
                alertas_df['descripcion'] = descripciones
                
                # 🔧 CORRECCIÓN PANDAS: Evitar desajuste de índices en el ID con .values
                alertas_df['identificador_registro'] = anomalias['id_conversacion'].astype(str).values
                alertas_df['fecha_deteccion'] = fecha_actual_completa

                query_exist = "SELECT identificador_registro FROM ml_alertas_globales WHERE origen_datos = 'CD Diario'"
                try:
                    df_exist = pd.read_sql_query(query_exist, engine)
                    alertas_nuevas = alertas_df[~alertas_df['identificador_registro'].isin(df_exist['identificador_registro'].tolist())]
                except Exception:
                    alertas_nuevas = alertas_df

                if not alertas_nuevas.empty:
                    alertas_nuevas.to_sql('ml_alertas_globales', engine, if_exists='append', index=False)
                    print(f"   💾 {len(alertas_nuevas)} alertas de CD Diario disparadas.")
                else:
                    print("   ℹ️ Anomalías de CD Diario ya reportadas.")
            else:
                print("   ✅ Operación CD Diario fluyendo con normalidad.")

        except Exception as e:
            print(f"   ❌ Error en análisis horario CD Diario: {e}")

    # ==========================================================
    # 🧠 ANÁLISIS 2: CIERRE DE JORNADA (HISTÓRICO Y LÍDERES)
    # ==========================================================
    elif modo == 'cierre':
        print("\n🧠 [CD DIARIO - DEEP INSIGHTS] Ejecutando clustering con foco en Supervisores...")
        
        try:
            query_hist_chats = """
                SELECT 
                    "id_conversación" as id_conversacion, 
                    agente, 
                    tiempo_conversacion 
                FROM hist_base_chat_cddiario 
                WHERE agente IS NOT NULL AND agente != '[None]'
            """
            
            query_hist_nps = 'SELECT * FROM hist_base_encuestas_cddiario'
            query_dim = "SELECT asesor, supervisor FROM dim_agentes" 
            
            df_chats = pd.read_sql_query(query_hist_chats, engine)
            df_nps = pd.read_sql_query(query_hist_nps, engine)
            df_dim = pd.read_sql_query(query_dim, engine)

            if len(df_chats) < 10:
                print("   ⚠️ No hay suficiente histórico en CD Diario para ejecutar K-Means.")
                return

            df_chats['tmo_segundos'] = pd.to_timedelta(df_chats['tiempo_conversacion'], errors='coerce').dt.total_seconds().fillna(0)
            
            if 'id_de_conversación' in df_nps.columns:
                df_nps.rename(columns={'id_de_conversación': 'id_conversacion'}, inplace=True)
            elif 'id_conversación' in df_nps.columns:
                df_nps.rename(columns={'id_conversación': 'id_conversacion'}, inplace=True)

            columna_nota = None
            for col in df_nps.columns:
                if 'satisfacci' in col.lower() or 'nota' in col.lower():
                    if 'bot' not in col.lower():
                        columna_nota = col
                        break

            if columna_nota and 'id_conversacion' in df_nps.columns:
                df_nps['nota_numerica'] = pd.to_numeric(df_nps[columna_nota], errors='coerce')
                df_nps['es_promotor'] = df_nps['nota_numerica'].apply(lambda x: 1 if x >= 4 else 0)
                df_nps['es_encuesta'] = 1
                
                df_master = pd.merge(df_chats, df_nps[['id_conversacion', 'es_promotor', 'es_encuesta']], on='id_conversacion', how='left')
                df_master['es_promotor'] = df_master['es_promotor'].fillna(0)
                df_master['es_encuesta'] = df_master['es_encuesta'].fillna(0)
            else:
                print("   ⚠️ No se encontró la columna de notas NPS/Satisfacción. Evaluando solo por TMO.")
                df_master = df_chats
                df_master['es_promotor'] = 0
                df_master['es_encuesta'] = 0

            df_master['agente_norm'] = df_master['agente'].astype(str).str.lower().str.strip()
            df_dim['asesor_norm'] = df_dim['asesor'].astype(str).str.lower().str.strip()

            agentes_kpi = df_master.groupby('agente_norm').agg(
                nombre_original=('agente', 'first'),
                total_chats=('id_conversacion', 'count'),
                tmo_promedio=('tmo_segundos', 'mean'),
                total_encuestas=('es_encuesta', 'sum'),
                total_promotores=('es_promotor', 'sum')
            ).reset_index()

            agentes_kpi = agentes_kpi[agentes_kpi['total_chats'] > 5]

            agentes_kpi['porcentaje_promotores'] = np.where(
                agentes_kpi['total_encuestas'] > 0, 
                (agentes_kpi['total_promotores'] / agentes_kpi['total_encuestas']) * 100, 
                0
            )

            agentes_kpi = pd.merge(agentes_kpi, df_dim[['asesor_norm', 'supervisor']], left_on='agente_norm', right_on='asesor_norm', how='left')
            agentes_kpi['supervisor'] = agentes_kpi['supervisor'].fillna('Sin Supervisor')

            if len(agentes_kpi) >= 3:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(agentes_kpi[['porcentaje_promotores', 'tmo_promedio']])
                
                kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
                agentes_kpi['cluster_id'] = kmeans.fit_predict(X_scaled)
                
                cluster_medias = agentes_kpi.groupby('cluster_id')['porcentaje_promotores'].mean().sort_values()
                nombres_clusters = {
                    cluster_medias.index[0]: 'Alerta Operativa (Baja Calidad)',
                    cluster_medias.index[1]: 'Rendimiento Estándar',
                    cluster_medias.index[2]: 'Excelencia Operativa'
                }
                agentes_kpi['cluster_nombre'] = agentes_kpi['cluster_id'].map(nombres_clusters)

                insights_df = pd.DataFrame()
                insights_df['fecha_analisis'] = [fecha_analisis_fija] * len(agentes_kpi)
                insights_df['tipo_insight'] = ['K-Means (Agentes por Líder)'] * len(agentes_kpi)
                
                # 🔧 CORRECCIÓN PANDAS: Asegurar también con .values que la tabla de insights no inserte NaNs
                insights_df['agente'] = agentes_kpi['nombre_original'].values
                insights_df['lider'] = agentes_kpi['supervisor'].values
                insights_df['cluster_nombre'] = agentes_kpi['cluster_nombre'].values
                insights_df['metrica_principal'] = round(agentes_kpi['porcentaje_promotores'], 2).values
                insights_df['metrica_secundaria'] = round(agentes_kpi['tmo_promedio'], 2).values
                
                descripciones = []
                for _, row in agentes_kpi.iterrows():
                    descripciones.append(f"Equipo {row['supervisor']}: Agente en '{row['cluster_nombre']}' con {round(row['porcentaje_promotores'], 1)}% NPS.")
                insights_df['descripcion_insight'] = descripciones
                
                insights_df['fecha_ejecucion'] = fecha_actual_completa

                try:
                    with engine.begin() as conn:
                        conn.execute(f"DELETE FROM ml_insights_cddiario WHERE fecha_analisis = '{fecha_analisis_fija}'")
                except Exception:
                    pass

                insights_df.to_sql('ml_insights_cddiario', engine, if_exists='append', index=False)
                print(f"   ✅ Se clasificaron {len(insights_df)} agentes de CD Diario, enlazados a sus Supervisores.")
                print("   💾 Resultados guardados en 'ml_insights_cddiario'.")
            else:
                print("   ⚠️ No hay suficientes agentes válidos.")

        except Exception as e:
            print(f"   ❌ Error en análisis de cierre CD Diario: {e}")