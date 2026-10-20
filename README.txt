# 🚀 APXGTR Analytics - Documentación y Guía de Ejecución

Este repositorio contiene el código fuente y la arquitectura completa del proyecto de grado: **"Desarrollo de un Sistema Automatizado de Monitoreo, Análisis de KPIs y Alertas Inteligentes en Tiempo Real para la Gestión Operativa de un BPO"**.

El ecosistema está diseñado bajo el patrón MLOps y Arquitectura Lambda, integrando RPA (Playwright), procesamiento de datos (Pandas), almacenamiento en la nube (Supabase/PostgreSQL), Inteligencia Artificial (Scikit-Learn) y un Dashboard Web (FastAPI + Jinja2).

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

## 🛠️ Requisitos Previos y Preparación del Entorno

Para ejecutar la simulación y ver la automatización operando "en vivo", es estrictamente necesario preparar el entorno local y limpiar la base de datos en la nube para evitar colisiones de datos históricos.

### 1. Preparación de Carpetas Locales
Antes de ejecutar el sistema, asegúrese de que las siguientes carpetas temporales estén **COMPLETAMENTE VACÍAS**:
*   `descargas_bot/`
*   `historico_procesados/`

### 2. Purga de la Base de Datos (Supabase)
El sistema emulará la operación del día **26 de Junio de 2025**. Para que la simulación funcione correctamente y la IA tenga una "pizarra limpia" para predecir, ejecute el siguiente bloque de sentencias SQL en el editor de PostgreSQL de su clúster en Supabase.

Esto vaciará las tablas de transacciones intradía y eliminará los registros históricos que colisionen con la fecha de la prueba:

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

-- Limpieza de históricos RRSS (casteo a texto por seguridad)
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

## 🏃‍♂️ Guía de Ejecución de la Simulación

La demostración del sistema requiere levantar dos servidores paralelos (el Mock de Cari AI y el Dashboard) y finalmente iniciar el Orquestador Autónomo. Se recomienda abrir **3 terminales independientes** en su editor de código (ej. VS Code).

### Paso 1: Levantar el Entorno Emulado (Mock Server)
Dado que no se tiene acceso directo al proveedor original, el bot extraerá la data de un servidor local emulado.
1. Abra la **Terminal 1**.
2. Active su entorno virtual (`venv\Scripts\activate` en Windows).
3. Navegue a la carpeta de datos internos:
   ```bash
   cd base_datos_interna
   ```
4. Inicie el servidor HTTP de Python en el puerto 8080:
   ```bash
   python -m http.server 8080
   ```
   *(Deje esta terminal corriendo en segundo plano).*

### Paso 2: Desplegar el Dashboard Web (FastAPI)
Para poder visualizar los datos a medida que el orquestador los procesa, debe encender el servidor web.
1. Abra la **Terminal 2**.
2. Active su entorno virtual.
3. Ejecute el servidor Uvicorn:
   ```bash
   python app.py
   ```
4. Abra su navegador web y diríjase a `http://localhost:8000`. Podrá visualizar el Dashboard (inicialmente en ceros, ya que las tablas acaban de ser truncadas).

### Paso 3: Iniciar la Automatización (El Orquestador)
Este es el paso final. Al ejecutar este script, el sistema cobrará vida, simulará el paso del tiempo operativo y llenará la base de datos automáticamente.
1. Abra la **Terminal 3**.
2. Active su entorno virtual.
3. Ejecute el orquestador:
   ```bash
   python bucle_maestro.py
   ```

### ⚙️ ¿Cómo funciona la simulación (Modo Tesis)?
El `bucle_maestro.py` está configurado actualmente en un modo de simulación acelerada ("Modo Tesis") para facilitar su evaluación sin tener que esperar horas reales. Su comportamiento es el siguiente:

1. **Iteración Acelerada:** En lugar de esperar 60 minutos reales entre cada corte horario, el orquestador avanza a la siguiente hora tras una **pausa de solo 5 segundos** (procesando rápidamente desde las 08:00 hasta las 17:00).
2. **Ejecución en Cadena:** Durante cada ciclo rápido, el RPA descarga los 6 reportes `.csv` del *localhost:8080*, el ETL los limpia y los sube a Supabase, y el Motor IA escanea las anomalías y genera proyecciones.
3. **Visualización en Vivo:** Si usted recarga constantemente su navegador en `localhost:8000`, verá cómo los gráficos se construyen de forma progresiva, el embudo va creciendo y las alertas de la Inteligencia Artificial comienzan a aparecer en la interfaz hora tras hora.
4. **Protocolo de Cierre y Reinicio Infinito:** Al simular la hora de las 17:00, el sistema ejecutará el "Protocolo de Cierre (EOD)", volcando los datos y perfilando a los agentes con *K-Means*. Posteriormente, el sistema entrará en un **estado de reposo de exactamente 5 minutos**. Al finalizar esos 5 minutos, el orquestador ejecutará una purga automática para limpiar la información y **volverá a iniciar la simulación desde las 08:00 am**, creando un bucle demostrativo continuo.
