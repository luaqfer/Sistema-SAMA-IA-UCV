import os
import sqlite3
import pandas as pd
from datetime import datetime  # <-- Importamos para manejar la fecha obligatoria

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ_PROYECTO = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

EXCEL_PATH = os.path.join(RAIZ_PROYECTO, 'activos.xlsx')
DB_PATH = os.path.join(RAIZ_PROYECTO, 'data', 'database', 'eam_ia_database.db')

# Diccionario traductor: Mapea el texto del Excel al ID numérico de tu BD
DICCIONARIO_CATEGORIAS = {
    "Activos Inmuebles e Infraestructura": 1,
    "Maquinaria, Equipos y Herramientas Industriales": 2,
    "Equipos Tecnológicos y de Cómputo": 3,
    "Mobiliario y Enseres de Oficina": 4,
    "Flota y Equipos de Transporte": 5
}

def obtener_id_categoria(texto_categoria):
    texto_limpio = str(texto_categoria).strip()
    return DICCIONARIO_CATEGORIAS.get(texto_limpio, 2)

def iniciar_carga_masiva():
    print("====== SAMA DIGITAL DATA SEEDER (CON FECHA DE COMPRA) ======")
    
    if not os.path.exists(EXCEL_PATH) or not os.path.exists(DB_PATH):
        print("❌ ERROR: Verifica que existan el Excel y el archivo .db")
        return

    try:
        # 1. Leer el Excel
        df_excel = pd.read_excel(EXCEL_PATH)
        print(f"📦 Total de registros detectados en Excel: {len(df_excel)}")
        
        # 2. Crear el DataFrame limpio adaptado al esquema real
        df_db = pd.DataFrame()
        
        # Generar Códigos QR secuenciales automáticos (EAM_QR_0001, EAM_QR_0002...)
        df_db['codigo_qr'] = [f"EAM_QR_{str(i).zfill(4)}" for i in range(1, len(df_excel) + 1)]
        
        # Mapear columnas directas del Excel
        df_db['nombre_activo'] = df_excel['nombre de activo']
        df_db['valor_adquisicion'] = df_excel['valor de adquisicion']
        df_db['ubicacion'] = df_excel['ubicacion']
        df_db['marca'] = df_excel['marca']
        df_db['num_serie'] = df_excel['n° serie']
        
        # Autocompletar estados por defecto
        df_db['estado_operativo'] = 'OPERATIVO'
        
        # SOLUCIÓN AL NOT NULL: Inyectamos la fecha actual en formato YYYY-MM-DD
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        df_db['fecha_compra'] = fecha_hoy
        
        # Aplicar el traductor automático para la columna de categoría
        df_db['id_categoria'] = df_excel['categoria'].apply(obtener_id_categoria)
        
        print("📋 Estructurando datos e inyectando marcas, series y fechas de compra automáticas...")

        # 3. Conexión e inserción masiva nativa mediante SQL tradicional
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔌 Insertando las 680 filas en la tabla ACTIVOS de forma atómica...")
        
        insert_query = """
            INSERT INTO ACTIVOS (codigo_qr, nombre_activo, valor_adquisicion, ubicacion, marca, num_serie, estado_operativo, fecha_compra, id_categoria)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Convertimos a tuplas ordenadas para SQL incluyendo la fecha_compra
        valores_a_insertar = list(df_db[['codigo_qr', 'nombre_activo', 'valor_adquisicion', 'ubicacion', 'marca', 'num_serie', 'estado_operativo', 'fecha_compra', 'id_categoria']].itertuples(index=False, name=None))
        
        # Ejecución masiva en bloque
        cursor.executemany(insert_query, valores_a_insertar)
        conn.commit()
        conn.close()
        
        print("\n✅ ¡MIGRACIÓN EXITOSA COMPLETADA AL 100%!")
        print(f"🚀 Se han inyectado satisfactoriamente los {len(df_db)} activos industriales a SAMA.")
        
    except Exception as e:
        print(f"\n❌ FALLO CRÍTICO EN PROCESAMIENTO: {str(e)}")

if __name__ == "__main__":
    iniciar_carga_masiva()