-- 1. Habilitar llaves foráneas en SQLite (Obligatorio)
PRAGMA foreign_keys = ON;

-- 2. Creación de Tabla ROLES
CREATE TABLE ROLES (
    id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_rol TEXT NOT NULL UNIQUE,
    permiso_procesar_ia INTEGER NOT NULL DEFAULT 0
);

-- 3. Creación de Tabla USUARIOS
CREATE TABLE USUARIOS (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    id_rol INTEGER NOT NULL,
    nombres_completos TEXT NOT NULL,
    credencial_hash TEXT NOT NULL,
    estado_cuenta INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_rol) REFERENCES ROLES(id_rol) ON DELETE RESTRICT
);

-- 4. Creación de Tabla CATEGORIAS_ACTIVOS
CREATE TABLE CATEGORIAS_ACTIVOS (
    id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_categoria TEXT NOT NULL UNIQUE,
    tasa_depreciacion_anual REAL NOT NULL
);

-- 5. Creación de Tabla ACTIVOS
CREATE TABLE ACTIVOS (
    id_activo INTEGER PRIMARY KEY AUTOINCREMENT,
    id_categoria INTEGER NOT NULL,
    codigo_qr TEXT NOT NULL UNIQUE,
    nombre_activo TEXT NOT NULL,
    valor_adquisicion REAL NOT NULL,
    fecha_compra TEXT NOT NULL,
    estado_operativo TEXT NOT NULL DEFAULT 'OPERATIVO',
    FOREIGN KEY (id_categoria) REFERENCES CATEGORIAS_ACTIVOS(id_categoria) ON DELETE RESTRICT
);

-- 6. Creación de Tabla MOVIMIENTOS_ACTIVOS (Para inyectar Frecuencia de Uso)
CREATE TABLE MOVIMIENTOS_ACTIVOS (
    id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
    id_activo INTEGER NOT NULL,
    id_usuario INTEGER NOT NULL,
    fecha_hora_salida TEXT NOT NULL,
    fecha_hora_retorno TEXT,
    FOREIGN KEY (id_activo) REFERENCES ACTIVOS(id_activo) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES USUARIOS(id_usuario) ON DELETE RESTRICT
);

-- 7. Creación de Tabla HISTORIAL_INSPECCIONES_IA
CREATE TABLE HISTORIAL_INSPECCIONES_IA (
    id_inspeccion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_activo INTEGER NOT NULL,
    id_usuario INTEGER NOT NULL,
    fecha_hora_proceso TEXT NOT NULL,
    var_frecuencia_uso TEXT NOT NULL,
    var_anomalia_operativa TEXT NOT NULL,
    var_integridad_estruct TEXT NOT NULL,
    resultado_indice_salud REAL NOT NULL,
    alerta_bloqueo_disparada INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (id_activo) REFERENCES ACTIVOS(id_activo) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES USUARIOS(id_usuario) ON DELETE RESTRICT
);