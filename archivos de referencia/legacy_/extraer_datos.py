import pandas as pd
import os

def extraer_sabanas_crudas():
    # 1. Crear la carpeta destino si no existe
    carpeta_destino = 'base_datos_interna'
    os.makedirs(carpeta_destino, exist_ok=True)
    print(f"📁 Carpeta '{carpeta_destino}' lista.")
    print("-" * 40)

    # 2. Extraer Base de Chats (Inbound)
    try:
        print("⏳ Extrayendo 'Base Chat' desde Hora hora CD diario.xlsx...")
        # Leemos solo la pestaña específica
        df_chat = pd.read_excel('Hora hora CD diario.xlsx', sheet_name='Base chat')
        ruta_chat = os.path.join(carpeta_destino, 'base_chat.csv')
        # Guardamos como CSV limpio
        df_chat.to_csv(ruta_chat, index=False, encoding='utf-8-sig')
        print("✅ ¡Sábana de Chats guardada con éxito!")
    except Exception as e:
        print(f"❌ Error extrayendo Chats: {e}")

    # 3. Extraer Base de Llamadas (Outbound Migraciones)
    try:
        print("\n⏳ Extrayendo 'Data' de Llamadas desde Corte Migraciones.xlsx...")
        df_llamadas = pd.read_excel('Corte Migraciones.xlsx', sheet_name='Data')
        ruta_llamadas = os.path.join(carpeta_destino, 'base_llamadas.csv')
        df_llamadas.to_csv(ruta_llamadas, index=False, encoding='utf-8-sig')
        print("✅ ¡Sábana de Llamadas guardada con éxito!")
    except Exception as e:
        print(f"❌ Error extrayendo Llamadas: {e}")

    # 4. Extraer Base de Encuestas NPS
    try:
        print("\n⏳ Extrayendo 'encuesta' desde Hora hora CD diario.xlsx...")
        df_nps = pd.read_excel('Hora hora CD diario.xlsx', sheet_name='encuesta')
        ruta_nps = os.path.join(carpeta_destino, 'base_encuestas.csv')
        df_nps.to_csv(ruta_nps, index=False, encoding='utf-8-sig')
        print("✅ ¡Sábana de Encuestas NPS guardada con éxito!")
    except Exception as e:
        print(f"❌ Error extrayendo Encuestas: {e}")

    print("-" * 40)
    print("🚀 PROCESO DE EXTRACCIÓN FINALIZADO.")
    print(f"Revisa la carpeta '{carpeta_destino}' para ver tus archivos .csv listos.")

if __name__ == "__main__":
    extraer_sabanas_crudas()