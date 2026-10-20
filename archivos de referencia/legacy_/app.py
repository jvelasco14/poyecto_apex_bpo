import os
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Response, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from supabase import create_client, Client
from sklearn.ensemble import IsolationForest
import pandas as pd
from datetime import date, datetime
import numpy as np

# ==========================================
# 🔗 CONEXIÓN A LA BASE DE DATOS (SUPABASE)
# ==========================================
SUPABASE_URL = "https://vdvmyueufdfviztmribf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdm15dWV1ZmRmdml6dG1yaWJmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MzI2MTAsImV4cCI6MjA5NjEwODYxMH0.JHxc5WePZakQq1TzjtCYP3GpEp09tjIMRIe13eUwqSo" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 🚀 INICIALIZACIÓN DEL SERVIDOR FASTAPI
# ==========================================
app = FastAPI(title="GTR Analytics - Apex")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates_ia")

# =========================================================================
# 🛡️ MÓDULO DE SEGURIDAD Y AUTENTICACIÓN (ISO 27001)
# =========================================================================

# 1. El Guardián: Función que verificará si el usuario tiene permiso
async def verificar_sesion(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})
    
    try:
        res = supabase.auth.get_user(token)
        if not res or not res.user:
            raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})
        return res.user
    except Exception:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})

# 🔥 CREACIÓN DE LA ZONA PROTEGIDA (Router VIP)
rutas_protegidas = APIRouter(dependencies=[Depends(verificar_sesion)])

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    # Si hay un error (ej. contraseña incorrecta), lo pasamos al HTML
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"request": request, "error": error}
    )

# 3. Ruta para procesar el formulario de Login (PÚBLICA)
@app.post("/login")
async def procesar_login(response: Response, email: str = Form(...), password: str = Form(...)):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        token = auth_response.session.access_token
        redirect_response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        redirect_response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=28800
        )
        return redirect_response
        
    except Exception as e:
        print(f"Intento de acceso fallido: {e}")
        return RedirectResponse(url="/login?error=credenciales_invalidas", status_code=status.HTTP_302_FOUND)

# 4. Ruta para Cerrar Sesión (PÚBLICA)
@app.get("/logout")
async def logout():
    redirect_response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    redirect_response.delete_cookie("access_token")
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    return redirect_response

# ==========================================
# 1. RUTA DEL FRONTEND (GLOBAL OVERVIEW) - PROTEGIDA
# ==========================================
@rutas_protegidas.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, fecha: str = None):
    fecha_consulta = fecha if fecha else "2025-06-26" 
    
    try:
        # --- 1. VOLUMEN DE MIGRACIONES ---
        resp_mig = supabase.table("vw_rt_embudo_llamadas").select("*").eq("date", fecha_consulta).execute()
        data_mig = resp_mig.data[0] if resp_mig.data else {"total_base": 0}
        vol_migraciones = data_mig.get("total_base", 0)
        
        # --- 2. VOLUMEN DE RETENCIONES ---
        resp_ret = supabase.table("vw_ret_rt_embudo").select("*").eq("date", fecha_consulta).execute()
        data_ret = resp_ret.data[0] if resp_ret.data else {"total_base": 0}
        vol_retenciones = data_ret.get("total_base", 0)

        # --- 3. VOLUMEN DE RRSS ---
        resp_rrss = supabase.table("vw_rrss_master_unificada").select("id_conversacion").eq("fecha_real", fecha_consulta).execute()
        vol_rrss = len(resp_rrss.data) if resp_rrss.data else 0

        volumen_total = vol_migraciones + vol_retenciones + vol_rrss

        # --- 4. ALERTAS DE INTELIGENCIA ARTIFICIAL ---
        respuesta_alertas = supabase.table("ml_alertas_globales").select("*").eq("call_date", fecha_consulta).order("call_time", desc=True).execute()
        alertas_ia = respuesta_alertas.data if respuesta_alertas.data else []

        # --- 5. SÚPER-DICCIONARIO DE AGENTES (FIX: LÍMITE DE 10,000 FILAS) ---
        # Evitamos que Supabase corte la lista en 1000 y se pierdan asesores como el 1076626271
        resp_agentes = supabase.table("dim_agentes").select("id, cedula, five9, asesor").limit(10000).execute()
        mapa_nombres = {}
        
        for ag in (resp_agentes.data or []):
            nom = str(ag.get("asesor") or "").strip()
            if not nom or nom.lower() in ["none", "null", ""]:
                continue
                
            ced = str(ag.get("cedula") or "").strip().replace('.0', '')
            id_int = str(ag.get("id") or "").strip().replace('.0', '')
            f9 = str(ag.get("five9") or "").strip().replace('.0', '')
            
            if ced and ced.lower() != "none": mapa_nombres[ced] = nom
            if id_int and id_int.lower() != "none": mapa_nombres[id_int] = nom
            if f9 and f9.lower() != "none": mapa_nombres[f9] = nom

    except Exception as e:
        print(f"❌ Error conectando a Supabase en Global Overview: {e}")
        vol_migraciones = vol_retenciones = vol_rrss = volumen_total = 0
        alertas_ia = []
        mapa_nombres = {}

    conteo_frentes = {"Migraciones": 0, "Retenciones": 0, "RRSS": 0}
    import re
    
    for alerta in alertas_ia:
        origen = str(alerta.get("origen_datos", "")).lower()
        descripcion = str(alerta.get("descripcion", ""))
        
        if "migracion" in origen:
            conteo_frentes["Migraciones"] += 1
            alerta["origen_datos"] = "Migraciones Inbound"
        elif "retencion" in origen:
            conteo_frentes["Retenciones"] += 1
            alerta["origen_datos"] = "Retenciones Outbound"
        elif "chat" in origen or "rrss" in origen or "redes" in origen:
            conteo_frentes["RRSS"] += 1
            alerta["origen_datos"] = "Redes Sociales (Chat)"
            
        # ========================================================
        # LÓGICA DE EXTRACCIÓN DE NOMBRES SEGÚN FRENTE OPERATIVO
        # ========================================================
        
        if alerta["origen_datos"] == "Redes Sociales (Chat)":
            # Para RRSS, extraemos el nombre directamente de la descripción (Ej: "Agente Yeimy Katherine...")
            match_nombre = re.search(r'Agente\s+(.*?)\s+registró', descripcion, re.IGNORECASE)
            
            if match_nombre:
                alerta["nombre_asesor"] = match_nombre.group(1).strip()
            else:
                alerta["nombre_asesor"] = "Asesor Digital"
                
            # Mostramos el ID del Chat de forma limpia
            id_chat = str(alerta.get("asesor_id") or alerta.get("identificador_registro") or "N/A").split('.')[0]
            alerta["asesor_id_limpio"] = f"Chat {id_chat}"
            
        else:
            # Para Llamadas (Migraciones y Retenciones), cruzamos con la base de datos
            as_id_raw = str(alerta.get("asesor_id") or "").strip().split('.')[0]
            if not as_id_raw or as_id_raw.lower() in ["none", "nan", ""]:
                as_id_raw = str(alerta.get("agente") or "").strip().split('.')[0]
                
            if not as_id_raw or as_id_raw.lower() in ["none", "nan", ""]:
                # 1. Busca el nuevo formato del backfill: "(ID: 12345)"
                match_id = re.search(r'ID:\s*(\w+)', descripcion, re.IGNORECASE)
                if not match_id:
                    # 2. Si no lo encuentra, busca el formato original: "Agente 12345 tipificó..."
                    match_id = re.search(r'(?:Agente|Asesor)\s+(\d+)', descripcion, re.IGNORECASE)
                
                as_id_raw = match_id.group(1) if match_id else "N/A"
                
            alerta["asesor_id_limpio"] = as_id_raw
            
            if as_id_raw != "N/A":
                alerta["nombre_asesor"] = mapa_nombres.get(as_id_raw, "Sin Asignación (No en BD)")
            else:
                alerta["nombre_asesor"] = "Desconocido (Anomalía de Sistema)"

        
    datos_dona = [conteo_frentes["Migraciones"], conteo_frentes["Retenciones"], conteo_frentes["RRSS"]]
    datos_barras = [vol_migraciones, vol_retenciones, vol_rrss]

    contexto_datos = {
        "request": request,
        "titulo": "Global Overview",
        "menu_activo": "global",
        "fecha_consulta": fecha_consulta,
        "volumen_total": volumen_total,
        "vol_migraciones": vol_migraciones,
        "vol_retenciones": vol_retenciones,
        "vol_rrss": vol_rrss,
        "total_alertas": len(alertas_ia),
        "alertas": alertas_ia,
        "datos_dona": datos_dona,
        "datos_barras": datos_barras
    }
    
    return templates.TemplateResponse(request=request, name="webdash.html", context=contexto_datos)


# =========================================================================
# 2. RUTA: 🔴 OPERACIÓN EN TIEMPO REAL (INTRADAY) - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/migraciones/rt", response_class=HTMLResponse)
async def migraciones_rt(request: Request, fecha: str = None):
    fecha_hoy_real = "2025-06-26" 
    fecha_consulta = fecha if fecha else fecha_hoy_real
    es_historico = fecha_consulta != fecha_hoy_real
    
    try:
        resp_embudo = supabase.table("vw_rt_embudo_llamadas").select("*").eq("date", fecha_consulta).execute()
        data_embudo = resp_embudo.data[0] if resp_embudo.data else {"total_base": 0, "contacto_cliente": 0, "contacto_favorable": 0}
        
        total_base = data_embudo.get("total_base", 0)
        contacto_cliente = data_embudo.get("contacto_cliente", 0)
        contacto_favorable = data_embudo.get("contacto_favorable", 0)

        resp_ventas = supabase.table("vw_rt_ventas_consolidadas").select("*").eq("date", fecha_consulta).execute()
        data_ventas = resp_ventas.data[0] if resp_ventas.data else {"ventas_totales": 0, "ventas_migraciones": 0, "ventas_portabilidad": 0, "ventas_linea_nueva": 0}
        
        ventas_totales = data_ventas.get("ventas_totales", 0)
        tipos_venta = {
            "Migraciones": data_ventas.get("ventas_migraciones", 0),
            "Portabilidad": data_ventas.get("ventas_portabilidad", 0),
            "Linea Nueva": data_ventas.get("ventas_linea_nueva", 0)
        }

        resp_agentes = supabase.table("vw_rt_agentes_leaderboard").select("*").eq("date", fecha_consulta).execute()
        lista_agentes = []
        activos_llamada = 0
        
        for ag in (resp_agentes.data or []):
            marcaciones = ag.get("marcaciones", 0)
            ventas = ag.get("ventas", 0)
            efectivas_2m = ag.get("llamadas_efectivas", 0)
            efec = min((ventas / efectivas_2m * 100), 100.0) if efectivas_2m > 0 else 0
            
            if marcaciones > 0 and not es_historico: 
                activos_llamada += 1
            
            lista_agentes.append({
                "id": ag.get("asesor_id", ""),
                "nombre": ag.get("nombre", "Desconocido"),
                "supervisor": ag.get("supervisor", "Sin Supervisor"),
                "marcaciones": marcaciones,
                "llamadas_efectivas": efectivas_2m,
                "ventas": ventas,
                "efectividad": round(efec, 2)
            })
        lista_agentes.sort(key=lambda x: (x["ventas"], x["efectividad"], x["marcaciones"]), reverse=True)
        
        total_agentes_activos = len(lista_agentes) if len(lista_agentes) > 0 else 1
        libres_pausa = max(0, total_agentes_activos - activos_llamada)

        resp_motivos = supabase.table("vw_rt_motivos_llamada").select("*").eq("date", fecha_consulta).order("cantidad", desc=True).limit(5).execute()
        traduccion_disposiciones = {
            "NO ANSWER": "Sin Respuesta", "CALLER DISCONNECTED": "Cliente Cuelga",
            "CLIENTE CUELGA": "Cliente Cuelga", "HANGUP": "Colgó / Cortó",
            "ANSWERING MACHINE": "Buzón de Voz", "BUZON": "Buzón de Voz",
            "ACEPTA": "Acepta / Interesado", "VENTA": "Venta Exitosa"
        }
        rt_nombres_motivos = []
        rt_valores_motivos = []
        for m in (resp_motivos.data or []):
            motivo_raw = m.get("motivo", "")
            motivo_limpio = traduccion_disposiciones.get(motivo_raw.upper(), motivo_raw.title())
            rt_nombres_motivos.append(motivo_limpio)
            rt_valores_motivos.append(m.get("cantidad", 0))

        resp_horas = supabase.table("vw_rt_distribucion_horas").select("*").eq("date", fecha_consulta).execute()
        distribucion_horas = {f"{h:02d}:00": 0 for h in range(8, 18)}
        for h in (resp_horas.data or []):
            hora = h.get("hora_llamada", "")
            if hora in distribucion_horas:
                distribucion_horas[hora] = h.get("volumen", 0)

    except Exception as e:
        print(f"❌ Error conectando a Supabase RT: {e}")
        total_base = contacto_cliente = contacto_favorable = ventas_totales = activos_llamada = libres_pausa = 0
        tipos_venta = {"Migraciones": 0, "Portabilidad": 0, "Linea Nueva": 0}
        lista_agentes, rt_nombres_motivos, rt_valores_motivos = [], [], []
        distribucion_horas = {f"{h:02d}:00": 0 for h in range(8, 18)}

    pct_contacto = (contacto_cliente / total_base * 100) if total_base > 0 else 0
    pct_favorable = (contacto_favorable / contacto_cliente * 100) if contacto_cliente > 0 else 0
    pct_venta_favorable = (ventas_totales / contacto_favorable * 100) if contacto_favorable > 0 else 0
    pct_venta_contacto = (ventas_totales / contacto_cliente * 100) if contacto_cliente > 0 else 0
    efectividad_acida = (ventas_totales / total_base * 100) if total_base > 0 else 0
    dispersion_data = [{"x": 160 + (i * 15) % 120, "y": ag["ventas"], "r": max(ag["marcaciones"] * 1.5, 4)} for i, ag in enumerate(lista_agentes)]

    alertas_rt_ml = []
    asesores_anomalos_ids = set()
    
    try:
        resp_ml = supabase.table("ml_alertas_globales").select("*")\
            .ilike("origen_datos", "%Migracion%")\
            .eq("call_date", fecha_consulta)\
            .order("fecha_deteccion", desc=True)\
            .limit(50).execute()
        
        for alerta in (resp_ml.data or []):
            raw_desc = str(alerta.get("descripcion", ""))
            desc_limpia = (raw_desc
                .replace("BuzÃ³n", "Buzón").replace("MigraciÃ³n", "Migración")
                .replace("Ã³", "ó").replace("Ã±", "ñ").replace("Ã¡", "á")
            )
            alerta["descripcion"] = desc_limpia

            as_id = str(alerta.get("asesor_id", "")).strip().replace('.0', '')
            if not as_id or as_id == "None":
                import re
                match = re.search(r'Agente\s+(\d+)', desc_limpia)
                if match: as_id = match.group(1)
            
            alerta["asesor_id"] = as_id if as_id else "N/A"
            if as_id and as_id != "N/A":
                asesores_anomalos_ids.add(as_id)

            c_date = alerta.get("call_date", "")
            c_time = alerta.get("call_time", "")
            if c_date and c_time: alerta["fecha_deteccion"] = f"{c_date} {c_time} (Llamada)"
            else:
                f_raw = str(alerta.get("fecha_deteccion", ""))
                alerta["fecha_deteccion"] = f_raw.replace("T", " ")[:19] if "T" in f_raw else "Reciente"

            alertas_rt_ml.append(alerta)
    except Exception as e: pass

    alertas_macro_ml = []
    try:
        resp_macro = supabase.table("ml_alertas_macro").select("*")\
            .ilike("origen_datos", "%Migracion%")\
            .eq("call_date", fecha_consulta).execute()
            
        for m in (resp_macro.data or []):
            c_date = str(m.get("call_date", ""))
            c_time = str(m.get("call_time", ""))
            if c_date and c_time: m["fecha_deteccion"] = f"{c_date} {c_time} (Franja Horaria)"
            alertas_macro_ml.append(m)
        alertas_macro_ml.sort(key=lambda x: (str(x.get("call_date", "")), str(x.get("call_time", ""))), reverse=True)
    except Exception: pass

    contexto = {
        "request": request, "titulo": "MIGRACIONES INBOUND", "menu_activo": "rt",
        "fecha_consulta": fecha_consulta, "es_historico": es_historico, "fecha_hoy_real": fecha_hoy_real, 
        "embudo": {
            "total_base": total_base, "contacto_cliente": contacto_cliente, "pct_contacto": round(pct_contacto, 2),
            "contacto_favorable": contacto_favorable, "pct_favorable": round(pct_favorable, 2),
            "ventas": ventas_totales, "pct_venta_favorable": round(pct_venta_favorable, 2),
            "pct_venta_contacto": round(pct_venta_contacto, 2), "efectividad_acida": round(efectividad_acida, 2)
        },
        "desglose_ventas": tipos_venta, "rt_nombres_motivos": rt_nombres_motivos, "rt_valores_motivos": rt_valores_motivos,
        "horas_labels": list(distribucion_horas.keys()), "horas_valores": list(distribucion_horas.values()),
        "estado_agentes": [activos_llamada, libres_pausa], "dispersion_agentes": dispersion_data,
        "alertas_rt_ml": alertas_rt_ml, "alertas_macro_ml": alertas_macro_ml, 
        "asesores_anomalos_ids": asesores_anomalos_ids, "agentes": lista_agentes
    }
    
    return templates.TemplateResponse(request=request, name="migraciones_rt.html", context=contexto)

# =========================================================================
# 4. RUTA: CIERRE DE JORNADA (EOD) - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/migraciones/eod", response_class=HTMLResponse)
async def migraciones_eod(request: Request, fecha: str = None):
    fecha_eod_str = fecha if fecha else "2025-06-26" 
    
    try:
        resp_kpis = supabase.table("vw_mig_eod_kpis").select("*").eq("date", fecha_eod_str).execute()
        data_kpis = resp_kpis.data[0] if resp_kpis.data else {"total_marcaciones": 0, "tmo_promedio": 0}
        eod_total_marcaciones = data_kpis.get("total_marcaciones", 0)
        eod_tmo_promedio = round(data_kpis.get("tmo_promedio", 0) or 0, 1)

        resp_ventas = supabase.table("vw_rt_ventas_consolidadas").select("*").eq("date", fecha_eod_str).execute()
        eod_ventas_totales = resp_ventas.data[0].get("ventas_totales", 0) if resp_ventas.data else 0

        resp_agentes = supabase.table("vw_mig_eod_agentes").select("*").eq("date", fecha_eod_str).execute()
        lista_asesores_eod = []
        for ag in (resp_agentes.data or []):
            lista_asesores_eod.append({
                "asesor": ag.get("asesor_id", ""),
                "marcaciones": ag.get("marcaciones", 0),
                "ventas": ag.get("ventas", 0),
                "efectividad": round(ag.get("efectividad", 0), 2)
            })
        
        eod_agentes_activos = len(lista_asesores_eod)
        eod_top_asesores = sorted(lista_asesores_eod, key=lambda x: (x["ventas"], x["efectividad"]), reverse=True)
        eod_bottom_asesores = sorted(lista_asesores_eod, key=lambda x: (x["ventas"], x["efectividad"]))

        resp_motivos = supabase.table("vw_mig_eod_motivos").select("*").eq("date", fecha_eod_str).order("cantidad", desc=True).limit(5).execute()
        eod_disp_labels = []
        eod_disp_valores = []
        for m in (resp_motivos.data or []):
            eod_disp_labels.append(m.get("motivo", ""))
            eod_disp_valores.append(m.get("cantidad", 0))

        resp_horas = supabase.table("vw_mig_eod_horas").select("*").eq("date", fecha_eod_str).execute()
        distribucion_horas = {f"{h:02d}:00": 0 for h in range(7, 19)}
        for h in (resp_horas.data or []):
            hora = h.get("hora_llamada", "")
            if hora in distribucion_horas:
                distribucion_horas[hora] = h.get("volumen", 0)
        
        eod_horas_labels = list(distribucion_horas.keys())
        eod_horas_valores = list(distribucion_horas.values())

        resp_insights = supabase.table("ml_insights_migraciones").select("*").eq("fecha_analisis", fecha_eod_str).execute()
        insights_raw = resp_insights.data if resp_insights.data else []
        insights_kmeans = [i for i in insights_raw if str(i.get("agente", "")).strip() not in ["0", "0.0", "None", "", "nan"]]
        insights_kmeans = sorted(insights_kmeans, key=lambda x: float(x.get("metrica_principal", 0)), reverse=True)

    except Exception as e:
        print(f"❌ Error conectando a Supabase para Cierre EOD: {e}")
        eod_total_marcaciones = eod_tmo_promedio = eod_ventas_totales = eod_agentes_activos = 0
        eod_disp_labels, eod_disp_valores, eod_horas_labels, eod_horas_valores, eod_top_asesores, eod_bottom_asesores, insights_kmeans = [], [], [], [], [], [], []

    eod_efectividad_acida = round((eod_ventas_totales / eod_total_marcaciones) * 100, 2) if eod_total_marcaciones > 0 else 0

    contexto_eod = {
        "request": request, "titulo": "Migraciones (Inbound)", "menu_activo": "migraciones_eod",
        "eod_fecha_analisis": fecha_eod_str, "eod_ventas_totales": eod_ventas_totales,
        "eod_efectividad_acida": eod_efectividad_acida, "eod_total_marcaciones": eod_total_marcaciones,
        "eod_tmo_promedio": eod_tmo_promedio, "eod_agentes_activos": eod_agentes_activos,
        "eod_horas_labels": eod_horas_labels, "eod_horas_valores": eod_horas_valores,
        "eod_disp_labels": eod_disp_labels, "eod_disp_valores": eod_disp_valores,
        "eod_top_asesores": eod_top_asesores, "eod_bottom_asesores": eod_bottom_asesores,
        "insights_kmeans": insights_kmeans
    }
    
    return templates.TemplateResponse(request=request, name="migraciones_eod.html", context=contexto_eod)

# =========================================================================
# 5. RUTA: CENTRO DE MANDO ML (MIGRACIONES) - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/migraciones/ml", response_class=HTMLResponse)
async def migraciones_ml(request: Request, fecha: str = None):
    fecha_analisis_str = fecha if fecha else "2025-06-26"
    
    try:
        resp_kmeans = supabase.table("vw_mig_ml_kmeans").select("*").eq("fecha_analisis", fecha_analisis_str).execute()
        kmeans_limpio = resp_kmeans.data if resp_kmeans.data else []
        
        resp_freq = supabase.table("vw_mig_ml_anomalias_freq").select("*").eq("call_date", fecha_analisis_str).execute()
        labels_anomalias = [f.get("tipo_alerta", "") for f in (resp_freq.data or [])]
        valores_anomalias = [f.get("cantidad", 0) for f in (resp_freq.data or [])]
        
        resp_if = supabase.table("ml_alertas_globales").select("*").eq("call_date", fecha_analisis_str).eq("origen_datos", "Migraciones").execute()
        if_data = resp_if.data if resp_if.data else []
        
        resp_macro = supabase.table("ml_alertas_macro").select("*").eq("call_date", fecha_analisis_str).execute()
        macro_data = resp_macro.data if resp_macro.data else []
        
        for m in macro_data:
            c_date = str(m.get("call_date", ""))
            c_time = str(m.get("call_time", ""))
            if c_date and c_time:
                m["fecha_deteccion"] = f"{c_date} {c_time} (Franja Horaria)"
                
        macro_data.sort(key=lambda x: (str(x.get("call_date", "")), str(x.get("call_time", ""))), reverse=True)
        
    except Exception as e:
        print(f"❌ Error conectando a Supabase para Análisis ML: {e}")
        kmeans_limpio, labels_anomalias, valores_anomalias, if_data, macro_data = [], [], [], [], []

    scatter_alto_rendimiento = []
    scatter_estandar = []
    scatter_oportunidad = []
    
    for k in kmeans_limpio:
        tmo = float(k.get("tmo_promedio") or 0)
        efec = float(k.get("efectividad") or 0)
        agente = str(k.get("asesor_id") or k.get("agente") or "")
        punto = {"x": tmo, "y": efec, "agente": agente}
        cluster = str(k.get("cluster_nombre", ""))
        
        if "Francotiradores" in cluster or "Estrella" in cluster:
            scatter_alto_rendimiento.append(punto)
        elif "Estándar" in cluster:
            scatter_estandar.append(punto)
        else:
            scatter_oportunidad.append(punto)

    contexto_ml = {
        "request": request, "titulo": "Migraciones Inbound", "menu_activo": "ml_migraciones",
        "fecha_analisis": fecha_analisis_str, "total_agentes_perfilados": len(kmeans_limpio),
        "total_micro_anomalias": len(if_data), "total_macro_anomalias": len(macro_data),
        "scatter_alto_rendimiento": scatter_alto_rendimiento, "scatter_estandar": scatter_estandar,
        "scatter_oportunidad": scatter_oportunidad, "labels_anomalias": labels_anomalias,
        "valores_anomalias": valores_anomalias, "macro_data": macro_data,
        "if_ultimas_alertas": sorted(if_data, key=lambda x: str(x.get("call_time", "")), reverse=True) 
    }
    
    return templates.TemplateResponse(request=request, name="migraciones_ml.html", context=contexto_ml)

# =========================================================================
# 6. RUTA: 🔵 RETENCIONES RT - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/retenciones/rt", response_class=HTMLResponse)
async def retenciones_rt(request: Request, fecha: str = None):
    fecha_hoy_real = "2025-06-26" 
    fecha_consulta = fecha if fecha else fecha_hoy_real
    es_historico = fecha_consulta != fecha_hoy_real
    
    try:
        resp_embudo = supabase.table("vw_ret_rt_embudo").select("*").eq("date", fecha_consulta).execute()
        data_embudo = resp_embudo.data[0] if resp_embudo.data else {
            "total_base": 0, "numero_llamados": 0, "contacto_cliente": 0, "contacto_favorable": 0, "retenciones": 0
        }
        
        total_base = data_embudo.get("total_base", 0)
        numero_llamados = data_embudo.get("numero_llamados", 0)
        contacto_cliente = data_embudo.get("contacto_cliente", 0)
        contacto_favorable = data_embudo.get("contacto_favorable", 0)
        retenciones = data_embudo.get("retenciones", 0)

        resp_agentes = supabase.table("vw_ret_rt_agentes").select("*").eq("date", fecha_consulta).execute()
        lista_agentes = []
        activos_llamada = 0
        
        for ag in (resp_agentes.data or []):
            marcaciones = ag.get("marcaciones", 0)
            ventas = ag.get("retenciones", 0)
            efectivas = ag.get("llamadas_efectivas", 0)
            
            efec = min((ventas / efectivas * 100), 100.0) if efectivas > 0 else 0
            if marcaciones > 0 and not es_historico: 
                activos_llamada += 1
            
            lista_agentes.append({
                "id": ag.get("asesor_id", ""),
                "nombre": ag.get("nombre", "Desconocido"),
                "supervisor": ag.get("supervisor", "Sin Supervisor"),
                "marcaciones": marcaciones,
                "llamadas_efectivas": efectivas,
                "ventas": ventas, 
                "efectividad": round(efec, 2)
            })
        lista_agentes.sort(key=lambda x: (x["ventas"], x["efectividad"], x["marcaciones"]), reverse=True)
        
        total_agentes_activos = len(lista_agentes) if len(lista_agentes) > 0 else 1
        libres_pausa = max(0, total_agentes_activos - activos_llamada)

        resp_motivos = supabase.table("vw_ret_rt_motivos").select("*").eq("date", fecha_consulta).order("cantidad", desc=True).limit(5).execute()
        traduccion_disposiciones = {
            "NO ANSWER": "Sin Respuesta", "HANGUP": "Colgó / Cortó", "ANSWERING MACHINE": "Buzón de Voz"
        }
        rt_nombres_motivos = []
        rt_valores_motivos = []
        for m in (resp_motivos.data or []):
            motivo_raw = m.get("tipificacion", "")
            motivo_limpio = traduccion_disposiciones.get(motivo_raw.upper(), motivo_raw.title())
            rt_nombres_motivos.append(motivo_limpio)
            rt_valores_motivos.append(m.get("cantidad", 0))

        resp_horas = supabase.table("vw_ret_rt_horas").select("*").eq("date", fecha_consulta).execute()
        distribucion_horas = {f"{h:02d}:00": 0 for h in range(8, 18)}
        for h in (resp_horas.data or []):
            hora = h.get("hora_llamada", "")
            if hora in distribucion_horas:
                distribucion_horas[hora] = h.get("volumen", 0)

    except Exception as e:
        print(f"❌ Error conectando a Supabase RETENCIONES RT: {e}")
        total_base = numero_llamados = contacto_cliente = contacto_favorable = retenciones = activos_llamada = libres_pausa = 0
        lista_agentes, rt_nombres_motivos, rt_valores_motivos = [], [], []
        distribucion_horas = {f"{h:02d}:00": 0 for h in range(8, 18)}

    barridos = round((numero_llamados / total_base), 2) if total_base > 0 else 0
    pct_contacto = (contacto_cliente / total_base * 100) if total_base > 0 else 0
    pct_favorable = (contacto_favorable / contacto_cliente * 100) if contacto_cliente > 0 else 0
    pct_ret_favorable = (retenciones / contacto_favorable * 100) if contacto_favorable > 0 else 0
    pct_ret_contacto = (retenciones / contacto_cliente * 100) if contacto_cliente > 0 else 0
    efectividad_acida = (retenciones / total_base * 100) if total_base > 0 else 0

    dispersion_data = [{"x": 160 + (i * 15) % 120, "y": ag["ventas"], "r": max(ag["marcaciones"] * 1.5, 4)} for i, ag in enumerate(lista_agentes)]

    alertas_rt_ml = []
    asesores_anomalos_ids = set()
    try:
        resp_ml = supabase.table("ml_alertas_globales").select("*")\
            .ilike("origen_datos", "%Retenciones%")\
            .eq("call_date", fecha_consulta)\
            .order("fecha_deteccion", desc=True).execute()
            
        todas_alertas = resp_ml.data if resp_ml.data else []
        
        for alerta in todas_alertas:
            raw_desc = str(alerta.get("descripcion", ""))
            desc_limpia = (raw_desc
                .replace("BuzÃ³n", "Buzón").replace("RetenciÃ³n", "Retención")
                .replace("Ã³", "ó").replace("Ã±", "ñ").replace("Ã¡", "á")
            )
            alerta["descripcion"] = desc_limpia

            as_id = str(alerta.get("identificador_registro", "")).strip().replace('.0', '')
            if not as_id or as_id == "None":
                import re
                match = re.search(r'Agente\s+(\d+)', desc_limpia)
                if match: as_id = match.group(1)
            
            alerta["asesor_id"] = as_id if as_id else "N/A"
            if as_id and as_id != "N/A":
                asesores_anomalos_ids.add(as_id)

            c_date = alerta.get("call_date")
            c_time = alerta.get("call_time")
            if c_date and c_time: alerta["fecha_deteccion"] = f"{c_date} {c_time}"
            else:
                f_raw = str(alerta.get("fecha_deteccion", ""))
                alerta["fecha_deteccion"] = f_raw.replace("T", " ")[:19] if "T" in f_raw else "Reciente"

            alertas_rt_ml.append(alerta)

    except Exception as e:
        print(f"⚠️️ Error al cargar alertas ML en RT Retenciones: {e}")

    contexto = {
        "request": request, "titulo": "Retenciones Outbound", "menu_activo": "rt_retenciones",
        "fecha_consulta": fecha_consulta, "es_historico": es_historico, "fecha_hoy_real": fecha_hoy_real,
        "embudo": {
            "total_base": total_base, "numero_llamados": numero_llamados, "barridos": barridos,
            "contacto_cliente": contacto_cliente, "pct_contacto": round(pct_contacto, 2),
            "contacto_favorable": contacto_favorable, "pct_favorable": round(pct_favorable, 2),
            "retenciones": retenciones, "pct_ret_favorable": round(pct_ret_favorable, 2),
            "pct_ret_contacto": round(pct_ret_contacto, 2), "efectividad_acida": round(efectividad_acida, 2)
        },
        "rt_nombres_motivos": rt_nombres_motivos, "rt_valores_motivos": rt_valores_motivos,
        "horas_labels": list(distribucion_horas.keys()), "horas_valores": list(distribucion_horas.values()),
        "estado_agentes": [activos_llamada, libres_pausa], "dispersion_agentes": dispersion_data,
        "alertas_rt_ml": alertas_rt_ml, "asesores_anomalos_ids": asesores_anomalos_ids, "agentes": lista_agentes
    }
    
    return templates.TemplateResponse(request=request, name="retenciones_rt.html", context=contexto)

# =========================================================================
# 7. RUTA: 🔵 RETENCIONES EOD - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/retenciones/eod", response_class=HTMLResponse)
async def retenciones_eod(request: Request, fecha: str = None):
    try:
        resp_fechas = supabase.table("vw_ret_eod_kpis").select("fecha").execute()
        fechas_disp = sorted(list(set([f["fecha"] for f in (resp_fechas.data or []) if f["fecha"]])), reverse=True)
        fecha_str = fecha if fecha else (fechas_disp[0] if fechas_disp else "2025-06-26")

        resp_kpis = supabase.table("vw_ret_eod_kpis").select("*").eq("fecha", fecha_str).execute()
        data_kpis = resp_kpis.data[0] if resp_kpis.data else {}

        total_base = data_kpis.get("total_base") or 0
        numero_llamados = data_kpis.get("marcaciones") or 0
        contacto_cliente = data_kpis.get("contacto_cliente") or 0
        contacto_favorable = data_kpis.get("contacto_favorable") or 0
        retenciones = data_kpis.get("retenciones") or 0

        pct_contacto = round((contacto_cliente / total_base) * 100, 1) if total_base > 0 else 0
        pct_ret_favorable = round((retenciones / contacto_favorable) * 100, 1) if contacto_favorable > 0 else 0
        efectividad_acida = round((retenciones / total_base) * 100, 1) if total_base > 0 else 0
        barridos = round(numero_llamados / total_base, 1) if total_base > 0 else 0

        embudo = {
            "total_base": total_base, "numero_llamados": numero_llamados, "barridos": barridos,
            "contacto_cliente": contacto_cliente, "pct_contacto": pct_contacto,
            "contacto_favorable": contacto_favorable, "retenciones": retenciones,
            "pct_ret_favorable": pct_ret_favorable, "efectividad_acida": efectividad_acida
        }

        resp_horas = supabase.table("vw_ret_eod_horas").select("*").eq("fecha", fecha_str).order("hora").execute()
        horas_labels = [f"{h['hora']}:00" for h in (resp_horas.data or [])]
        horas_valores = [h.get("volumen") or 0 for h in (resp_horas.data or [])]

        resp_motivos = supabase.table("vw_ret_eod_motivos").select("*").eq("fecha", fecha_str).order("volumen", desc=True).limit(10).execute()
        nombres_motivos = [m.get("tipificacion", "Desconocido") for m in (resp_motivos.data or [])]
        valores_motivos = [m.get("volumen") or 0 for m in (resp_motivos.data or [])]

        resp_agentes = supabase.table("vw_ret_eod_agentes").select("*").eq("fecha", fecha_str).execute()
        agentes_eod = resp_agentes.data if resp_agentes.data else []

        for ag in agentes_eod:
            efec = ag.get("llamadas_efectivas") or 0
            ret = ag.get("retenciones") or 0
            ag["efectividad"] = round((ret / efec) * 100, 1) if efec > 0 else 0

        agentes_eod.sort(key=lambda x: x.get("retenciones") or 0, reverse=True)

        resp_insights = supabase.table("ml_insights_retenciones").select("*").eq("fecha_analisis", fecha_str).execute()
        insights_raw = resp_insights.data if resp_insights.data else []
        insights_ia = [i for i in insights_raw if str(i.get("agente", "")).strip() not in ["0", "0.0", "None", "", "nan"]]
        
    except Exception as e:
        print(f"❌ Error interno en la ruta /retenciones/eod: {e}")
        fecha_str = "2025-06-26"
        fechas_disp, horas_labels, horas_valores, nombres_motivos, valores_motivos, agentes_eod, insights_ia = [], [], [], [], [], [], []
        embudo = {"total_base": 0, "numero_llamados": 0, "barridos": 0, "contacto_cliente": 0, "pct_contacto": 0, "contacto_favorable": 0, "retenciones": 0, "pct_ret_favorable": 0, "efectividad_acida": 0}

    contexto = {
        "request": request, "titulo": "Retenciones Outbound", "menu_activo": "eod_retenciones",
        "fecha_seleccionada": fecha_str, "fechas_disponibles": fechas_disp, "embudo": embudo,
        "horas_labels": horas_labels, "horas_valores": horas_valores, "nombres_motivos": nombres_motivos,
        "valores_motivos": valores_motivos, "agentes": agentes_eod, "insights_ia": insights_ia
    }

    return templates.TemplateResponse(request=request, name="retenciones_eod.html", context=contexto)

# =========================================================================
# 8. RUTA: 🟣 RETENCIONES ML - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/retenciones/ml", response_class=HTMLResponse)
async def retenciones_ml(request: Request, fecha: str = None):
    fecha_analisis_str = fecha if fecha else "2025-06-26"
    
    try:
        resp_kmeans = supabase.table("ml_insights_retenciones").select("*").eq("fecha_analisis", fecha_analisis_str).execute()
        kmeans_raw = resp_kmeans.data if resp_kmeans.data else []
        kmeans_limpio = [k for k in kmeans_raw if str(k.get("agente", "")).strip() not in ["0", "0.0", "None", "", "nan"]]
        
        resp_if = supabase.table("ml_alertas_globales").select("*").eq("call_date", fecha_analisis_str).eq("origen_datos", "Retenciones Outbound").execute()
        if_data = resp_if.data if resp_if.data else []
        
        freq_dict = {}
        for alerta in if_data:
            tipo = alerta.get("tipo_alerta", "Desconocida")
            freq_dict[tipo] = freq_dict.get(tipo, 0) + 1
            
        labels_anomalias = list(freq_dict.keys())
        valores_anomalias = list(freq_dict.values())
        
    except Exception as e:
        print(f"❌ Error conectando a Supabase para Análisis ML Retenciones: {e}")
        kmeans_limpio, if_data, labels_anomalias, valores_anomalias = [], [], [], []

    scatter_alto_rendimiento = []
    scatter_estandar = []
    scatter_oportunidad = []
    
    for k in kmeans_limpio:
        tmo = float(k.get("metrica_secundaria") or 0)
        efec = float(k.get("metrica_principal") or 0)
        agente = str(k.get("agente", ""))
        punto = {"x": tmo, "y": efec, "agente": agente}
        cluster = str(k.get("cluster_nombre", ""))
        
        if "Estrella" in cluster or "Top Performers" in cluster:
            scatter_alto_rendimiento.append(punto)
        elif "Estándar" in cluster:
            scatter_estandar.append(punto)
        else:
            scatter_oportunidad.append(punto)

    kmeans_limpio.sort(key=lambda x: float(x.get("metrica_principal", 0)), reverse=True)

    contexto_ml = {
        "request": request, "titulo": "Retenciones Outbound", "menu_activo": "ml_retenciones",
        "fecha_analisis": fecha_analisis_str, "total_agentes_perfilados": len(kmeans_limpio),
        "total_micro_anomalias": len(if_data), "scatter_alto_rendimiento": scatter_alto_rendimiento,
        "scatter_estandar": scatter_estandar, "scatter_oportunidad": scatter_oportunidad,
        "labels_anomalias": labels_anomalias, "valores_anomalias": valores_anomalias,
        "insights_kmeans": kmeans_limpio, "if_ultimas_alertas": sorted(if_data, key=lambda x: str(x.get("call_time", "")), reverse=True) 
    }
    
    return templates.TemplateResponse(request=request, name="retenciones_ml.html", context=contexto_ml)

# =========================================================================
# 9. RUTA: 🟢 REDES SOCIALES (RRSS) RT - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/rrss/rt", response_class=HTMLResponse)
async def rrss_rt(request: Request, fecha: str = None, segmento_filtro: str = 'General'):
    fecha_hoy_real = "2025-06-26" 
    fecha_consulta = fecha if fecha else fecha_hoy_real
    es_historico = fecha_consulta != fecha_hoy_real
    
    try:
        resp_master = supabase.table("vw_rrss_master_unificada").select("*").eq("fecha_real", fecha_consulta).execute()
        df_master = pd.DataFrame(resp_master.data if resp_master.data else [])

        if not df_master.empty:
            if segmento_filtro != 'General':
                df_filtrado = df_master[df_master['segmento'] == segmento_filtro].copy()
            else:
                df_filtrado = df_master.copy()

            df_atendidos = df_filtrado[df_filtrado['es_atendido'] == 1].copy()
            df_atendidos['tmo_seg'] = pd.to_numeric(df_atendidos['tmo_seg'], errors='coerce').fillna(0)
            
            ofrecidas_totales = len(df_filtrado)
            atendidas_totales = len(df_atendidos)
            chats_pendientes = ofrecidas_totales - atendidas_totales
            
            tmo_promedio = round(df_atendidos['tmo_seg'].mean(), 1) if not df_atendidos.empty else 0
            asa_promedio = round(df_atendidos['asa_seg'].mean(), 1) if not df_atendidos.empty else 0
            
            umbral_ok = df_atendidos['cumple_umbral'].sum() if not df_atendidos.empty else 0
            sla_vivo = round((umbral_ok / atendidas_totales) * 100, 1) if atendidas_totales > 0 else 0

            if not df_atendidos.empty:
                df_atendidos['canal_seguro'] = df_atendidos['canal_final'].replace([None, '', 'NaN'], 'RRSS')
                conteo_canal = df_atendidos['canal_seguro'].value_counts().to_dict()
                labels_canal = list(conteo_canal.keys())
                valores_canal = list(conteo_canal.values())
            else:
                labels_canal, valores_canal = [], []

            df_atendidos['agente_seguro'] = df_atendidos['agente'].replace([None, '', 'NaN'], 'Sin Asignar')
            agentes_vivo = df_atendidos.groupby('agente_seguro').agg(
                chats=('id_conversacion', 'count'), tmo_actual=('tmo_seg', 'mean')
            ).reset_index().sort_values(by='chats', ascending=False).head(15)
            agentes_vivo['tmo_actual'] = agentes_vivo['tmo_actual'].round(1)
            agentes_vivo.rename(columns={'agente_seguro': 'Agente'}, inplace=True)
            lista_agentes = agentes_vivo.to_dict('records')

            df_matriz = df_filtrado.groupby('canal_final').agg(
                ofrecidas=('id_conversacion', 'count'), atendidas=('es_atendido', 'sum'), atendidas_4min=('cumple_umbral', 'sum')
            ).reset_index()
            
            if not df_atendidos.empty:
                promedios = df_atendidos.groupby('canal_final').agg(tmo=('tmo_seg', 'mean'), asa=('asa_seg', 'mean')).reset_index()
                df_matriz = pd.merge(df_matriz, promedios, on='canal_final', how='left').fillna(0)
            else:
                df_matriz['tmo'] = 0; df_matriz['asa'] = 0

            df_matriz['sla'] = np.where(df_matriz['atendidas'] > 0, round((df_matriz['atendidas_4min'] / df_matriz['atendidas']) * 100, 1), 0)
            df_matriz['tmo'] = df_matriz['tmo'].round(1)
            df_matriz['asa'] = df_matriz['asa'].round(1)
            matriz_rt = df_matriz.to_dict('records')

            df_horas = df_filtrado.groupby('hora_bloque').agg(
                ofrecidas=('id_conversacion', 'count'), atendidas=('es_atendido', 'sum')
            ).reset_index().sort_values('hora_bloque') 
            df_horas['hora_limpia'] = df_horas['hora_bloque'].astype(str).str[:5] 
            desglose_horas = df_horas.to_dict('records')
            
        else:
            chats_pendientes = atendidas_totales = tmo_promedio = asa_promedio = sla_vivo = 0
            labels_canal, valores_canal, lista_agentes, matriz_rt, desglose_horas = [], [], [], [], []

    except Exception as e:
        print(f"❌ Error en RRSS Tiempo Real: {e}")
        chats_pendientes = atendidas_totales = tmo_promedio = asa_promedio = sla_vivo = 0
        labels_canal, valores_canal, lista_agentes, matriz_rt, desglose_horas = [], [], [], [], []

    try:
        response_alertas = supabase.table("ml_alertas_globales").select("*")\
            .ilike("origen_datos", "%Redes Sociales%")\
            .eq("call_date", fecha_consulta)\
            .order("fecha_deteccion", desc=True).execute()
            
        alertas_ml = response_alertas.data if response_alertas.data else []
        
        for alerta in alertas_ml:
            c_date = alerta.get('call_date', '')
            c_time = str(alerta.get('call_time', ''))[:8] 
            
            if c_date and c_time:
                alerta['fecha_formateada'] = f"{c_date} {c_time}"
            else:
                alerta['fecha_formateada'] = str(alerta.get('fecha_deteccion', ''))[:16].replace('T', ' ')
                
    except Exception as e:
        print(f"❌ Error consultando alertas ML en RRSS: {e}")
        alertas_ml = []

    contexto_rt = {
        "request": request, "titulo": "Redes Sociales", "menu_activo": "rt_rrss",
        "fecha_consulta": fecha_consulta, "es_historico": es_historico, "fecha_hoy_real": fecha_hoy_real,
        "segmento_activo": segmento_filtro, "chats_pendientes": chats_pendientes, 
        "chats_atendidos": atendidas_totales, "asa_vivo": asa_promedio, 
        "tmo_vivo": tmo_promedio, "sla_vivo": sla_vivo,
        "labels_canal": labels_canal, "valores_canal": valores_canal, "agentes_vivo": lista_agentes,
        "matriz_rt": matriz_rt, "desglose_horas": desglose_horas, "alertas_ml": alertas_ml 
    }

    return templates.TemplateResponse(request=request, name="rrss_rt.html", context=contexto_rt)

# =========================================================================
# 10. RUTA: 🟢 REDES SOCIALES (RRSS) EOD - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/rrss/eod", response_class=HTMLResponse)
async def rrss_eod(request: Request, fecha: str = None):
    fecha_seleccionada = fecha if fecha else "2025-06-26"
    tramos_tmo = {"0_5": 0, "5_10": 0, "10_20": 0, "mas_20": 0} 
    
    if "/" in fecha_seleccionada:
        partes = fecha_seleccionada.split("/")
        if len(partes) == 3 and len(partes[2]) == 4:
            fecha_seleccionada = f"{partes[2]}-{partes[0].zfill(2)}-{partes[1].zfill(2)}"

    try:
        resp_matriz = supabase.table("vw_hist_rrss_eod_matriz").select("*").eq("fecha_real", fecha_seleccionada).execute()
        df_matriz = pd.DataFrame(resp_matriz.data if resp_matriz.data else [])

        resp_master = supabase.table("vw_hist_rrss_master").select("*").eq("fecha_real", fecha_seleccionada).execute()
        df_master = pd.DataFrame(resp_master.data if resp_master.data else [])

        if not df_matriz.empty:
            ofrecidas_totales = int(df_matriz['ofrecidas'].sum())
            atendidas_totales = int(df_matriz['atendidas'].sum())
            atend_4m_totales = int(df_matriz['atendidas_4min'].sum())
            
            df_atendidos = df_master[df_master['es_atendido'] == 1]
            tmo_promedio = round(df_atendidos['tmo_seg'].mean(), 1) if not df_atendidos.empty else 0
            asa_promedio = round(df_atendidos['asa_seg'].mean(), 1) if not df_atendidos.empty else 0
            sla_global = round((atend_4m_totales / atendidas_totales) * 100, 1) if atendidas_totales > 0 else 0

            df_unicos = df_matriz[df_matriz['canal_final'].str.contains('Unicos|Monetizacion', case=False, na=False)].copy()
            df_reaperturas = df_matriz[df_matriz['canal_final'].str.contains('Reapertura', case=False, na=False)].copy()
            
            df_unicos['canal_final'] = df_unicos['canal_final'].str.replace(' Unicos', '', regex=False).str.strip()
            df_reaperturas['canal_final'] = df_reaperturas['canal_final'].str.replace(' Reapertura', '', regex=False).str.strip()

            lista_unicos = df_unicos.to_dict('records')
            lista_reaperturas = df_reaperturas.to_dict('records')

            df_agg = df_matriz.copy()
            df_agg['canal_puro'] = df_agg['canal_final'].str.replace(' Unicos', '').str.replace(' Reapertura', '').str.strip()
            
            df_general = df_agg.groupby('canal_puro').agg({
                'ofrecidas': 'sum', 'atendidas': 'sum', 'atendidas_4min': 'sum',
                'frcst': 'sum', 'promotores': 'sum', 'detractores': 'sum', 'pasivos': 'sum'
            }).reset_index()
            
            promedios_gen = df_master[df_master['es_atendido']==1].groupby('canal_final').agg(tmo=('tmo_seg', 'mean'), asa=('asa_seg', 'mean')).reset_index().rename(columns={'canal_final': 'canal_puro'})
            
            df_general = pd.merge(df_general, promedios_gen, on='canal_puro', how='left').fillna(0)
            df_general['sla'] = np.where(df_general['atendidas'] > 0, round((df_general['atendidas_4min'] / df_general['atendidas']) * 100, 1), 0)
            df_general['tmo'] = df_general['tmo'].round(1)
            df_general['asa'] = df_general['asa'].round(1)
            df_general.rename(columns={'canal_puro': 'canal_final'}, inplace=True)
            lista_general = df_general.to_dict('records')

            tramos_tmo = {'0-5 min': 0, '5-10 min': 0, '10-20 min': 0, 'Mas 20 min': 0}
            if not df_atendidos.empty:
                for tmo in df_atendidos['tmo_seg']:
                    if tmo <= 300: tramos_tmo['0-5 min'] += 1
                    elif tmo <= 600: tramos_tmo['5-10 min'] += 1
                    elif tmo <= 1200: tramos_tmo['10-20 min'] += 1
                    else: tramos_tmo['Mas 20 min'] += 1
            
            valores_nps = [int(df_matriz['promotores'].sum()), int(df_matriz['pasivos'].sum()), int(df_matriz['detractores'].sum())]
            if sum(valores_nps) == 0: valores_nps = [0, 0, 0]

            trafico = df_master.groupby('hora_bloque').agg(ofrecidas=('id_conversacion', 'count'), atendidas=('es_atendido', 'sum')).reset_index().sort_values('hora_bloque')
            labels_horas = trafico['hora_bloque'].astype(str).str[:5].tolist()
            data_ofrecidas = trafico['ofrecidas'].tolist()
            data_atendidas = trafico['atendidas'].tolist()

        else:
            ofrecidas_totales = atendidas_totales = tmo_promedio = asa_promedio = sla_global = 0
            lista_general, lista_unicos, lista_reaperturas, labels_horas, data_ofrecidas, data_atendidas = [], [], [], [], [], []
            valores_nps = [0, 0, 0]

        try:
            resp_insights = supabase.table("ml_insights_rrss").select("*").eq("fecha_analisis", fecha_seleccionada).execute()
            insights_raw = resp_insights.data if resp_insights.data else []
            insights_kmeans = [i for i in insights_raw if str(i.get("agente", "")).strip() not in ["0", "0.0", "None", "", "nan"]]
            insights_kmeans = sorted(insights_kmeans, key=lambda x: float(x.get("metrica_principal", 0)), reverse=True)
        except: insights_kmeans = []

    except Exception as e:
        print(f"❌ Error CRÍTICO en RRSS EOD: {e}")
        ofrecidas_totales = atendidas_totales = tmo_promedio = asa_promedio = sla_global = 0
        lista_general, lista_unicos, lista_reaperturas, labels_horas, data_ofrecidas, data_atendidas, insights_kmeans = [], [], [], [], [], [], []
        valores_nps = [0, 0, 0]

    contexto_eod = {
        "request": request, "titulo": "Redes Sociales", "menu_activo": "eod_rrss",
        "fecha_seleccionada": fecha_seleccionada, "ofrecidas": ofrecidas_totales,
        "atendidas": atendidas_totales, "tmo": tmo_promedio, "asa": asa_promedio, "sla": sla_global,
        "matriz_general": lista_general, "matriz_unicos": lista_unicos, "matriz_reaperturas": lista_reaperturas,
        "labels_horas": labels_horas, "data_ofrecidas": data_ofrecidas, "data_atendidas": data_atendidas,
        "valores_nps": valores_nps, "insights_kmeans": insights_kmeans, "tramos_tmo": tramos_tmo 
    }
    
    return templates.TemplateResponse(request=request, name="rrss_eod.html", context=contexto_eod)

# =========================================================================
# 11. RUTA: 🟣 REDES SOCIALES (RRSS) ML - PROTEGIDA
# =========================================================================
@rutas_protegidas.get("/rrss/ml", response_class=HTMLResponse)
async def rrss_ml(request: Request, fecha: str = None):
    fecha_analisis_str = fecha if fecha else "2025-06-26"
    
    try:
        resp_kmeans = supabase.table("ml_insights_rrss").select("*").eq("fecha_analisis", fecha_analisis_str).execute()
        kmeans_raw = resp_kmeans.data if resp_kmeans.data else []
        kmeans_limpio = [k for k in kmeans_raw if str(k.get("agente", "")).strip() not in ["0", "0.0", "None", "", "nan"]]
        
        resp_if = supabase.table("ml_alertas_globales").select("*").eq("call_date", fecha_analisis_str).eq("origen_datos", "Redes Sociales").execute()
        if_data = resp_if.data if resp_if.data else []
        
        freq_dict = {}
        for alerta in if_data:
            tipo_raw = str(alerta.get("tipo_alerta", "Desconocida"))
            tipo_limpio = tipo_raw.replace("Ã³", "ó").replace("Ã±", "ñ").replace("Ã¡", "á").replace("Ã©", "é").replace("Ã", "í")
            freq_dict[tipo_limpio] = freq_dict.get(tipo_limpio, 0) + 1
            
            c_date = alerta.get('call_date', '')
            c_time = str(alerta.get('call_time', ''))[:8]
            alerta['fecha_formateada'] = f"{c_date} {c_time}" if c_date and c_time else str(alerta.get('fecha_deteccion', ''))[:16].replace('T', ' ')
            
        labels_anomalias = list(freq_dict.keys())
        valores_anomalias = list(freq_dict.values())
        
    except Exception as e:
        print(f"❌ Error conectando a Supabase para Análisis ML RRSS: {e}")
        kmeans_limpio, if_data, labels_anomalias, valores_anomalias = [], [], [], []

    scatter_alto_rendimiento = []
    scatter_estandar = []
    scatter_oportunidad = []
    
    for k in kmeans_limpio:
        tmo = float(k.get("metrica_secundaria") or 0)  
        efec = float(k.get("metrica_principal") or 0)   
        agente = str(k.get("agente", ""))
        
        punto = {"x": tmo, "y": efec, "agente": agente}
        cluster = str(k.get("cluster_nombre", ""))
        
        if "Estrella" in cluster or "Alto" in cluster:
            scatter_alto_rendimiento.append(punto)
        elif "Estándar" in cluster or "Estandar" in cluster:
            scatter_estandar.append(punto)
        else:
            scatter_oportunidad.append(punto)

    kmeans_limpio.sort(key=lambda x: float(x.get("metrica_principal", 0)), reverse=True)

    contexto_ml = {
        "request": request, "titulo": "Redes Sociales", "menu_activo": "ml_rrss",
        "fecha_analisis": fecha_analisis_str, "total_agentes_perfilados": len(kmeans_limpio),
        "total_micro_anomalias": len(if_data), "scatter_alto_rendimiento": scatter_alto_rendimiento,
        "scatter_estandar": scatter_estandar, "scatter_oportunidad": scatter_oportunidad,
        "labels_anomalias": labels_anomalias, "valores_anomalias": valores_anomalias,
        "insights_kmeans": kmeans_limpio, "if_ultimas_alertas": sorted(if_data, key=lambda x: str(x.get("call_time", "")), reverse=True) 
    }
    
    return templates.TemplateResponse(request=request, name="rrss_ml.html", context=contexto_ml)

# =========================================================================
# 12. RUTA: 🔎 AGENT ANALYTICS (BUSCADOR DE RENDIMIENTO HISTÓRICO)
# =========================================================================
@rutas_protegidas.get("/analytics/agente", response_class=HTMLResponse)
async def agent_analytics(request: Request, cedula: str = None):
    datos_agente = None
    alertas_agente = []
    
    if cedula:
        try:
            resp_agente = supabase.table("vw_aa_resumen_agente").select("*").eq("asesor_id", cedula).execute()
            if resp_agente.data:
                datos_agente = resp_agente.data[0]
            
            resp_alertas = supabase.table("ml_alertas_globales").select("*").eq("asesor_id", cedula).order("call_date", desc=True).order("call_time", desc=True).execute()
            alertas_agente = resp_alertas.data if resp_alertas.data else []
            
            for alerta in alertas_agente:
                c_date, c_time = alerta.get('call_date', ''), str(alerta.get('call_time', ''))[:8]
                alerta['fecha_formateada'] = f"{c_date} {c_time}" if c_date and c_time else str(alerta.get('fecha_deteccion', ''))[:16].replace('T', ' ')
                
        except Exception as e:
            print(f"❌ Error consultando Agent Analytics para {cedula}: {e}")
            
    contexto_aa = {
        "request": request,
        "titulo": "Agent Analytics",
        "menu_activo": "agent_analytics",
        "cedula_buscada": cedula,
        "agente": datos_agente,
        "alertas": alertas_agente
    }
    
    return templates.TemplateResponse(request=request, name="agent_analytics.html", context=contexto_aa)

# =========================================================================
# 13. RUTA: 🛡️ SYSTEM ADMINISTRATOR (GESTIÓN DE USUARIOS)
# =========================================================================
@rutas_protegidas.get("/admin/usuarios", response_class=HTMLResponse)
async def gestion_usuarios(request: Request, msg: str = None):
    # Para tu sustentación, mostramos una lista controlada de la jerarquía
    usuarios_activos = [
        {"nombre": "Juan Guillermo Velasco", "email": "jvelasco@apex.com", "rol": "System Administrator", "estado": "Activo", "ultimo_acceso": "Hace 5 min"},
        {"nombre": "Alexander Morales Silva", "email": "amorales@apex.com", "rol": "Supervisor WFM", "estado": "Activo", "ultimo_acceso": "Hace 2 horas"},
        {"nombre": "Jonathan Andrés Daza", "email": "jdaza@apex.com", "rol": "Supervisor RT", "estado": "Activo", "ultimo_acceso": "Hace 1 hora"},
        {"nombre": "Auditor Calidad", "email": "auditor@wom.com", "rol": "Lector Externo", "estado": "Inactivo", "ultimo_acceso": "Hace 3 días"}
    ]
    
    contexto_admin = {
        "request": request,
        "titulo": "Gestión de Usuarios",
        "menu_activo": "admin_usuarios",
        "usuarios": usuarios_activos,
        "msg": msg
    }
    return templates.TemplateResponse(request=request, name="gestion_usuarios.html", context=contexto_admin)

@rutas_protegidas.post("/admin/usuarios/crear")
async def crear_usuario(request: Request, nombre: str = Form(...), email: str = Form(...), rol: str = Form(...)):
    print(f"🔒 Solicitud ISO 27001: Creando usuario {nombre} con rol {rol}")
    return RedirectResponse(url="/admin/usuarios?msg=creado", status_code=status.HTTP_302_FOUND)

# ==========================================
# 🔌 CONEXIÓN DEL ROUTER VIP A LA APP (DEBE IR AL FINAL DE TODO)
# ==========================================
app.include_router(rutas_protegidas)

if __name__ == "__main__":
    print("🚀 Arrancando servidor FastAPI industrial...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)