import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import shutil

import sys
import os
# Añadimos el directorio padre (logic) al PATH para poder importar 'core'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importamos el motor de IA desde nuestra capa de lógica de negocio (Core)
from core.ia_motor_difuso import motor_ia

# Inicializamos la aplicación FastAPI
app = FastAPI(
    title="Sistema EAM Inteligente Universal - UCV 2025",
    description="API Gateway N-Capas con Motor de Inferencia Difusa Mamdani integrado",
    version="1.0.0"
)

# Servir archivos estáticos (fotos y manuales)
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app.mount("/data", StaticFiles(directory=os.path.join(base_dir, 'data')), name="data")

# ---------------------------------------------------------
# CONFIGURACIÓN CORS (VITAL PARA EL FRONTEND WEB)
# ---------------------------------------------------------
# Evita que el navegador web (Chrome, Edge) bloquee las peticiones 
# entre el archivo index.html y este servidor API por políticas de seguridad.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite cualquier origen para entorno de prueba
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de Datos de Entrada (Pydantic para validación estricta de payloads JSON)
class InspeccionRequest(BaseModel):
    id_activo: int
    id_usuario: int
    anomalia_operativa: float   # Escala numérica de 0 a 10 desde la Web
    integridad_estructural: float # Escala numérica de 0 a 10 desde la Web
    temperatura_trabajo: float
    fuga_fluidos: float

class LoginRequest(BaseModel):
    usuario: str
    pin: str

class UsuarioCreate(BaseModel):
    username: str
    pin: str
    nombres_completos: str
    dni: str
    id_rol: int

class UsuarioUpdate(BaseModel):
    username: str
    pin: str
    nombres_completos: str
    dni: str
    id_rol: int
    estado_cuenta: int

class MovimientoQRRequest(BaseModel):
    qr_activo: str
    qr_personal: str


def get_db_connection():
    """
    Establece y retorna una conexión a la base de datos SQLite.
    Se utiliza sqlite3.Row para poder acceder a las columnas por su nombre en lugar de por índice.
    """
    # Resolvemos la ruta a data dinámicamente según la nueva arquitectura
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, 'data', 'database', 'eam_ia_database.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # Permite recuperar las columnas por su nombre string
    return conn

def check_and_migrate_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN ubicacion TEXT DEFAULT 'No especificada'")
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN marca TEXT DEFAULT 'Desconocida'")
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN num_serie TEXT DEFAULT 'S/N'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Las columnas ya existen
    try:
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN foto_path TEXT")
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN manual_path TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Las columnas ya existen
    try:
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN estado_uso TEXT DEFAULT 'DISPONIBLE'")
        cursor.execute("ALTER TABLE ACTIVOS ADD COLUMN id_usuario_responsable INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Las columnas ya existen
    try:
        cursor.execute("DROP TABLE IF EXISTS MOVIMIENTOS_ACTIVOS")
        cursor.execute("""
        CREATE TABLE MOVIMIENTOS_ACTIVOS (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_activo INTEGER NOT NULL,
            fecha_movimiento TEXT NOT NULL,
            tipo_movimiento TEXT NOT NULL,
            id_usuario INTEGER
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS HISTORIAL_INSPECCIONES_IA (
            id_historial INTEGER PRIMARY KEY AUTOINCREMENT,
            id_activo INTEGER NOT NULL,
            id_usuario INTEGER NOT NULL,
            fecha_hora_proceso TEXT NOT NULL,
            var_frecuencia_uso TEXT NOT NULL,
            var_anomalia_operativa TEXT NOT NULL,
            var_integridad_estruct TEXT NOT NULL,
            resultado_indice_salud REAL NOT NULL,
            alerta_bloqueo_disparada INTEGER NOT NULL
        )""")
        
        # Adaptar ROLES y USUARIOS existentes a la lógica
        cursor.execute("INSERT OR IGNORE INTO ROLES (id_rol, nombre_rol, permiso_procesar_ia) VALUES (1, 'ADMINISTRADOR', 1)")
        cursor.execute("INSERT OR IGNORE INTO ROLES (id_rol, nombre_rol, permiso_procesar_ia) VALUES (2, 'SUPERVISOR', 1)")
        cursor.execute("INSERT OR IGNORE INTO ROLES (id_rol, nombre_rol, permiso_procesar_ia) VALUES (3, 'OPERARIO', 1)")

        try:
            cursor.execute("ALTER TABLE USUARIOS ADD COLUMN username TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE USUARIOS ADD COLUMN pin TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE USUARIOS ADD COLUMN dni TEXT")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()
            
        # Actualizar usuarios o crearlos
        cursor.execute("INSERT OR IGNORE INTO USUARIOS (id_usuario, id_rol, nombres_completos, credencial_hash, username, pin, estado_cuenta, dni) VALUES (101, 1, 'Administrador del Sistema', 'N/A', 'admin', '1234', 1, '00000001')")
        cursor.execute("INSERT OR IGNORE INTO USUARIOS (id_usuario, id_rol, nombres_completos, credencial_hash, username, pin, estado_cuenta, dni) VALUES (102, 2, 'Supervisor de Planta', 'N/A', 'super', '1234', 1, '00000002')")
        cursor.execute("INSERT OR IGNORE INTO USUARIOS (id_usuario, id_rol, nombres_completos, credencial_hash, username, pin, estado_cuenta, dni) VALUES (103, 3, 'Operario Técnico', 'N/A', 'ope', '1234', 1, '00000003')")
        
        conn.commit()
    except sqlite3.OperationalError as e:
        print("Error en base de datos:", e)
        pass
    finally:
        conn.close()

# Ejecutar migración al vuelo para garantizar que existan las nuevas columnas
check_and_migrate_db()

# ---------------------------------------------------------
# ENDPOINTS PRINCIPALES (CAPA DE SERVICIOS / API GATEWAY)
# ---------------------------------------------------------

@app.post("/api/login")
def login(request: LoginRequest):
    """
    Endpoint para autenticar a un usuario mediante su username y PIN de 4 dígitos.
    Valida en la tabla USUARIOS y retorna el perfil del usuario junto con su Rol si las credenciales son correctas.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT U.id_usuario, U.nombres_completos as nombre_usuario, U.dni, U.id_rol, R.nombre_rol as rol 
               FROM USUARIOS U 
               JOIN ROLES R ON U.id_rol = R.id_rol 
               WHERE U.username = ? AND U.pin = ? AND U.estado_cuenta = 1""",
            (request.usuario, request.pin)
        )
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            raise HTTPException(status_code=401, detail="Usuario o PIN incorrecto")
            
        return {
            "mensaje": "Login exitoso",
            "usuario": dict(user)
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/usuarios")
def obtener_usuarios():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT U.id_usuario, U.username, U.nombres_completos, U.dni, U.pin, U.id_rol, U.estado_cuenta, R.nombre_rol as rol 
            FROM USUARIOS U 
            JOIN ROLES R ON U.id_rol = R.id_rol
        """)
        usuarios = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return usuarios
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/usuarios")
def crear_usuario(user: UsuarioCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO USUARIOS (id_rol, nombres_completos, credencial_hash, username, pin, estado_cuenta, dni) VALUES (?, ?, 'N/A', ?, ?, 1, ?)",
            (user.id_rol, user.nombres_completos, user.username, user.pin, user.dni)
        )
        conn.commit()
        conn.close()
        return {"mensaje": "Usuario creado exitosamente"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El nombre de usuario o DNI ya existe.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/usuarios/{id_usuario}")
def editar_usuario(id_usuario: int, user: UsuarioUpdate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE USUARIOS SET id_rol=?, nombres_completos=?, username=?, pin=?, dni=?, estado_cuenta=? WHERE id_usuario=?",
            (user.id_rol, user.nombres_completos, user.username, user.pin, user.dni, user.estado_cuenta, id_usuario)
        )
        conn.commit()
        conn.close()
        return {"mensaje": "Usuario actualizado exitosamente"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El nombre de usuario o DNI ya existe.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/usuarios/{id_usuario}")
def eliminar_usuario(id_usuario: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM USUARIOS WHERE id_usuario=?", (id_usuario,))
        conn.commit()
        conn.close()
        return {"mensaje": "Usuario eliminado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ia/historial")
def obtener_historial_ia():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.fecha_hora_proceso, h.resultado_indice_salud, h.alerta_bloqueo_disparada, a.nombre_activo
            FROM HISTORIAL_INSPECCIONES_IA h
            JOIN ACTIVOS a ON h.id_activo = a.id_activo
            ORDER BY h.id_inspeccion DESC
            LIMIT 7
        """)
        historial = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return historial
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/activos")
def obtener_activos():
    """
    Recupera el inventario patrimonial completo de activos desde la base de datos.
    Calcula al vuelo (On-the-fly) el estado de mantenimiento preventivo basado en el Kardex (uso real),
    e inyecta el resultado del último diagnóstico de la Inteligencia Artificial.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT A.*, C.nombre_categoria, COALESCE(A.estado_uso, 'DISPONIBLE') as estado_uso, A.id_usuario_responsable 
            FROM ACTIVOS A
            LEFT JOIN CATEGORIAS_ACTIVOS C ON A.id_categoria = C.id_categoria
            ORDER BY A.id_activo ASC
        """)
        activos = [dict(row) for row in cursor.fetchall()]
        
        # Enriquecer con el nombre del usuario responsable si lo hay, y último diagnóstico IA
        for activo in activos:
            if activo['id_usuario_responsable']:
                cursor.execute("SELECT nombres_completos FROM USUARIOS WHERE id_usuario = ?", (activo['id_usuario_responsable'],))
                user = cursor.fetchone()
                activo['usuario_responsable_nombre'] = user['nombres_completos'] if user else 'Desconocido'
            else:
                activo['usuario_responsable_nombre'] = None
                
            # Obtener el último diagnóstico IA
            cursor.execute("SELECT resultado_indice_salud FROM HISTORIAL_INSPECCIONES_IA WHERE id_activo = ? ORDER BY id_inspeccion DESC LIMIT 1", (activo['id_activo'],))
            diag = cursor.fetchone()
            activo['ultimo_diagnostico_ia'] = diag['resultado_indice_salud'] if diag else None

            # Calcular "Mantenimiento Preventivo" basado en Kardex (Retiros)
            # Supongamos que cada activo requiere mantenimiento cada 30 usos (retiros)
            cursor.execute("SELECT COUNT(id_movimiento) as total_retiros FROM MOVIMIENTOS_ACTIVOS WHERE id_activo = ? AND tipo_movimiento = 'RETIRO'", (activo['id_activo'],))
            retiros_row = cursor.fetchone()
            total_retiros = retiros_row['total_retiros'] if retiros_row else 0
            usos_restantes = 30 - (total_retiros % 30)
            activo['usos_para_mantenimiento'] = usos_restantes

        conn.close()
        return activos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/movimientos/qr")
def procesar_movimiento_qr(req: MovimientoQRRequest):
    """
    Procesa un retiro o devolución de un activo escaneando su QR y el QR del responsable (DNI/ID).
    Bloquea automáticamente la transacción si la IA previamente catalogó el activo como "INOPERATIVO".
    Actualiza el Kardex (historial de movimientos) y cambia el estado de DISPONIBLE a EN USO (o viceversa).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Verificar Activo
        cursor.execute("""
            SELECT id_activo, nombre_activo, estado_operativo, COALESCE(estado_uso, 'DISPONIBLE') as estado_uso 
            FROM ACTIVOS 
            WHERE codigo_qr = ? OR CAST(id_activo as TEXT) = ? OR nombre_activo COLLATE NOCASE = ?
        """, (req.qr_activo, req.qr_activo, req.qr_activo))
        activo = cursor.fetchone()
        if not activo:
            raise HTTPException(status_code=404, detail="No se encontró ninguna máquina con ese QR, ID o Nombre.")
            
        if activo['estado_operativo'] == "INOPERATIVO (BLOQUEADO)":
            raise HTTPException(status_code=403, detail="Este activo está bloqueado por Inteligencia Artificial y requiere mantenimiento urgente.")
            
        # 2. Verificar Usuario (Personal) usando su DNI, ID o Nombre
        cursor.execute("""
            SELECT id_usuario, nombres_completos, estado_cuenta 
            FROM USUARIOS 
            WHERE dni = ? OR CAST(id_usuario as TEXT) = ? OR nombres_completos COLLATE NOCASE = ?
        """, (req.qr_personal, req.qr_personal, req.qr_personal))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="No se encontró ningún personal con ese DNI, ID o Nombre.")
        if usuario['estado_cuenta'] != 1:
            raise HTTPException(status_code=403, detail="El usuario se encuentra desactivado.")
            
        estado_actual = activo['estado_uso']
        fecha_actual = datetime.now().isoformat()
        
        # 3. Lógica de Cambio de Estado
        if estado_actual == 'DISPONIBLE':
            # RETIRO
            cursor.execute("UPDATE ACTIVOS SET estado_uso = 'EN USO', id_usuario_responsable = ? WHERE id_activo = ?", 
                           (usuario['id_usuario'], activo['id_activo']))
            cursor.execute("INSERT INTO MOVIMIENTOS_ACTIVOS (id_activo, fecha_movimiento, tipo_movimiento, id_usuario) VALUES (?, ?, ?, ?)",
                           (activo['id_activo'], fecha_actual, 'RETIRO', usuario['id_usuario']))
            mensaje = f"Activo '{activo['nombre_activo']}' retirado exitosamente por {usuario['nombres_completos']}."
            accion = "RETIRO"
        else:
            # DEVOLUCION
            cursor.execute("UPDATE ACTIVOS SET estado_uso = 'DISPONIBLE', id_usuario_responsable = NULL WHERE id_activo = ?", 
                           (activo['id_activo'],))
            cursor.execute("INSERT INTO MOVIMIENTOS_ACTIVOS (id_activo, fecha_movimiento, tipo_movimiento, id_usuario) VALUES (?, ?, ?, ?)",
                           (activo['id_activo'], fecha_actual, 'DEVOLUCION', usuario['id_usuario']))
            mensaje = f"Activo '{activo['nombre_activo']}' devuelto exitosamente por {usuario['nombres_completos']}."
            accion = "DEVOLUCION"

        conn.commit()
        conn.close()
        return {"mensaje": mensaje, "accion": accion}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/activos")
def registrar_nuevo_activo(
    codigo_qr: str = Form(...),
    nombre_activo: str = Form(...),
    id_categoria: int = Form(...),
    valor_adquisicion: float = Form(...),
    ubicacion: str = Form(...),
    marca: str = Form(...),
    num_serie: str = Form(...),
    fecha_compra: str = Form(...),
    foto: UploadFile = File(None),
    manual: UploadFile = File(None)
):
    """Registra un nuevo activo en el sistema incluyendo la subida física de foto y manual."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Guardar foto si existe
        foto_guardada = None
        if foto and foto.filename:
            fotos_dir = os.path.join(base_dir, 'data', 'assets', 'fotos')
            os.makedirs(fotos_dir, exist_ok=True)
            ext = os.path.splitext(foto.filename)[1]
            foto_filename = f"foto_{codigo_qr}{ext}"
            foto_path_abs = os.path.join(fotos_dir, foto_filename)
            with open(foto_path_abs, "wb") as buffer:
                shutil.copyfileobj(foto.file, buffer)
            foto_guardada = f"data/assets/fotos/{foto_filename}"

        # Guardar manual si existe
        manual_guardado = None
        if manual and manual.filename:
            manuales_dir = os.path.join(base_dir, 'data', 'assets', 'manuales')
            os.makedirs(manuales_dir, exist_ok=True)
            ext = os.path.splitext(manual.filename)[1]
            manual_filename = f"manual_{codigo_qr}{ext}"
            manual_path_abs = os.path.join(manuales_dir, manual_filename)
            with open(manual_path_abs, "wb") as buffer:
                shutil.copyfileobj(manual.file, buffer)
            manual_guardado = f"data/assets/manuales/{manual_filename}"

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Validar si el QR ya existe
        cursor.execute("SELECT id_activo FROM ACTIVOS WHERE codigo_qr = ?", (codigo_qr,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="El Código QR ya está registrado en otro activo.")

        cursor.execute("""
            INSERT INTO ACTIVOS (codigo_qr, nombre_activo, id_categoria, valor_adquisicion, estado_operativo, ubicacion, marca, num_serie, fecha_compra, foto_path, manual_path)
            VALUES (?, ?, ?, ?, 'OPERATIVO', ?, ?, ?, ?, ?, ?)
        """, (
            codigo_qr, 
            nombre_activo, 
            id_categoria, 
            valor_adquisicion,
            ubicacion,
            marca,
            num_serie,
            fecha_compra,
            foto_guardada,
            manual_guardado
        ))
        
        conn.commit()
        nuevo_id = cursor.lastrowid
        conn.close()
        
        return {"status": "success", "mensaje": "Activo y archivos registrados correctamente", "id_activo": nuevo_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar activo: {str(e)}")

@app.put("/api/activos/{id_activo}")
def editar_activo(
    id_activo: int,
    codigo_qr: str = Form(...),
    nombre_activo: str = Form(...),
    id_categoria: int = Form(...),
    valor_adquisicion: float = Form(...),
    ubicacion: str = Form(...),
    marca: str = Form(...),
    num_serie: str = Form(...),
    fecha_compra: str = Form(...),
    foto: UploadFile = File(None),
    manual: UploadFile = File(None)
):
    """Actualiza la información de un activo existente."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Validar si el QR ya existe en OTRO activo
        cursor.execute("SELECT id_activo FROM ACTIVOS WHERE codigo_qr = ? AND id_activo != ?", (codigo_qr, id_activo))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="El Código QR ya está registrado en otro activo.")

        # Obtener datos actuales
        cursor.execute("SELECT foto_path, manual_path FROM ACTIVOS WHERE id_activo = ?", (id_activo,))
        activo_actual = cursor.fetchone()
        if not activo_actual:
            conn.close()
            raise HTTPException(status_code=404, detail="Activo no encontrado.")

        foto_guardada = activo_actual['foto_path']
        manual_guardado = activo_actual['manual_path']

        # Actualizar foto si se envió
        if foto and foto.filename:
            fotos_dir = os.path.join(base_dir, 'data', 'assets', 'fotos')
            os.makedirs(fotos_dir, exist_ok=True)
            ext = os.path.splitext(foto.filename)[1]
            foto_filename = f"foto_{codigo_qr}{ext}"
            foto_path_abs = os.path.join(fotos_dir, foto_filename)
            with open(foto_path_abs, "wb") as buffer:
                shutil.copyfileobj(foto.file, buffer)
            foto_guardada = f"data/assets/fotos/{foto_filename}"

        # Actualizar manual si se envió
        if manual and manual.filename:
            manuales_dir = os.path.join(base_dir, 'data', 'assets', 'manuales')
            os.makedirs(manuales_dir, exist_ok=True)
            ext = os.path.splitext(manual.filename)[1]
            manual_filename = f"manual_{codigo_qr}{ext}"
            manual_path_abs = os.path.join(manuales_dir, manual_filename)
            with open(manual_path_abs, "wb") as buffer:
                shutil.copyfileobj(manual.file, buffer)
            manual_guardado = f"data/assets/manuales/{manual_filename}"

        cursor.execute("""
            UPDATE ACTIVOS SET 
                codigo_qr = ?, nombre_activo = ?, id_categoria = ?, valor_adquisicion = ?, 
                ubicacion = ?, marca = ?, num_serie = ?, fecha_compra = ?, foto_path = ?, manual_path = ?
            WHERE id_activo = ?
        """, (
            codigo_qr, nombre_activo, id_categoria, valor_adquisicion,
            ubicacion, marca, num_serie, fecha_compra, foto_guardada, manual_guardado,
            id_activo
        ))
        
        conn.commit()
        conn.close()
        return {"status": "success", "mensaje": "Activo actualizado correctamente"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar activo: {str(e)}")

@app.get("/")
def health_check():
    """Ruta raíz para verificar que el servidor local está vivo."""
    return {
        "status": "ONLINE",
        "timestamp": datetime.now().isoformat(),
        "proyecto": "EAM Platform con IA Difusa"
    }




@app.get("/api/activos/escanear/{codigo_qr}")
def escanear_activo_qr(codigo_qr: str):
    """Endpoint para escanear y buscar un activo por QR al instante."""
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


@app.get("/api/movimientos/activo/{id_activo}")
def obtener_historial_movimientos(id_activo: int):
    """
    Recupera la bitácora de movimientos físicos (Kardex) de un activo específico.
    Muestra quién retiró o devolvió el equipo y en qué fecha.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT M.fecha_movimiento, M.tipo_movimiento, U.nombres_completos 
            FROM MOVIMIENTOS_ACTIVOS M
            LEFT JOIN USUARIOS U ON M.id_usuario = U.id_usuario
            WHERE M.id_activo = ?
            ORDER BY M.id_movimiento DESC
        """, (id_activo,))
        movimientos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return movimientos
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
        cursor.execute("SELECT nombre_activo, estado_operativo, fecha_compra FROM ACTIVOS WHERE id_activo = ?", (req.id_activo,))
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

        # 2.1 Variables calculadas de BD (Edad y Fallas Previas)
        fecha_compra = activo["fecha_compra"]
        anio_compra = int(fecha_compra.split('-')[0]) if fecha_compra else 2026
        val_edad = 2026 - anio_compra

        cursor.execute("SELECT COUNT(*) FROM HISTORIAL_INSPECCIONES_IA WHERE id_activo = ? AND alerta_bloqueo_disparada = 1 AND fecha_hora_proceso >= datetime('now', '-30 days')", (req.id_activo,))
        val_fallas_previas = cursor.fetchone()[0]

        # 3. Invocar la Capa de Lógica de Negocio (Motor Matemático Scikit-Fuzzy)
        resultado_ia = motor_ia.procesar_diagnostico_predictivo(
            val_uso=val_uso_ia,
            val_anomalia=req.anomalia_operativa,
            val_integridad=req.integridad_estructural,
            val_temperatura=req.temperatura_trabajo,
            val_fugas=req.fuga_fluidos,
            val_fallas_previas=val_fallas_previas,
            val_edad=val_edad
        )

        indice_salud = resultado_ia["indice_salud_pct"]
        alerta_bloqueo = 1 if resultado_ia["alerta_bloqueo"] else 0
        nuevo_estado = resultado_ia["estado_recomendado"] # 'INOPERATIVO_BLOQUEADO' o 'OPERATIVO'

        # 4. Orquestación Transaccional Autónoma de la Base de Datos
        # Si la IA determina peligro, cambia el estado del activo en caliente para bloquearlo
        cursor.execute("UPDATE ACTIVOS SET estado_operativo = ? WHERE id_activo = ?", (nuevo_estado, req.id_activo))

        # Guardamos el registro inmutable en el historial clínico (Auditoría)
        cursor.execute("""
            INSERT INTO HISTORIAL_INSPECCIONES_IA 
            (id_activo, id_usuario, fecha_hora_proceso, var_frecuencia_uso, var_anomalia_operativa, var_integridad_estruct, resultado_indice_salud, alerta_bloqueo_disparada, num_anomalia, num_integridad, num_temperatura)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.id_activo, 
            req.id_usuario, 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            uso_etiqueta,
            "Severa" if req.anomalia_operativa > 7 else ("Moderada" if req.anomalia_operativa > 3 else "Ninguna"),
            "Peligro" if req.integridad_estructural < 4 else ("Desgaste" if req.integridad_estructural < 8 else "Intacta"),
            indice_salud,
            alerta_bloqueo,
            req.anomalia_operativa,
            req.integridad_estructural,
            req.temperatura_trabajo
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

@app.get("/api/ia/diagnostico-detalle/{id_activo}")
def obtener_diagnostico_detalle(id_activo: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT num_anomalia, num_integridad, num_temperatura, var_frecuencia_uso, resultado_indice_salud, var_anomalia_operativa, var_integridad_estruct
            FROM HISTORIAL_INSPECCIONES_IA
            WHERE id_activo = ?
            ORDER BY id_inspeccion DESC
            LIMIT 1
        """, (id_activo,))
        detalle = cursor.fetchone()
        conn.close()
        
        if not detalle:
            return None
        return dict(detalle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Bloque de arranque de la aplicación usando Uvicorn
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)