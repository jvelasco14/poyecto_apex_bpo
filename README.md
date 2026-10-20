# 🚀 APXGTR Analytics - Documentación y Guía de Ejecución

Este repositorio contiene el código fuente y la arquitectura completa del proyecto de grado: **"Desarrollo de un Sistema Automatizado de Monitoreo, Análisis de KPIs y Alertas Inteligentes en Tiempo Real para la Gestión Operativa de un BPO"**.

El ecosistema está diseñado bajo el patrón MLOps y Arquitectura Lambda, integrando RPA (Playwright), procesamiento de datos (Pandas), almacenamiento en la nube (Supabase/PostgreSQL), Inteligencia Artificial (Scikit-Learn) y un Dashboard Web (FastAPI + Jinja2).

💡 **NOTA IMPORTANTE SOBRE LA VISUALIZACIÓN:** 
La información del día simulado **ya se encuentra pre-cargada y lista para que la consulte directamente en la aplicación**. 
* Si desea **ver la aplicación inmediatamente** con los datos y gráficas finales, simplemente diríjase a la sección **"Guía de Ejecución"** y ejecute únicamente el **Paso 2**.
* Si desea evaluar cómo la automatización extrae, limpia y procesa los datos desde cero, siga todas las instrucciones desde el apartado "Requisitos Previos" para borrar la base de datos y ejecutar el ciclo completo.

---

## 📁 Estructura del Proyecto

El proyecto está modularizado de la siguiente manera:

*   **`bucle_maestro.py`**: El Orquestador central. Este script es el "reloj" del sistema, encargado de ejecutar la cadena completa (RPA -> ETL -> IA) de forma secuencial y cíclica.
*   **`bot_scraper.py`**: Módulo RPA (Playwright) que simula la navegación y extrae los reportes crudos (.CSV).
*   **`motor_etl.py`**: Pipeline de limpieza y gobernanza de datos. Convierte archivos crudos en registros estructurados e inyecta la data en Supabase.
*   **`motor_ia.py` (y submodelos `ia_*.py`)**: Capa de Inteligencia Artificial que ejecuta *Isolation Forest* (anomalías intradía) y *K-Means* (cierre EOD).
*   **`app.py`**: Servidor Web asíncrono (FastAPI) que expone el Dashboard.
*   **`templates/` & `templates_ia/`**: Vistas HTML del frontend construidas con Jinja2 y Bootstrap.
*   **`static/`**: Recursos estáticos (CSS, JS, imágenes).
*   **`base_datos_interna/`**: Servidor local de archivos estáticos utilizado por el entorno emulado (Mock) de Cari AI para simular descargas.
*   **`descargas_bot/`**: Zona de aterrizaje temporal (Landing Zone) donde el RPA guarda los archivos recién descargados antes de ser procesados por el ETL.
*   **`historico_procesados/`**: Repositorio local de seguridad donde el motor ETL mueve los archivos .CSV tras haberlos inyectado exitosamente en la nube.

### ⚠️ Archivos Excluidos del Flujo de Ejecución (Solo Referencia)
La carpeta **`archivos de referencia/`** NO forma parte del código ejecutable del proyecto. Contiene material documental y de contexto para la revisión de la tesis:
1.  **`ARCHIVOS APEX CONTEXTO/`**: Contiene un ejemplo de un día operativo real, mostrando los pesados archivos Excel que el analista GTR manejaba manualmente antes de esta automatización.
2.  **`legacy_/`**: Scripts obsoletos o de uso único empleados durante el desarrollo para inyecciones masivas iniciales de data histórica.
3.  **`monografia y anteproyecto/`**: Documentación académica final (Word/PDF) del proyecto de grado.

---

## 🛠️ Requisitos Previos (Para simulación desde cero)

Para ejecutar la simulación desde cero y ver la automatización operando "en vivo", es estrictamente necesario preparar el entorno local y limpiar la base de datos en la nube para evitar colisiones de datos.

### 1. Preparación de Carpetas Locales
Asegúrese de que las siguientes carpetas temporales estén **COMPLETAMENTE VACÍAS**:
*   `descargas_bot/`
*   `historico_procesados/`

### 2. Purga de la Base de Datos (Supabase)
Ejecute el siguiente bloque de sentencias SQL en el editor de PostgreSQL de su clúster en Supabase para vaciar las tablas y permitir que la simulación inicie desde cero:

```sql
-- 1. Vaciar tablas vivas (Capa Speed)
TRUNCATE TABLE public.base_llamadas_migraciones;
TRUNCATE TABLE public.base_ventas_migraciones;
TRUNCATE TABLE public.base_rete_out;
TRUNCATE TABLE public.chats_monetizacion_rrss;
TRUNCATE TABLE public.base_nps_rrss;
TRUNCATE TABLE public.base_tipificaciones_rrss;

-- 2. Limpiar históricos del día de prueba (Capa Batch)
DELETE FROM public.hist_base_llamadas_migraciones WHERE date = '2025-06-26';
DELETE FROM public.hist_base_llamadas_migraciones WHERE date = '2025-05-26';
DELETE FROM public.hist_base_ventas_migraciones WHERE fecha_de_venta = '2025-06-26';
DELETE FROM public.hist_base_rete_out WHERE date = '2025-06-26';

-- Limpieza de históricos RRSS
DELETE FROM public.hist_chats_monetizacion_rrss WHERE CAST(fecha_inicio AS TEXT) LIKE '2025-06-26%';
DELETE FROM public.hist_base_nps_rrss WHERE CAST(fecha_de_registro AS TEXT) LIKE '2025-06-26%';
DELETE FROM public.hist_base_tipificaciones_rrss WHERE CAST(fecha_de_registro AS TEXT) LIKE '2025-06-26%';

-- 3. Limpiar resultados de IA previos
DELETE FROM public.ml_insights_migraciones WHERE fecha_analisis = '2025-06-26';
DELETE FROM public.ml_insights_retenciones WHERE fecha_analisis = '2025-06-26';
DELETE FROM public.ml_insights_rrss WHERE fecha_analisis = '2025-06-26';
DELETE FROM public.ml_alertas_globales WHERE call_date = '2025-06-26';
DELETE FROM public.ml_alertas_macro WHERE call_date = '2025-06-26';
```

---

## 🏃‍♂️ Guía de Ejecución de la Aplicación

### Paso 1: Levantar el Entorno Emulado (Mock Server)
*(Solo necesario si ejecutará la simulación desde cero).*
1. Abra la **Terminal 1**.
2. Active su entorno virtual (`venv\Scripts\activate` en Windows).
3. Navegue a la carpeta de datos internos: `cd base_datos_interna`
4. Inicie el servidor HTTP de Python en el puerto 8080: `python -m http.server 8080`

### Paso 2: Desplegar el Dashboard Web (Visualización de la Aplicación)
Para poder visualizar los datos e interactuar con la aplicación.
1. Abra la **Terminal 2**.
2. Active su entorno virtual.
3. Ejecute el servidor Uvicorn: `python app.py`
4. Abra su navegador web y diríjase a **`http://localhost:8000`**. *(Si no borró la base de datos, verá la plataforma completamente funcional con los datos pre-cargados).*

### Paso 3: Iniciar la Automatización (El Orquestador)
*(Solo necesario si desea ver la simulación en vivo llenando el Dashboard desde cero).*
1. Abra la **Terminal 3**.
2. Active su entorno virtual.
3. Ejecute el orquestador: `python bucle_maestro.py`

---

### ⚙️ ¿Cómo funciona la simulación (Modo Tesis)?
El `bucle_maestro.py` está configurado actualmente en un modo de simulación acelerada ("Modo Tesis") para facilitar su evaluación:
1. **Iteración Acelerada:** En lugar de esperar 60 minutos reales entre cada corte horario, el orquestador avanza a la siguiente hora tras una **pausa de solo 5 segundos** (procesando rápidamente desde las 08:00 hasta las 17:00).
2. **Ejecución en Cadena:** Durante cada ciclo rápido, el RPA descarga los reportes, el ETL los limpia y los sube a Supabase, y el Motor IA escanea anomalías.
3. **Visualización en Vivo:** Si recarga su navegador en `localhost:8000`, verá cómo los gráficos se construyen de forma progresiva.
4. **Protocolo de Cierre y Reinicio Infinito:** Al simular las 17:00, el sistema ejecutará el "Protocolo de Cierre (EOD)", entrará en un **estado de reposo de exactamente 5 minutos**, limpiará la base de datos automáticamente y **volverá a iniciar la simulación** desde las 08:00 am, creando un bucle demostrativo continuo.
