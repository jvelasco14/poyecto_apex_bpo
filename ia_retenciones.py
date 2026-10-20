import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import datetime
from sqlalchemy import text
import warnings

warnings.filterwarnings('ignore')

def parse_excel_time(val):
    try:
        if pd.isna(val) or val == '': return np.nan
        val_str = str(val).strip()
        if ':' in val_str:
            parts = val_str.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else: return float(val) * 86400
    except: return 0

def ejecutar_modelos_predictivos_retenciones(engine, fecha_simulada, hora_simulada, fecha_actual_completa):
    try:
        hora_actual = int(hora_simulada)
        # Apagado total del script después de las 15:00
        if hora_actual < 8 or hora_actual > 15: return

        hora_proxima = hora_actual + 1
        hora_proxima_str = str(hora_proxima).zfill(2)
        hora_simulada_str = str(hora_simulada).zfill(2)
        
        alertas_predictivas = []
        
        with engine.connect() as conn:
            # =======================================================
            # MODELO 1: FORECASTING DE CIERRE DIARIO (SIN META FIJA)
            # =======================================================
            # Solo proyectamos el cierre diario ANTES de las 15:00
            if hora_actual < 15:
                # ARQUITECTURA LAMBDA: Se extrae de la tabla viva
                q_reten_hoy = f"SELECT COUNT(*) as reten_hoy FROM base_rete_out WHERE date = '{fecha_simulada}' AND SUBSTRING(CAST(time AS TEXT), 1, 2) <= '{hora_simulada_str}' AND LOWER(CAST(disposition AS TEXT)) LIKE '%retenci%'"
                
                # BLINDAJE: Verificación de DataFrame vacío
                df_reten_hoy = pd.read_sql_query(text(q_reten_hoy), conn)
                reten_hoy = df_reten_hoy['reten_hoy'].iloc[0] if not df_reten_hoy.empty and pd.notna(df_reten_hoy['reten_hoy'].iloc[0]) else 0
                
                horas_transcurridas = max(1, hora_actual - 8 + 1)
                horas_restantes = max(1, 15 - hora_actual - 1)
                
                if horas_transcurridas > 0 and horas_restantes > 0:
                    velocidad_actual = reten_hoy / horas_transcurridas
                    cierre_proyectado = reten_hoy + (velocidad_actual * horas_restantes)
                    
                    alertas_predictivas.append({
                        'origen_datos': 'Retenciones Outbound',
                        'tipo_alerta': '[PREDICTIVO] Proyección de Cierre Diario',
                        'severidad': 'INFO',
                        'descripcion': f"A una velocidad operativa de {velocidad_actual:.1f} retenciones/hora, proyectamos que el equipo cerrará la jornada a las 15:00 hrs con un total estimado de {int(cierre_proyectado)} retenciones.",
                        'identificador_registro': f"PRED-RETE-FORECAST-{fecha_simulada}-{hora_simulada_str}",
                        'call_date': fecha_simulada,
                        'call_time': f"{hora_simulada_str}:00:00",
                        'fecha_deteccion': fecha_actual_completa
                    })

            # =======================================================
            # MODELO 2: ANÁLISIS DE FATIGA DE BASE (COLD-START)
            # =======================================================
            q_eficiencia_hoy = f"""
                SELECT COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT agent), 0) as retenciones_por_agente
                FROM base_rete_out 
                WHERE date = '{fecha_simulada}' 
                AND SUBSTRING(CAST(time AS TEXT), 1, 2) = '{hora_simulada_str}'
                AND LOWER(CAST(disposition AS TEXT)) LIKE '%retenci%'
                AND agent IS NOT NULL AND agent != '' AND agent != '[None]'
            """
            df_eficiencia_hoy = pd.read_sql_query(text(q_eficiencia_hoy), conn)
            eficiencia_hoy = df_eficiencia_hoy['retenciones_por_agente'].iloc[0] if not df_eficiencia_hoy.empty and pd.notna(df_eficiencia_hoy['retenciones_por_agente'].iloc[0]) else 0.0

            q_eficiencia_acumulada = f"""
                SELECT COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT agent), 0) as retenciones_por_agente_hist
                FROM base_rete_out 
                WHERE date = '{fecha_simulada}' 
                AND SUBSTRING(CAST(time AS TEXT), 1, 2) < '{hora_simulada_str}'
                AND LOWER(CAST(disposition AS TEXT)) LIKE '%retenci%'
                AND agent IS NOT NULL AND agent != '' AND agent != '[None]'
            """
            df_eficiencia_acumulada = pd.read_sql_query(text(q_eficiencia_acumulada), conn)
            eficiencia_acumulada = df_eficiencia_acumulada['retenciones_por_agente_hist'].iloc[0] if not df_eficiencia_acumulada.empty and pd.notna(df_eficiencia_acumulada['retenciones_por_agente_hist'].iloc[0]) else 1.0 
            if eficiencia_acumulada == 0: eficiencia_acumulada = 1.0

            rendimiento = eficiencia_hoy / eficiencia_acumulada
            
            if rendimiento < 0.70 and eficiencia_hoy > 0: 
                alertas_predictivas.append({
                    'origen_datos': 'Retenciones Outbound',
                    'tipo_alerta': '[ANALÍTICA] Desaceleración Intradía',
                    'severidad': 'MEDIA',
                    'descripcion': f"Fatiga de base detectada. En la franja de las {hora_simulada_str}:00, el ritmo cayó a {eficiencia_hoy:.1f} retenciones por asesor, un {(1-rendimiento)*100:.1f}% por debajo del promedio que traía la campaña en la mañana ({eficiencia_acumulada:.1f}).",
                    'identificador_registro': f"ANALIT-RETE-PROD-{fecha_simulada}-{hora_simulada_str}",
                    'call_date': fecha_simulada, 'call_time': f"{hora_simulada_str}:00:00", 'fecha_deteccion': fecha_actual_completa
                })
            elif eficiencia_hoy > 0:
                alertas_predictivas.append({
                    'origen_datos': 'Retenciones Outbound',
                    'tipo_alerta': '[ANALÍTICA] Ritmo Operativo Estable',
                    'severidad': 'INFO',
                    'descripcion': f"El equipo mantiene la tracción. En la franja de las {hora_simulada_str}:00, se lograron {eficiencia_hoy:.1f} retenciones por asesor, sosteniendo el promedio del día ({eficiencia_acumulada:.1f}).",
                    'identificador_registro': f"ANALIT-RETE-PROD-{fecha_simulada}-{hora_simulada_str}",
                    'call_date': fecha_simulada, 'call_time': f"{hora_simulada_str}:00:00", 'fecha_deteccion': fecha_actual_completa
                })
            elif hora_actual == 15 and eficiencia_hoy == 0:
                 alertas_predictivas.append({
                    'origen_datos': 'Retenciones Outbound',
                    'tipo_alerta': '[ANALÍTICA] Cierre de Operaciones',
                    'severidad': 'INFO',
                    'descripcion': f"La campaña ha finalizado el barrido de base programado para el día de hoy.",
                    'identificador_registro': f"ANALIT-RETE-CIERRE-{fecha_simulada}-{hora_simulada_str}",
                    'call_date': fecha_simulada, 'call_time': f"{hora_simulada_str}:00:00", 'fecha_deteccion': fecha_actual_completa
                })

            if hora_actual < 15:
                inercia_desaceleracion = min(max(rendimiento, 0.5), 1.2)
                proyeccion_prox_hora = eficiencia_hoy * inercia_desaceleracion

                if proyeccion_prox_hora < (eficiencia_acumulada * 0.70):
                    alertas_predictivas.append({
                        'origen_datos': 'Retenciones Outbound',
                        'tipo_alerta': '[PREDICTIVO] Riesgo de Caída en Retenciones',
                        'severidad': 'MEDIA',
                        'descripcion': f"Debido al desgaste del barrido actual, se proyecta una caída a solo {proyeccion_prox_hora:.1f} retenciones por agente entre las {hora_proxima_str}:00 y {int(hora_proxima_str)+1}:00 hrs. Se recomienda rotar la base de datos.",
                        'identificador_registro': f"PRED-RETE-EFIC-{fecha_simulada}-{hora_proxima_str}",
                        'call_date': fecha_simulada, 'call_time': f"{hora_simulada_str}:00:00", 'fecha_deteccion': fecha_actual_completa
                    })
                else:
                    alertas_predictivas.append({
                        'origen_datos': 'Retenciones Outbound',
                        'tipo_alerta': '[PREDICTIVO] Proyección de Barrido Óptimo',
                        'severidad': 'INFO',
                        'descripcion': f"La contactabilidad se mantiene estable. Proyectamos que cada agente sostendrá un ritmo de {proyeccion_prox_hora:.1f} retenciones entre las {hora_proxima_str}:00 y {int(hora_proxima_str)+1}:00 hrs.",
                        'identificador_registro': f"PRED-RETE-EFIC-{fecha_simulada}-{hora_proxima_str}",
                        'call_date': fecha_simulada, 'call_time': f"{hora_simulada_str}:00:00", 'fecha_deteccion': fecha_actual_completa
                    })

        if alertas_predictivas:
            df_alertas_pred = pd.DataFrame(alertas_predictivas)
            df_alertas_pred['asesor_id'] = 'N/A (Campaña)'
            df_alertas_pred = df_alertas_pred[['origen_datos', 'tipo_alerta', 'severidad', 'descripcion', 'identificador_registro', 'asesor_id', 'call_date', 'call_time', 'fecha_deteccion']]
            
            try:
                with engine.connect() as conn:
                    df_exist = pd.read_sql_query(text("SELECT identificador_registro FROM ml_alertas_globales WHERE origen_datos = 'Retenciones Outbound'"), conn)
                alertas_nuevas = df_alertas_pred[~df_alertas_pred['identificador_registro'].isin(df_exist['identificador_registro'].tolist())]
            except:
                alertas_nuevas = df_alertas_pred

            if not alertas_nuevas.empty:
                try:
                    with engine.connect() as conn:
                        df_global_actual = pd.read_sql_query(text("SELECT * FROM ml_alertas_globales"), conn)
                    df_actualizado = pd.concat([df_global_actual, alertas_nuevas], ignore_index=True)
                    df_actualizado.sort_values(by=['call_date', 'call_time'], ascending=[False, False], inplace=True)
                    with engine.begin() as conn:
                        df_actualizado.to_sql('ml_alertas_globales', conn, if_exists='replace', index=False)
                    print(f"   🔮 [PREDICTIVO RETENCIONES] {len(alertas_nuevas)} alertas inyectadas a las {hora_simulada_str}:00.")
                except Exception:
                    with engine.begin() as conn:
                        alertas_nuevas.to_sql('ml_alertas_globales', conn, if_exists='append', index=False)

    except Exception as e:
        print(f"   ❌ Error predictivo Retenciones: {e}")

def analizar_retenciones(engine, modo, tz_colombia):
    fecha_actual_completa = datetime.now(tz_colombia).strftime("%Y-%m-%d %H:%M:%S")

    if modo == 'horario':
        print("\n🔍 [RETENCIONES - LIVE] Ejecutando análisis en tiempo real (Arquitectura Lambda)...")
        
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT MAX(date), MAX(SUBSTRING(CAST(time AS TEXT), 1, 2)) FROM base_rete_out WHERE talk_time IS NOT NULL")).fetchone()
                # BLINDAJE: Si la tabla viva está vacía, no procedemos
                if res[0] is None:
                    print("   ⚠️ [RETENCIONES] No hay datos en la tabla viva para analizar.")
                    return
                fecha_sim = str(res[0])
                hora_sim = str(res[1]).zfill(2)
        except Exception as e:
            print(f"   ❌ Error al obtener fecha/hora de la base viva: {e}")
            return
        
        try:
            with engine.connect() as conn:
                resp_agentes = pd.read_sql_query(text("SELECT id, cedula, five9, asesor FROM dim_agentes"), conn)
            mapa_agentes = {}
            for _, ag in resp_agentes.iterrows():
                nom = str(ag.get("asesor", "")).strip()
                ced_real = str(ag.get("cedula", "")).strip().replace('.0', '')
                if nom and nom.lower() not in ["none", "null", ""]:
                    ced, id_int, f9 = str(ag.get("cedula", "")).strip().replace('.0', ''), str(ag.get("id", "")).strip().replace('.0', ''), str(ag.get("five9", "")).strip().replace('.0', '')
                    datos_ag = {"nombre": nom, "cedula": ced_real}
                    if ced and ced != 'None': mapa_agentes[ced] = datos_ag
                    if id_int and id_int != 'None': mapa_agentes[id_int] = datos_ag
                    if f9 and f9 != 'None': mapa_agentes[f9] = datos_ag
        except:
            mapa_agentes = {}

        print(f"   ⌚ Analizando franja de las {hora_sim}:00 hrs del {fecha_sim}...")
            
        try:
            q_live = f"""
                SELECT id as db_id, date, time, agent as agente, talk_time, disposition as tipificacion 
                FROM base_rete_out 
                WHERE date = '{fecha_sim}' 
                AND SUBSTRING(CAST(time AS TEXT), 1, 2) = '{hora_sim}'
                AND talk_time IS NOT NULL
            """
            with engine.connect() as conn:
                df_live = pd.read_sql_query(text(q_live), conn)
            
            # BLINDAJE: Validación estricta de cantidad de datos
            if not df_live.empty and len(df_live) >= 5:
                df_live['segundos_hablados'] = df_live['talk_time'].apply(parse_excel_time)
                df_live = df_live.dropna(subset=['segundos_hablados', 'agente'])
                df_live = df_live[df_live['segundos_hablados'] > 2]
                
                if len(df_live) > 1:
                    df_live['prediccion_ia'] = IsolationForest(n_estimators=100, contamination=0.03, random_state=42).fit_predict(df_live[['segundos_hablados']])
                    anomalias = df_live[df_live['prediccion_ia'] == -1].copy()

                    if not anomalias.empty:
                        alertas_df = pd.DataFrame()
                        alertas_df['origen_datos'] = ['Retenciones Outbound'] * len(anomalias)
                        alertas_df['tipo_alerta'] = ['Anomalía TMO vs Tipificación'] * len(anomalias)
                        alertas_df['severidad'] = ['MEDIA'] * len(anomalias)
                        
                        descripciones, asesor_ids = [], []
                        for _, row in anomalias.iterrows():
                            segundos = row['segundos_hablados']
                            tip = row['tipificacion'] if pd.notna(row['tipificacion']) else 'Desconocida'
                            as_id_raw = str(row['agente']).strip().replace('.0', '')
                            info_ag = mapa_agentes.get(as_id_raw, {"nombre": "Sin Asignación", "cedula": as_id_raw})
                            
                            dur_str = f"{round(segundos / 60, 1)} min" if segundos > 60 else f"{round(segundos, 1)} seg"
                            descripciones.append(f"Agente {info_ag['nombre']} (CC: {info_ag['cedula']}) registró llamada atípica de {dur_str} tipificando '{tip}'.")
                            asesor_ids.append(info_ag['cedula'])
                            
                        alertas_df['descripcion'] = descripciones
                        alertas_df['identificador_registro'] = anomalias['db_id'].astype(str).values
                        alertas_df['asesor_id'] = asesor_ids 
                        alertas_df['call_date'] = anomalias['date'].values
                        alertas_df['call_time'] = anomalias['time'].values
                        alertas_df['fecha_deteccion'] = fecha_actual_completa

                        alertas_df = alertas_df[['origen_datos', 'tipo_alerta', 'severidad', 'descripcion', 'identificador_registro', 'asesor_id', 'call_date', 'call_time', 'fecha_deteccion']]

                        try:
                            with engine.connect() as conn:
                                df_exist = pd.read_sql_query(text("SELECT identificador_registro FROM ml_alertas_globales"), conn)
                            alertas_nuevas = alertas_df[~alertas_df['identificador_registro'].isin(df_exist['identificador_registro'].tolist())]
                        except: alertas_nuevas = alertas_df

                        if not alertas_nuevas.empty:
                            try:
                                with engine.connect() as conn:
                                    df_global_actual = pd.read_sql_query(text("SELECT * FROM ml_alertas_globales"), conn)
                                df_actualizado = pd.concat([df_global_actual, alertas_nuevas], ignore_index=True)
                                df_actualizado.sort_values(by=['call_date', 'call_time'], ascending=[False, False], inplace=True)
                                with engine.begin() as conn:
                                    df_actualizado.to_sql('ml_alertas_globales', conn, if_exists='replace', index=False)
                                print(f"   🔍 [MICRO RETENCIONES] {len(alertas_nuevas)} TMOs anómalos ordenados a las {hora_sim}:00.")
                            except Exception:
                                with engine.begin() as conn:
                                    alertas_nuevas.to_sql('ml_alertas_globales', conn, if_exists='append', index=False)
                else:
                    print("   ⚠️ Datos limpios insuficientes para ejecutar Isolation Forest en Retenciones.")
            else:
                print("   ⚠️ Volumen inferior a 5 llamadas. No se ejecutará Isolation Forest para Retenciones.")
            
            ejecutar_modelos_predictivos_retenciones(engine, fecha_sim, hora_sim, fecha_actual_completa)
            
        except Exception as e: print(f"   ❌ Error simulación Retenciones {fecha_sim} {hora_sim}:00: {e}")

    elif modo == 'cierre':
        print("\n🧠 [RETENCIONES - DEEP INSIGHTS] Ejecutando análisis de cierre histórico...")
        
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT MAX(date) FROM hist_base_rete_out")).fetchone()
                fecha_cierre = str(res[0]) if res[0] else datetime.now(tz_colombia).strftime("%Y-%m-%d")
        except:
            fecha_cierre = datetime.now(tz_colombia).strftime("%Y-%m-%d")

        try:
            q_hist = f"SELECT agent as agente, talk_time, disposition as tipificacion, date FROM hist_base_rete_out WHERE agent IS NOT NULL AND agent != '[None]' AND date = '{fecha_cierre}'"
            with engine.connect() as conn:
                df_hist = pd.read_sql_query(text(q_hist), conn)

            # BLINDAJE: Verificación de DataFrame vacío
            if df_hist.empty or len(df_hist) < 5: 
                print(f"   ⚠️ No hay datos suficientes para perfilar agentes de Retenciones el {fecha_cierre}.")
                return

            df_hist['tmo_segundos'] = df_hist['talk_time'].apply(parse_excel_time).fillna(0)
            no_efectivas = ['no answer', 'buzon', 'hangup', 'abandon', 'machine', 'muda']
            df_hist['es_efectiva'] = df_hist['tipificacion'].astype(str).str.lower().apply(lambda x: 0 if any(b in x for b in no_efectivas) else 1)
            df_hist['es_retencion'] = df_hist['tipificacion'].astype(str).str.lower().apply(lambda x: 1 if 'retenci' in x else 0)

            agentes_kpi = df_hist.groupby('agente').agg(total_llamadas=('agente', 'count'), llamadas_efectivas=('es_efectiva', 'sum'), total_retenciones=('es_retencion', 'sum'), tmo_promedio=('tmo_segundos', 'mean')).reset_index()
            agentes_kpi = agentes_kpi[agentes_kpi['llamadas_efectivas'] > 3].copy()
            if agentes_kpi.empty: return

            agentes_kpi['efectividad'] = (agentes_kpi['total_retenciones'] / agentes_kpi['llamadas_efectivas']) * 100

            # BLINDAJE: KMeans(3) requiere 3 o más agentes
            if len(agentes_kpi) >= 3:
                agentes_kpi['cluster_id'] = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(StandardScaler().fit_transform(agentes_kpi[['efectividad', 'tmo_promedio']]))
                cluster_medias = agentes_kpi.groupby('cluster_id')['efectividad'].mean().sort_values()
                nombres_clusters = {cluster_medias.index[0]: 'Área de Oportunidad (Baja Retención)', cluster_medias.index[1]: 'Estándar (Cierre Medio)', cluster_medias.index[2]: 'Top Performers (Cerradores Estrella)'}
                agentes_kpi['cluster_nombre'] = agentes_kpi['cluster_id'].map(nombres_clusters)

                insights_df = pd.DataFrame()
                insights_df['fecha_analisis'] = [fecha_cierre] * len(agentes_kpi)
                insights_df['tipo_insight'] = ['K-Means (Efectividad vs TMO)'] * len(agentes_kpi)
                insights_df['agente'] = agentes_kpi['agente'].astype(str).values
                insights_df['cluster_nombre'] = agentes_kpi['cluster_nombre'].values
                insights_df['metrica_principal'] = round(agentes_kpi['efectividad'], 2).values
                insights_df['metrica_secundaria'] = round(agentes_kpi['tmo_promedio'], 2).values
                insights_df['fecha_ejecucion'] = fecha_actual_completa
                insights_df['descripcion_insight'] = [f"Agente clasificado en '{r['cluster_nombre']}' con {round(r['efectividad'], 2)}% de retención y TMO de {round(r['tmo_promedio']/60, 1)} min." for _, r in agentes_kpi.iterrows()]

                try:
                    with engine.begin() as conn: conn.execute(text(f"DELETE FROM ml_insights_retenciones WHERE fecha_analisis = '{fecha_cierre}'"))
                except: pass
                with engine.begin() as conn:
                    insights_df.to_sql('ml_insights_retenciones', conn, if_exists='append', index=False)
                print(f"   ✅ [{fecha_cierre}] Perfilados {len(insights_df)} agentes de Retenciones.")
            else:
                print(f"   ⚠️ Menos de 3 agentes activos para ejecutar K-Means en Retenciones ({fecha_cierre}).")
        except Exception as e: print(f"   ❌ Error cierre Retenciones {fecha_cierre}: {e}")