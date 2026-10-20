import pandas as pd
from sqlalchemy import create_engine
import warnings

# Ignorar advertencias de formato de Excel
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

def cargar_catalogo_maestro():
    print("🏗️ Iniciando carga del Catálogo Maestro (dim_agentes) con TODA la trazabilidad...")
    
    # 1. Conexión a Supabase (Recuerda poner tu contraseña real)
    db_url = "postgresql://postgres.vdvmyueufdfviztmribf:Velasco14062000**@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    engine = create_engine(db_url)
    
    # 2. Leer la Hoja 2 del Excel
    ruta_excel = 'Corte Migraciones.xlsx'
    print(f"📖 Leyendo el archivo '{ruta_excel}'...")
    
    try:
        # Leemos toda la 'Hoja2'
        df = pd.read_excel(ruta_excel, sheet_name='Hoja2', engine='openpyxl')
        
        # 3. Limpieza y Estandarización de formato
        df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(' ', '_').str.replace('.', '', regex=False)
        
        df_maestro = df.dropna(subset=['cedula']).copy()
        df_maestro['cedula'] = df_maestro['cedula'].astype(str).str.replace('.0', '', regex=False)
        df_maestro = df_maestro.drop_duplicates(subset=['cedula'])
        
        # 4. Subir a Supabase apuntando al nuevo Schema
        esquema_destino = 'Migraciones_Inbound'
        print(f"🚀 Subiendo {len(df_maestro)} agentes al esquema '{esquema_destino}' en la nube...")
        
        # Agregamos el parámetro schema='Migraciones_Inbound'
        df_maestro.to_sql(
            name='dim_agentes', 
            con=engine, 
            schema=esquema_destino, 
            if_exists='replace', 
            index=False
        )
        
        print(f"✅ ¡Catálogo Maestro 'dim_agentes' creado exitosamente en el esquema {esquema_destino}!")
        
    except Exception as e:
        print(f"❌ Error al cargar el catálogo: {e}")

if __name__ == "__main__":
    cargar_catalogo_maestro()