# AGENTS.md — proyecto_apex_bpo

Repo sin README, sin tests, sin lint, sin CI. Solo `requirements.txt` (desactualizado) y scripts sueltos en raíz. No asumir tooling estándar.

## Entradas reales (no confundir)

- `app.py` — App productiva **FastAPI** + Supabase, `templates_ia/`. `venv/Scripts/python app.py` → `127.0.0.1:8000`.
- `app_dashboard.py` — Mock/simulador **Flask** "Cari AI" para el RPA, `templates/`, datos en memoria desde `base_datos_interna/`. `venv/Scripts/python app_dashboard.py` → `127.0.0.1:5000`.
- `bucle_maestro.py` — Orquestador diario. Exige el Flask mock en `:5000` (`API_URL`). Flujo por hora `06→16`: `bot_scraper.run()` → `motor_etl.ejecutar_etl()`. Al final: vuelca `base_*`→`hist_*`, corre `motor_ia.py cierre`, hace `TRUNCATE` de `TABLAS_VIVAS` y borra `descargas_bot/`, `historico_procesados/`. **Destructivo: nunca correr completo sin respaldo.**
- `motor_etl.py` — `ejecutar_etl()` lee `descargas_bot/*.csv` → Supabase (`to_sql append`) → renombra a `historico_procesados/PROCESADO_<timestamp>_<archivo>` + log en `etl_auditoria`. Ejecutable solo: `venv/Scripts/python motor_etl.py`.
- `motor_ia.py` — Dispatcher: `venv/Scripts/python motor_ia.py [horario|cierre]` (default `horario`). Llama `ia_migraciones`, `ia_rrss`, `ia_retenciones`, `legacy_.ia_cddiario` (IsolationForest + KMeans).

## Setup

- Python 3.14, Windows PowerShell. Usar `venv/Scripts/python`, no `python` global. Activar con `venv/Scripts/Activate.ps1` si hace falta.
- `requirements.txt` está incompleto (solo Flask/pandas/numpy). Deps reales incluyen `fastapi, uvicorn, supabase, sqlalchemy, scikit-learn, playwright, pytz, openpyxl`. No reinstalar desde ese archivo; el `venv/` ya las tiene (`pip freeze` para verificar).
- No hay `pytest`/`ruff`/`mypy`. Verificar con `venv/Scripts/python -m py_compile <archivo.py>`.

## Scripts one-off (revisar rutas hardcodeadas antes de correr)

- `convertir_excel_a_csv.py` → lee `correcciones/` (tiene guard `__main__`).
- `cargar_historico_antiguo.py` → `correcciones/*.csv` → Supabase (tiene guard).
- `script_backfill_maestro.py` → fechas fijas `2025-06-25/26` directo a Supabase.
- `transformar_pronosticos.py` → **sin guard: corre al importar**. Lee `pronosticos_cd.xlsx` y escribe `pronosticos_rrss_listo.csv` en cwd. No importarlo; correr como script y solo si el xlsx existe.

## Datos y convenciones ETL

- `base_datos_interna/` — 8 CSV semilla `*_26062025.csv` para el mock Flask. No escribir aquí desde el ETL.
- `descargas_bot/` — inbox del bot (vacío en reposo). `historico_procesados/` — salidas `PROCESADO_*`. `plantillas_etl_vacias/*.xlsx` — plantillas, no inputs.
- `correcciones/` — fixes manuales (`csv/`, `ventas_*.csv/.xlsx`). `legacy_/` — código viejo + `apex_operaciones.db` (sqlite); prod es Supabase Postgres, ignorar ese db.
- `static/` + `templates/` pertenecen al Flask; `templates_ia/` al FastAPI. No mezclar.
- `motor_etl.normalizar_y_limpiar_datos()`: minúsculas/strip columnas, `id`→`id_original`, borra `unnamed_*`/columnas fantasma Excel/columnas-fecha, `dropna(how='all')` sin `drop_duplicates`, rellena texto con `No Registrado` y numéricos con `0`, invierte filas. Reusar esa función, no reinventar limpieza.
- CSVs mezclan `utf-8-sig` y `latin1`. Leer con fallback como hace `cargar_historico_antiguo.py`; escribir con `utf-8-sig`.

## DB / secretos

- Postgres + API Supabase con URL/keys hardcodeadas en `app.py`, `bucle_maestro.py`, `motor_etl.py`, `motor_ia.py`, `cargar_historico_antiguo.py`, `script_backfill_maestro.py`. No commitear nuevas credenciales ni imprimirlas en logs. Tablas vivas `base_*` vs históricas `hist_*`; vistas `vw_*`, alertas `ml_*`.
- `bot_scraper.py` usa Playwright `headless=False` contra `:5000` con credenciales de prueba hardcodeadas. No corre headless/CI sin rework.
