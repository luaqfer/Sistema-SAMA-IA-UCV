import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Importamos el motor de IA desde nuestra capa de lógica de negocio (Core)
from core.ia_motor_difuso import motor_ia

# Inicializamos la aplicación FastAPI
app = FastAPI(
    title="Sistema EAM Inteligente Universal - UCV 2025",
    description="API Gateway N-Capas con Motor de Inferencia Difusa Mamdani integrado",
    version="1.0.0"
)

# ---------------------------------------------------------
# CONFIGURACIÓN CORS (VITAL PARA CONECTAR FLUTTER Y WEB)
# ---------------------------------------------------------
# Habilita que las peticiones del navegador web o del celular en la red local
# no sean bloqueadas por políticas de seguridad del sistema operativo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite cualquier origen para entorno de concurso/hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de Datos de Entrada (Pydantic para validación estricta de payloads)
class InspeccionRequest(BaseModel):
    id_activo: int
    id_usuario: int
    anomalia_operativa: float   # Escala numérica de 0 a 10 desde la Web
    integridad_estructural: float # Escala numérica de 0 a 10 desde la Web

# Función auxiliar reutilizable para conectar con SQLite
def get_db_connection():
    # Buscamos el archivo en la subcarpeta db/ según la estructura estructurada
    conn = sqlite3.connect('db/eam_ia_database.db')
    conn.row_factory = sqlite3.Row # Permite recuperar las columnas por su nombre string
    return conn

# ---------------------------------------------------------
# ENDPOINTS PRINCIPALES (CAPA DE SERVICIOS / API GATEWAY)
# ---------------------------------------------------------

@app.get("/")
def health_check():
    """Ruta raíz para verificar que el servidor local está vivo."""
    return {
        "status": "ONLINE",
        "timestamp": datetime.now().isoformat(),
        "proyecto": "EAM Platform con IA Difusa"
    }


@app.get("/api/activos")
def obtener_inventario():
    """Retorna la lista completa de activos para el Dashboard de la Plataforma Web."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT A.id_activo, A.codigo_qr, A.nombre_activo, A.valor_adquisicion, A.estado_operativo, C.nombre_categoria 
            FROM ACTIVOS A
            JOIN CATEGORIAS_ACTIVOS C ON A.id_categoria = C.id_categoria
            ORDER BY A.id_activo ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en base de datos: {str(e)}")


@app.get("/api/activos/escanear/{codigo_qr}")
def escanear_activo_qr(codigo_qr: str):
    """Endpoint para la Aplicación Móvil Flutter. Busca el activo por QR al instante."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_activo, codigo_qr, nombre_activo, estado_operativo FROM ACTIVOS WHERE codigo_qr = ?", (codigo_qr,))
        activo = cursor.fetchone()
        conn.close()

        if not activo:
            raise HTTPException(status_code=404, detail="El código QR escaneado no pertenece a ningún activo registrado.")
        
        return {
            "status": "VINCULADO_EXITOSAMENTE",
            "datos": dict(activo)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict")
def procesar_inspeccion_ia(req: InspeccionRequest):
    """
    Ruta estrella del sistema. Toma las variables de la web, inyecta el uso del Kardex,
    procesa Mamdani y ejecuta transacciones SQL autónomas según el Índice de Salud.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Validación de existencia del activo
        cursor.execute("SELECT nombre_activo, estado_operativo FROM ACTIVOS WHERE id_activo = ?", (req.id_activo,))
        activo = cursor.fetchone()
        if not activo:
            conn.close()
            raise HTTPException(status_code=404, detail="Activo no encontrado.")

        # 2. Automatización de la Frecuencia de Uso leyendo la tabla de movimientos (Kardex)
        cursor.execute("SELECT COUNT(*) FROM MOVIMIENTOS_ACTIVOS WHERE id_activo = ?", (req.id_activo,))
        total_movimientos = cursor.fetchone()[0]
        
        # Mapeamos la cantidad de usos en el Kardex a un valor numérico (0 a 10) para el motor difuso
        if total_movimientos <= 2:
            val_uso_ia = 2.0     # Equivale a Uso Bajo
            uso_etiqueta = "Bajo"
        elif total_movimientos <= 7:
            val_uso_ia = 5.5     # Equivale a Uso Medio
            uso_etiqueta = "Medio"
        else:
            val_uso_ia = 8.5     # Equivale a Uso Alto
            uso_etiqueta = "Alto"

        # 3. Invocar la Capa de Lógica de Negocio (Motor Matemático Scikit-Fuzzy)
        resultado_ia = motor_ia.procesar_diagnostico_predictivo(
            val_uso=val_uso_ia,
            val_anomalia=req.anomalia_operativa,
            val_integridad=req.integridad_estructural
        )

        indice_salud = resultado_ia["indice_salud_pct"]
        alerta_bloqueo = 1 if resultado_ia["alerta_bloqueo"] else 0
        nuevo_estado = resultado_ia["estado_recomended"] # 'INOPERATIVO_BLOQUEADO' o 'OPERATIVO'

        # 4. Orquestación Transaccional Autónoma de la Base de Datos
        # Si la IA determina peligro, cambia el estado del activo en caliente para bloquearlo
        cursor.execute("UPDATE ACTIVOS SET estado_operativo = ? WHERE id_activo = ?", (nuevo_estado, req.id_activo))

        # Guardamos el registro inmutable en el historial clínico (Auditoría)
        cursor.execute("""
            INSERT INTO HISTORIAL_INSPECCIONES_IA 
            (id_activo, id_usuario, fecha_hora_proceso, var_frecuencia_uso, var_anomalia_operativa, var_integridad_estruct, resultado_indice_salud, alerta_bloqueo_disparada)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.id_activo, 
            req.id_usuario, 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            uso_etiqueta,
            "Severa" if req.anomalia_operativa > 7 else ("Moderada" if req.anomalia_operativa > 3 else "Ninguna"),
            "Peligro" if req.integridad_estructural < 4 else ("Desgaste" if req.integridad_estructural < 8 else "Intacta"),
            indice_salud,
            alerta_bloqueo
        ))

        conn.commit()
        conn.close()

        # Retornamos el payload JSON final que leerá el frontend web para pintar el semáforo
        return {
            "id_activo": req.id_activo,
            "nombre_activo": activo["nombre_activo"],
            "indice_salud_pct": indice_salud,
            "alerta_bloqueo_disparada": bool(alerta_bloqueo),
            "estado_actualizado": nuevo_estado,
            "frecuencia_uso_detectada": uso_etiqueta,
            "mensaje": f"Inspección procesada. Estado del activo actualizado a: {nuevo_estado}."
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo crítico en el procesamiento: {str(e)}")

# Bloque de arranque de la aplicación usando Uvicorn
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)