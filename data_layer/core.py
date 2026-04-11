import os
import sys

# Permitir ejecucion directa del script agregando la raiz al PATH
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import mysql.connector
from mysql.connector import pooling
import csv
import shutil
from datetime import datetime, date, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session, run_query

try:
    from tkinter import messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False

# Importar Auditoría de Bodega para inicialización
try:
    from data_layer.warehouse_audit import crear_tablas_auditoria
except ImportError:
    def crear_tablas_auditoria(): pass

def safe_messagebox(title, message, type="error"):
    """Muestra un mensaje usando messagebox si está disponible, de lo contrario imprime en consola."""
    if HAS_TK:
        if type == "error":
            messagebox.showerror(title, message)
        elif type == "info":
            messagebox.showinfo(title, message)
        elif type == "warning":
            messagebox.showwarning(title, message)
    else:
        logger.warning(f"[{title.upper()}] {message}")


def _get_sql_types():
    """Retorna tipos SQL compatibles según el motor de BD configurado."""
    return {
        'AUTOINC':  "AUTO_INCREMENT" if DB_TYPE == 'MYSQL' else "AUTOINCREMENT",
        'LONGTEXT': "LONGTEXT"       if DB_TYPE == 'MYSQL' else "TEXT",
        'INT':      "INT"            if DB_TYPE == 'MYSQL' else "INTEGER",
    }


def _make_column_helpers(cursor):
    """
    Devuelve funciones auxiliares (check_column, add_column, add_index)
    ligadas al cursor activo. Se llaman desde las sub-funciones de init.
    """
    _cache = {}

    def _get_cols(table):
        if table in _cache:
            return _cache[table]
        if DB_TYPE == 'MYSQL':
            cursor.execute(f"SHOW COLUMNS FROM {table}")
            cols = [r[0] for r in cursor.fetchall()]
        else:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cursor.fetchall()]
        _cache[table] = cols
        return cols

    def add_col(table, column, col_type, default=None):
        try:
            if column not in _get_cols(table):
                sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                if default is not None:
                    sql += f" DEFAULT {default}"
                cursor.execute(sql)
                logger.info(f"Columna '{column}' añadida a '{table}'")
                _cache.pop(table, None)
        except Exception as e:
            logger.warning(f"add_col({table}.{column}): {e}")

    def add_idx(name, table, cols):
        """Añade un índice MySQL de forma segura e idempotente."""
        if DB_TYPE != 'MYSQL':
            return
        import re
        if not re.match(r'^[a-zA-Z0-9_,\s]+$', f"{name}{table}{cols}"):
            return
        try:
            cursor.execute(f"CREATE INDEX {name} ON {table}({cols})")
        except Exception as e:
            if "1061" not in str(e) and "Duplicate" not in str(e):
                logger.warning(f"Indice {name} en {table}: {e}")

    return add_col, add_idx


# ─────────────────────────────────────────────────────────
# ETAPA 1 — Crear tablas
# ─────────────────────────────────────────────────────────
def _crear_tablas(cursor, T):
    """Crea todas las tablas del esquema si no existen (idempotente)."""
    AUTOINC, LONGTEXT, INT = T['AUTOINC'], T['LONGTEXT'], T['INT']

    # productos
    try:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS productos (
                id {INT} {AUTOINC} PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                sku VARCHAR(50) NOT NULL,
                cantidad INTEGER NOT NULL DEFAULT 0,
                ubicacion VARCHAR(50) NOT NULL,
                minimo_stock INTEGER DEFAULT 10,
                categoria VARCHAR(100) DEFAULT 'General',
                marca VARCHAR(100) DEFAULT 'N/A',
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                secuencia_vista VARCHAR(20),
                sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
                UNIQUE (sku, ubicacion, sucursal)
            )
        """)
    except Exception:
        try:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS productos (id {INT} {AUTOINC} PRIMARY KEY, sku VARCHAR(50) NOT NULL, ubicacion VARCHAR(50) NOT NULL)")
        except Exception: pass

    # asignacion_moviles
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS asignacion_moviles (
            id {INT} {AUTOINC} PRIMARY KEY,
            sku_producto VARCHAR(50) NOT NULL,
            movil VARCHAR(100) NOT NULL,
            paquete VARCHAR(50),
            cantidad INTEGER NOT NULL DEFAULT 0,
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
            UNIQUE (sku_producto, movil, paquete, sucursal)
        )
    """)

    # movimientos
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS movimientos (
            id {INT} PRIMARY KEY {AUTOINC},
            sku_producto VARCHAR(50) NOT NULL,
            tipo_movimiento VARCHAR(50) NOT NULL,
            cantidad_afectada INTEGER NOT NULL,
            movil_afectado VARCHAR(100),
            fecha_movimiento DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_evento DATE,
            paquete_asignado VARCHAR(50),
            documento_referencia {LONGTEXT},
            observaciones {LONGTEXT},
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI'
        )
    """)

    # prestamos_activos
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS prestamos_activos (
            id {INT} PRIMARY KEY {AUTOINC},
            sku VARCHAR(50) NOT NULL,
            nombre_producto VARCHAR(255) NOT NULL,
            cantidad_prestada INTEGER NOT NULL,
            fecha_prestamo DATE NOT NULL,
            fecha_devolucion DATE,
            estado VARCHAR(20) DEFAULT 'ACTIVO',
            observaciones {LONGTEXT}
        )
    """)

    # recordatorios_pendientes
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS recordatorios_pendientes (
            id {INT} PRIMARY KEY {AUTOINC},
            movil VARCHAR(100) NOT NULL,
            paquete VARCHAR(50) NOT NULL,
            tipo_recordatorio VARCHAR(50) NOT NULL,
            fecha_recordatorio DATE NOT NULL,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            completado INTEGER DEFAULT 0,
            fecha_completado DATETIME
        )
    """)

    # configuracion
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS configuracion (
            id_config {INT} PRIMARY KEY,
            nombre_empresa VARCHAR(255),
            rut VARCHAR(50),
            direccion VARCHAR(255),
            telefono VARCHAR(50),
            email VARCHAR(100),
            logo_path {LONGTEXT}
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM configuracion")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO configuracion (id_config, nombre_empresa) VALUES (1, 'Mi Empresa')")

    # moviles
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS moviles (
            id {INT} PRIMARY KEY {AUTOINC},
            nombre VARCHAR(100) NOT NULL UNIQUE,
            patente VARCHAR(20),
            conductor VARCHAR(255),
            ayudante VARCHAR(255),
            activo INTEGER DEFAULT 1,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # consumos_pendientes
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS consumos_pendientes (
            id {INT} PRIMARY KEY {AUTOINC},
            movil VARCHAR(100) NOT NULL,
            sku VARCHAR(50) NOT NULL,
            cantidad INTEGER NOT NULL,
            tecnico_nombre VARCHAR(255),
            ayudante_nombre VARCHAR(255),
            ticket VARCHAR(255),
            colilla VARCHAR(255),
            num_contrato VARCHAR(255),
            fecha DATE,
            estado VARCHAR(20) DEFAULT 'PENDIENTE',
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI'
        )
    """)

    # tecnicos
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS tecnicos (
            id {INT} PRIMARY KEY {AUTOINC},
            nombre VARCHAR(255) NOT NULL UNIQUE,
            activo INTEGER DEFAULT 1,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # faltantes_registrados
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS faltantes_registrados (
            id {INT} PRIMARY KEY {AUTOINC},
            movil VARCHAR(100) NOT NULL,
            sku VARCHAR(50) NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha_audit DATETIME DEFAULT CURRENT_TIMESTAMP,
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
            paquete VARCHAR(100) DEFAULT 'NINGUNO',
            observaciones {LONGTEXT}
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS seriales_faltantes_detalle (
            id {INT} PRIMARY KEY {AUTOINC},
            faltante_id {INT} NOT NULL,
            serial VARCHAR(255) NOT NULL,
            FOREIGN KEY (faltante_id) REFERENCES faltantes_registrados(id)
        )
    """)

    # series_registradas
    try:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS series_registradas (
                id {INT} PRIMARY KEY {AUTOINC},
                sku VARCHAR(50) NOT NULL,
                serial_number VARCHAR(100) NOT NULL,
                mac_number VARCHAR(100),
                ubicacion VARCHAR(100) DEFAULT 'BODEGA',
                movil VARCHAR(100),
                contrato VARCHAR(255),
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
                paquete VARCHAR(50)
            )
        """)
    except Exception:
        try:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS series_registradas (id {INT} PRIMARY KEY {AUTOINC}, sku VARCHAR(50) NOT NULL, serial_number VARCHAR(100) NOT NULL)")
        except Exception: pass

    logger.info("Etapa 1 completada: tablas verificadas/creadas.")


# ─────────────────────────────────────────────────────────
# ETAPA 2 — Migraciones de columnas e índices únicos
# ─────────────────────────────────────────────────────────
def _ejecutar_migraciones(cursor, T, add_col):
    """Añade columnas faltantes y actualiza índices únicos obsoletos."""
    LONGTEXT = T['LONGTEXT']

    # productos
    add_col('productos', 'sucursal',            'VARCHAR(50)',  "'CHIRIQUI'")
    add_col('productos', 'minimo_stock',         'INTEGER',      10)
    add_col('productos', 'categoria',            'VARCHAR(100)', "'General'")
    add_col('productos', 'marca',                'VARCHAR(100)', "'N/A'")
    add_col('productos', 'secuencia_vista',      'VARCHAR(20)')
    add_col('productos', 'codigo_barra',         'VARCHAR(100)')
    add_col('productos', 'codigo_barra_maestro', 'VARCHAR(100)')
    try: run_query(cursor, "UPDATE productos SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
    except Exception: pass

    # Migrar índice único de productos (MySQL)
    if DB_TYPE == 'MYSQL':
        try:
            cursor.execute("SHOW INDEX FROM productos WHERE Key_name IN ('sku', 'sku_ubic_suc')")
            idx = cursor.fetchall()
            if idx and len(idx) < 3:
                logger.info("Migrando indice de productos para incluir sucursal...")
                for name in ('sku', 'sku_ubic_suc'):
                    try: cursor.execute(f"ALTER TABLE productos DROP INDEX {name}")
                    except Exception: pass
                cursor.execute("ALTER TABLE productos ADD UNIQUE KEY sku_ubic_suc (sku, ubicacion, sucursal)")
        except Exception: pass

    # asignacion_moviles
    add_col('asignacion_moviles', 'paquete',   'VARCHAR(50)')
    add_col('asignacion_moviles', 'sucursal',  'VARCHAR(50)', "'CHIRIQUI'")
    try: run_query(cursor, "UPDATE asignacion_moviles SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
    except Exception: pass
    if DB_TYPE == 'MYSQL':
        try:
            cursor.execute("SHOW INDEX FROM asignacion_moviles WHERE Key_name = 'sku_producto'")
            idx = cursor.fetchall()
            if idx and len(idx) < 3:
                logger.info("Migrando indice de asignacion_moviles...")
                cursor.execute("ALTER TABLE asignacion_moviles DROP INDEX sku_producto")
                cursor.execute("ALTER TABLE asignacion_moviles ADD UNIQUE KEY sku_movil_paquete_suc (sku_producto, movil, paquete, sucursal)")
        except Exception as e:
            logger.warning(f"Indice asignacion_moviles: {e}")

    # movimientos
    add_col('movimientos', 'movil_afectado',      'VARCHAR(100)')
    add_col('movimientos', 'paquete_asignado',     'VARCHAR(50)')
    add_col('movimientos', 'documento_referencia', LONGTEXT)
    add_col('movimientos', 'sucursal',             'VARCHAR(50)', "'CHIRIQUI'")
    try: run_query(cursor, "UPDATE movimientos SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
    except Exception: pass
    try: run_query(cursor, "UPDATE productos SET nombre = 'Sticker' WHERE sku = '2-7-07'")
    except Exception: pass

    # moviles
    add_col('moviles', 'ayudante', 'VARCHAR(255)')

    # consumos_pendientes
    add_col('consumos_pendientes', 'colilla',        'VARCHAR(255)')
    add_col('consumos_pendientes', 'num_contrato',   'VARCHAR(255)')
    add_col('consumos_pendientes', 'ayudante_nombre','VARCHAR(255)')
    add_col('consumos_pendientes', 'seriales_usados', LONGTEXT)
    add_col('consumos_pendientes', 'paquete',        'VARCHAR(50)', "'NINGUNO'")
    add_col('consumos_pendientes', 'sucursal',       'VARCHAR(50)', "'CHIRIQUI'")

    # series_registradas
    add_col('series_registradas', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")
    add_col('series_registradas', 'paquete',  'VARCHAR(50)')
    add_col('series_registradas', 'estado',   'VARCHAR(50)', "'DISPONIBLE'")
    try: run_query(cursor, "UPDATE series_registradas SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
    except Exception: pass
    if DB_TYPE == 'MYSQL':
        try:
            cursor.execute("SHOW CREATE TABLE series_registradas")
            create_sql = cursor.fetchone()[1]
            if 'UNIQUE KEY `serial_number` (`serial_number`)' in create_sql:
                logger.info("Migrando indice de series_registradas para incluir sucursal...")
                cursor.execute("ALTER TABLE series_registradas DROP INDEX serial_number")
                cursor.execute("ALTER TABLE series_registradas ADD UNIQUE KEY sn_sucursal (serial_number, sucursal)")
            if 'UNIQUE KEY `mac_number` (`mac_number`)' in create_sql:
                cursor.execute("ALTER TABLE series_registradas DROP INDEX mac_number")
                cursor.execute("ALTER TABLE series_registradas ADD UNIQUE KEY mac_sucursal (mac_number, sucursal)")
        except Exception: pass

    # faltantes_registrados — columna paquete
    try:
        if DB_TYPE == 'MYSQL':
            cursor.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'faltantes_registrados' AND column_name = 'paquete'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE faltantes_registrados ADD COLUMN paquete VARCHAR(100) DEFAULT 'NINGUNO'")
        else:
            cursor.execute("PRAGMA table_info(faltantes_registrados)")
            if 'paquete' not in [c[1] for c in cursor.fetchall()]:
                cursor.execute("ALTER TABLE faltantes_registrados ADD COLUMN paquete TEXT DEFAULT 'NINGUNO'")
    except Exception as e:
        logger.warning(f"Migracion faltantes_registrados.paquete: {e}")

    logger.info("Etapa 2 completada: migraciones de columnas aplicadas.")


# ─────────────────────────────────────────────────────────
# ETAPA 3 — Índices de rendimiento
# ─────────────────────────────────────────────────────────
def _actualizar_indices(cursor, add_idx):
    """Crea índices de rendimiento para las tablas de mayor consulta (No bloqueante)."""
    if DB_TYPE == 'MYSQL':
        try: 
            cursor.execute("SET SESSION wait_timeout = 60")
            cursor.execute("SET SESSION group_concat_max_len = 1000000")
        except Exception: pass

    if DB_TYPE == 'SQLITE':
        indices = [
            ("idx_productos_sku", "productos", "sku"),
            ("idx_productos_codigo_maestro", "productos", "codigo_barra_maestro"),
            ("idx_mov_sku_tipo", "movimientos", "sku_producto, tipo_movimiento"),
            ("idx_mov_fecha", "movimientos", "fecha_evento"),
            ("idx_mov_fecha_tipo", "movimientos", "fecha_evento, tipo_movimiento"),
            ("idx_asig_sku", "asignacion_moviles", "sku_producto"),
            ("idx_asig_movil", "asignacion_moviles", "movil"),
            ("idx_cons_fecha", "consumos_pendientes", "fecha"),
            ("idx_cons_estado", "consumos_pendientes", "estado"),
            ("idx_cons_movil", "consumos_pendientes", "movil"),
            ("idx_series_serial", "series_registradas", "serial_number"),
            ("idx_series_sku", "series_registradas", "sku"),
        ]
        for name, table, cols in indices:
            try: cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({cols})")
            except Exception: pass
    else:
        add_idx('idx_productos_sku',            'productos',            'sku')
        add_idx('idx_productos_codigo_maestro', 'productos',            'codigo_barra_maestro')
        add_idx('idx_mov_sku_tipo',             'movimientos',          'sku_producto, tipo_movimiento')
        add_idx('idx_mov_fecha',                'movimientos',          'fecha_evento')
        add_idx('idx_mov_fecha_tipo',           'movimientos',          'fecha_evento, tipo_movimiento')
        add_idx('idx_asig_sku',                 'asignacion_moviles',   'sku_producto')
        add_idx('idx_asig_movil',               'asignacion_moviles',   'movil')
        add_idx('idx_cons_fecha',               'consumos_pendientes',  'fecha')
        add_idx('idx_cons_estado',              'consumos_pendientes',  'estado')
        add_idx('idx_cons_movil',               'consumos_pendientes',  'movil')
        add_idx('idx_series_serial',            'series_registradas',   'serial_number')
        add_idx('idx_series_sku',               'series_registradas',   'sku')

    logger.info("Etapa 3 completada: indices de rendimiento verificados.")


# ─────────────────────────────────────────────────────────
# ETAPA 4 — Poblar móviles iniciales
# ─────────────────────────────────────────────────────────
def _poblar_moviles(cursor):
    """Asegura que todos los móviles configurados existan (Operación ligera)."""
    try:
        from config import ALL_MOVILES
        if not ALL_MOVILES: return
        if DB_TYPE == 'MYSQL':
            placeholders = ", ".join(["(%s, 1)"] * len(ALL_MOVILES))
            cursor.execute(f"INSERT IGNORE INTO moviles (nombre, activo) VALUES {placeholders}", tuple(ALL_MOVILES))
        else:
            for mv in ALL_MOVILES:
                try: run_query(cursor, "INSERT OR IGNORE INTO moviles (nombre, activo) VALUES (?, 1)", (mv,))
                except Exception: pass
        logger.info("Etapa 4 completada: moviles verificados.")
    except Exception as e:
        logger.warning(f"Etapa 4 no critica: {e}")


# ─────────────────────────────────────────────────────────
# PUNTO DE ENTRADA PÚBLICO
# ─────────────────────────────────────────────────────────
def inicializar_bd():
    """
    Orquesta la inicialización completa de la base de datos (Resiliente).
    Si ocurre un error de conexión, informa al usuario sin colgar la App.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True) if DB_TYPE == 'MYSQL' else conn.cursor()

        T = _get_sql_types()
        add_col, add_idx = _make_column_helpers(cursor)

        # Ejecución por etapas (Optimizado)
        _crear_tablas(cursor, T)
        crear_tablas_auditoria() # NUEVO: Módulo de Auditoría independiente
        _ejecutar_migraciones(cursor, T, add_col)
        
        # Etapas no críticas que pueden fallar por red lenta
        try: _actualizar_indices(cursor, add_idx)
        except Exception as e: logger.warning(f"Indices: {e}")
        
        try: _poblar_moviles(cursor)
        except Exception as e: logger.warning(f"Moviles: {e}")

        conn.commit()
        logger.info("Base de datos inicializada correctamente.")
        return True

    except Exception as e:
        engine = "MySQL" if DB_TYPE == 'MYSQL' else "SQLite"
        logger.error(f"Error critico en inicializar_bd: {e}")
        safe_messagebox("Error de Inicio", f"Error de {engine} al inicializar la base de datos:\n\n{e}\n\nVerifique su conexión.")
        return False
    finally:
        if conn:
            close_connection(conn)



def poblar_datos_iniciales():
    """Inserta los productos de la lista inicial si no existen, con stock 0, solo en BODEGA."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Primero limpiar duplicados
        # eliminados, mensaje = limpiar_productos_duplicados()
        # logger.info(f"Limpieza de duplicados: {mensaje}")
        
        # Limpiar duplicados en asignación móviles (Pesado - Movido a segundo plano o manual)
        # exito, mensaje_asignacion = limpiar_duplicados_asignacion_moviles()
        # logger.info(f"Limpieza de asignación móviles: {mensaje_asignacion}")
        
        fecha_hoy = date.today().isoformat()
        inserted_count = 0
        
        for nombre, sku, secuencia_vista in PRODUCTOS_INICIALES:
            # Asegurar que el producto exista en BODEGA para CADA sucursal configurada
            # Esto evita errores de "Producto no encontrado en BODEGA" cuando se cambia de contexto
            sucursales_a_validar = ['CHIRIQUI', 'SANTIAGO'] # Extendible según ALL_MOVILES
            
            for suc in sucursales_a_validar:
                run_query(cursor, "SELECT COUNT(*) FROM productos WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (sku, suc))
                if cursor.fetchone()[0] == 0:
                    sql_prod = "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, sucursal) VALUES (?, ?, ?, ?, ?, ?)"
                    run_query(cursor, sql_prod, (nombre, sku, 0, "BODEGA", secuencia_vista, suc))
                    
                    sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, sucursal) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    run_query(cursor, sql_mov, (sku, 'INICIAL (0)', 0, None, fecha_hoy, None, suc))
                    inserted_count += 1
                
        conn.commit()
        return inserted_count > 0
        
    except Exception as e:
        logger.error(f"Error al poblar datos iniciales: {e}")
        return False
    finally:
        if conn: close_connection(conn)

def crear_respaldo_bd(dest_path):
    """
    Crea una copia de seguridad de la base de datos en la ruta especificada.
    Punto final de seguridad.
    """
    try:
        # Asegurarse de que el origen existe
        if not os.path.exists(DATABASE_NAME):
            return False, "La base de datos original no existe."
            
        shutil.copy2(DATABASE_NAME, dest_path)
        return True, f"Respaldo creado con éxito en:\n{dest_path}"
    except Exception as e:
        return False, f"Error al crear el respaldo: {str(e)}"

def limpiar_base_datos():
    """
    Limpia todos los movimientos y datos de la base de datos, manteniendo solo la estructura.
    ADVERTENCIA: Esta operación es irreversible.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Limpiar todas las tablas de datos
        tablas_a_limpiar = [
            'movimientos',
            'asignacion_moviles',
            'consumos_pendientes',
            'recordatorios_pendientes',
            'prestamos_activos',
            'series_registradas'
        ]
        
        for tabla in tablas_a_limpiar:
            run_query(cursor, f"DELETE FROM {tabla}")
        
        # Resetear cantidades de productos a 0
        run_query(cursor, "UPDATE productos SET cantidad = 0")
        
        conn.commit()
        return True, "Base de datos limpiada exitosamente. Todos los movimientos y datos han sido eliminados."
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Error al limpiar la base de datos: {str(e)}"
    finally:
        if conn: close_connection(conn)

def obtener_configuracion():
    """Obtiene los datos de configuración de la empresa."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(dictionary=True)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
        
        run_query(cursor, "SELECT * FROM configuracion WHERE id_config = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {}
    except Exception as e:
        logger.error(f"Error al obtener configuración: {e}")
        return {}
    finally:
        if conn: close_connection(conn)

def guardar_configuracion(datos):
    """Guarda/Actualiza los datos de configuración."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql = """
            UPDATE configuracion SET 
            nombre_empresa = ?, rut = ?, direccion = ?, 
            telefono = ?, email = ?, logo_path = ?
            WHERE id_config = 1
        """
        params = (
            datos.get('nombre_empresa'), datos.get('rut'), 
            datos.get('direccion'), datos.get('telefono'), 
            datos.get('email'), datos.get('logo_path')
        )
        
        run_query(cursor, sql, params)
        conn.commit()
        return True, "Configuración guardada exitosamente."
    except Exception as e:
        return False, f"Error al guardar: {e}"
    finally:
        if conn: close_connection(conn)

def autenticar_usuario(username, password):
    """Verifica credenciales de usuario."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(dictionary=True)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT id, usuario, rol 
            FROM usuarios 
            WHERE usuario = ? AND password = ?
        """, (username, password))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error en autenticación: {e}")
        return None
    finally:
        if conn: close_connection(conn)

def crear_usuario(username, password, rol, nombre):
    """Crea un nuevo usuario."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, """
            INSERT INTO usuarios (usuario, password, rol) 
            VALUES (?, ?, ?)
        """, (username, password, rol))
        conn.commit()
        return True, f"Usuario '{username}' creado."
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return False, f"El nombre de usuario '{username}' ya existe."
        return False, f"Error: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_usuarios():
    """Obtiene lista de usuarios."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, "SELECT id, usuario, rol FROM usuarios")
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def eliminar_usuario(id_usuario):
    """Elimina un usuario por su ID."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, "DELETE FROM usuarios WHERE id = ?", (id_usuario,))
        conn.commit()
        return True, "Usuario eliminado."
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        if conn: close_connection(conn)

