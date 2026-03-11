import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
import csv
import shutil
from datetime import datetime, date, timedelta

# Logging y Validación
from utils.logger import get_logger
from utils.validators import (
    validate_sku, validate_quantity, validate_date, 
    validate_movil, validate_tipo_movimiento, 
    validate_observaciones, ValidationError
)

logger = get_logger(__name__)

try:
    from tkinter import messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False

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
from config import (
    DATABASE_NAME,
    DB_TYPE,
    MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT,
    MOVILES_DISPONIBLES,
    MOVILES_SANTIAGO,
    UBICACION_DESCARTE,
    TIPO_MOVIMIENTO_DESCARTE,
    TIPOS_CONSUMO,
    TIPOS_ABASTO,
    PAQUETES_MATERIALES,
    PRODUCTOS_INICIALES,
    MATERIALES_COMPARTIDOS
)

# =================================================================
# CONFIGURACIÓN DE CONEXIÓN (PUNTO 3)
# =================================================================

# Importar nueva gestión de conexiones
from utils.db_connector import get_db_connection, close_connection, db_session



def run_query(cursor, query, params=None):
    """
    Ejecuta una consulta ajustando la sintaxis según el motor de DB.
    Convierte '?' a '%s' si el motor es MySQL.
    Registra errores de consulta.
    """
    if DB_TYPE == 'MYSQL':
        # Reemplazo básico de placeholder para MySQL
        query = query.replace('?', '%s')
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.rowcount
    except Exception as e:
        logger.error(f"❌ Error SQL ejecución: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise e

# =================================================================
# 2. FUNCIONES DE BASE DE DATOS (CRUD y Movimientos) - CORREGIDAS
# =================================================================

def inicializar_bd():
    """Crea la BD y las tablas necesarias. Compatible con SQLite y MySQL."""
    conn = None
    try:
        conn = get_db_connection()
        # Usar cursores con buffer para MySQL por defecto
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Auxiliares para compatibilidad
        AUTOINC = "AUTO_INCREMENT" if DB_TYPE == 'MYSQL' else "AUTOINCREMENT"
        TEXT_TYPE = "VARCHAR(255)" if DB_TYPE == 'MYSQL' else "TEXT"
        LONGTEXT = "LONGTEXT" if DB_TYPE == 'MYSQL' else "TEXT"
        INT_TYPE = "INT" if DB_TYPE == 'MYSQL' else "INTEGER"
        
        # Cache de columnas para optimizar velocidad en MySQL (Punto 3 - Latencia)
        table_columns_cache = {}

        def get_all_columns(table):
            if table in table_columns_cache:
                return table_columns_cache[table]
            
            if DB_TYPE == 'MYSQL':
                cursor.execute(f"SHOW COLUMNS FROM {table}")
                cols = [row[0] for row in cursor.fetchall()]
            else:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in cursor.fetchall()]
            
            table_columns_cache[table] = cols
            return cols

        def check_column_exists(table, column):
            try:
                columns = get_all_columns(table)
                return column in columns
            except Exception as e:
                logger.warning(f"⚠️ Error verificando columna {column} en tabla {table}: {e}")
                return False

        def add_column_if_missing(table, column, type, default=None):
            if not check_column_exists(table, column):
                alter_query = f"ALTER TABLE {table} ADD COLUMN {column} {type}"
                if default is not None:
                    alter_query += f" DEFAULT {default}"
                cursor.execute(alter_query)
                logger.info(f"🆕 Columna {column} añadida a {table}")
                # Limpiar cache para forzar recarga si se añade otra
                if table in table_columns_cache:
                    del table_columns_cache[table]

        # 1. TABLA PRODUCTOS
        q_prod = f"""
            CREATE TABLE IF NOT EXISTS productos (
                id {INT_TYPE} {AUTOINC} PRIMARY KEY,
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
        """
        try:
            cursor.execute(q_prod)
        except Exception as e:
            # Si falla (posiblemente por UNIQUE con columna inexistente), intentamos crearla básica
            logger.info("🔧 Re-intentando creación de tabla productos...")
            try:
                cursor.execute(f"CREATE TABLE IF NOT EXISTS productos (id {INT_TYPE} {AUTOINC} PRIMARY KEY, sku VARCHAR(50) NOT NULL, ubicacion VARCHAR(50) NOT NULL)")
            except: pass
        
        # Primero añadimos la columna para que el resto sea posible
        add_column_if_missing('productos', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")
        add_column_if_missing('productos', 'minimo_stock', 'INTEGER', 10)
        add_column_if_missing('productos', 'categoria', 'VARCHAR(100)', "'General'")
        add_column_if_missing('productos', 'marca', 'VARCHAR(100)', "'N/A'")
        add_column_if_missing('productos', 'secuencia_vista', 'VARCHAR(20)')
        add_column_if_missing('productos', 'codigo_barra', 'VARCHAR(100)') # Código de barra individual (equipos)
        add_column_if_missing('productos', 'codigo_barra_maestro', 'VARCHAR(100)') # Código de barra maestro (SKU)
        add_column_if_missing('productos', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")
        
        # MIGRACIÓN: Asegurar que filas existentes tengan sucursal
        try:
            run_query(cursor, "UPDATE productos SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
        except: pass

        # MIGRACIÓN: Corregir UNIQUE KEY en productos (MySQL)
        if DB_TYPE == 'MYSQL':
            try:
                # Comprobar si el índice existe bajo el nombre 'sku' o 'sku_ubic_suc'
                cursor.execute("SHOW INDEX FROM productos WHERE Key_name IN ('sku', 'sku_ubic_suc')")
                idx_data = cursor.fetchall()
                # Si es el antiguo (2 columnas) o no tiene el formato correcto
                if idx_data and len(idx_data) < 3: 
                     logger.info("🔧 Migrando índice de productos para incluir sucursal...")
                     try: cursor.execute("ALTER TABLE productos DROP INDEX sku")
                     except: pass
                     try: cursor.execute("ALTER TABLE productos DROP INDEX sku_ubic_suc")
                     except: pass
                     cursor.execute("ALTER TABLE productos ADD UNIQUE KEY sku_ubic_suc (sku, ubicacion, sucursal)")
            except: pass
        
        # 2. TABLA ASIGNACION_MOVILES
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS asignacion_moviles (
                id {INT_TYPE} {AUTOINC} PRIMARY KEY,
                sku_producto VARCHAR(50) NOT NULL,
                movil VARCHAR(100) NOT NULL,
                paquete VARCHAR(50),
                cantidad INTEGER NOT NULL DEFAULT 0,
                sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
                UNIQUE (sku_producto, movil, paquete, sucursal)
            )
        """)
        add_column_if_missing('asignacion_moviles', 'paquete', 'VARCHAR(50)')
        add_column_if_missing('asignacion_moviles', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")
        
        # MIGRACIÓN: Asegurar que filas existentes tengan sucursal
        try:
            run_query(cursor, "UPDATE asignacion_moviles SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
        except: pass

        # --- MIGRACIÓN: Corregir Índice Único en asignacion_moviles (MySQL) ---
        if DB_TYPE == 'MYSQL':
            try:
                # Comprobar si existe el índice antiguo restrictivo
                cursor.execute("SHOW INDEX FROM asignacion_moviles WHERE Key_name = 'sku_producto'")
                idx_data = cursor.fetchall()
                if idx_data and len(idx_data) < 3:
                     logger.info("🔧 Migrando índice de asignacion_moviles para soportar múltiples paquetes...")
                     cursor.execute("ALTER TABLE asignacion_moviles DROP INDEX sku_producto")
                     cursor.execute("ALTER TABLE asignacion_moviles ADD UNIQUE KEY sku_movil_paquete_suc (sku_producto, movil, paquete, sucursal)")
                     logger.info("✅ Índice migrado exitosamente (con sucursal).")
            except Exception as e:
                logger.warning(f"⚠️ Error en migración de índice asignacion_moviles: {e}")
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS movimientos (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
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
        add_column_if_missing('movimientos', 'movil_afectado', 'VARCHAR(100)')
        add_column_if_missing('movimientos', 'paquete_asignado', 'VARCHAR(50)')
        add_column_if_missing('movimientos', 'documento_referencia', LONGTEXT)
        add_column_if_missing('movimientos', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'") # Nueva: Para aislamiento
        
        # MIGRACIÓN: Asegurar que filas existentes tengan sucursal
        try:
            run_query(cursor, "UPDATE movimientos SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")
        except: pass
        
        # 4. TABLA PRESTAMOS
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS prestamos_activos (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
                sku VARCHAR(50) NOT NULL,
                nombre_producto VARCHAR(255) NOT NULL,
                cantidad_prestada INTEGER NOT NULL,
                fecha_prestamo DATE NOT NULL,
                fecha_devolucion DATE,
                estado VARCHAR(20) DEFAULT 'ACTIVO',
                observaciones {LONGTEXT}
            )
        """)
        
        # 5. TABLA RECORDATORIOS
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS recordatorios_pendientes (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
                movil VARCHAR(100) NOT NULL,
                paquete VARCHAR(50) NOT NULL,
                tipo_recordatorio VARCHAR(50) NOT NULL,
                fecha_recordatorio DATE NOT NULL,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                completado INTEGER DEFAULT 0,
                fecha_completado DATETIME
            )
        """)
        
        # 6. TABLA CONFIGURACION
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS configuracion (
                id_config {INT_TYPE} PRIMARY KEY,
                nombre_empresa VARCHAR(255),
                rut VARCHAR(50),
                direccion VARCHAR(255),
                telefono VARCHAR(50),
                email VARCHAR(100),
                logo_path {LONGTEXT}
            )
        """)
        
        # Inicializar configuración si está vacía
        cursor.execute("SELECT COUNT(*) FROM configuracion")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO configuracion (id_config, nombre_empresa) VALUES (1, 'Mi Empresa')")
            logger.info("⚙️ Configuración inicial creada.")
        
        # 7. TABLA MOVILES
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS moviles (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
                nombre VARCHAR(100) NOT NULL UNIQUE,
                patente VARCHAR(20),
                conductor VARCHAR(255),
                ayudante VARCHAR(255),
                activo INTEGER DEFAULT 1,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        add_column_if_missing('moviles', 'ayudante', 'VARCHAR(255)')
        
        # 9. TABLA CONSUMOS PENDIENTES (Portal Móvil)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS consumos_pendientes (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
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
        add_column_if_missing('consumos_pendientes', 'colilla', 'VARCHAR(255)')
        add_column_if_missing('consumos_pendientes', 'num_contrato', 'VARCHAR(255)')
        add_column_if_missing('consumos_pendientes', 'ayudante_nombre', 'VARCHAR(255)')
        add_column_if_missing('consumos_pendientes', 'seriales_usados', LONGTEXT)
        add_column_if_missing('consumos_pendientes', 'paquete', 'VARCHAR(50)', "'NINGUNO'")
        add_column_if_missing('consumos_pendientes', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")

        # Helper para añadir índices en MySQL (Defensivo)
        def add_mysql_index(name, table, cols):
            """Añade un índice MySQL de forma segura."""
            if DB_TYPE != 'MYSQL': 
                return  # Skip if not MySQL
            
            # Validar que los nombres solo contengan caracteres alfanuméricos y guiones bajos
            import re
            if not re.match(r'^[a-zA-Z0-9_,\s]+$', f"{name}{table}{cols}"):
                logger.warning(f"⚠️ Nombres de índice/tabla/columnas contienen caracteres no válidos")
                return
            
            try:
                cursor.execute(f"CREATE INDEX {name} ON {table}({cols})")
            except Exception as e:
                # Ignorar si ya existe o hay error de duplicado
                if "1061" in str(e) or "Duplicate" in str(e): 
                    pass
                else:
                    logger.warning(f"⚠️ No se pudo crear índice {name} en {table}: {e}")

        q_series = f"""
            CREATE TABLE IF NOT EXISTS series_registradas (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
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
        """
        try:
            cursor.execute(q_series)
        except Exception as e:
            logger.info("🔧 Re-intentando creación de tabla series_registradas...")
            try:
                cursor.execute(f"CREATE TABLE IF NOT EXISTS series_registradas (id {INT_TYPE} PRIMARY KEY {AUTOINC}, sku VARCHAR(50) NOT NULL, serial_number VARCHAR(100) NOT NULL)")
            except: pass

        add_column_if_missing('series_registradas', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")
        add_column_if_missing('series_registradas', 'paquete', 'VARCHAR(50)')
        add_column_if_missing('series_registradas', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'")
        run_query(cursor, "UPDATE series_registradas SET sucursal = 'CHIRIQUI' WHERE sucursal IS NULL")

        # MIGRACIÓN: Corregir UNIQUE KEY en series_registradas (MySQL)
        if DB_TYPE == 'MYSQL':
            try:
                # El serial_number antiguo era UNIQUE globalmente. Ahora debe ser por sucursal.
                cursor.execute("SHOW CREATE TABLE series_registradas")
                create_sql = cursor.fetchone()[1]
                if 'UNIQUE KEY `serial_number` (`serial_number`)' in create_sql:
                     logger.info("🔧 Migrando índice de series_registradas para incluir sucursal...")
                     cursor.execute("ALTER TABLE series_registradas DROP INDEX serial_number")
                     cursor.execute("ALTER TABLE series_registradas ADD UNIQUE KEY sn_sucursal (serial_number, sucursal)")
                
                if 'UNIQUE KEY `mac_number` (`mac_number`)' in create_sql:
                     cursor.execute("ALTER TABLE series_registradas DROP INDEX mac_number")
                     cursor.execute("ALTER TABLE series_registradas ADD UNIQUE KEY mac_sucursal (mac_number, sucursal)")
            except: pass
        add_column_if_missing('series_registradas', 'sucursal', 'VARCHAR(50)', "'CHIRIQUI'") # Aislamiento
        
        # MySQL Session: Aumentar límite de GROUP_CONCAT para evitar truncamiento de series (61 -> ilimitado)
        if DB_TYPE == 'MYSQL':
            try:
                cursor.execute("SET SESSION group_concat_max_len = 1000000")
            except: pass
        add_mysql_index('idx_series_serial', 'series_registradas', 'serial_number')
        add_mysql_index('idx_series_sku', 'series_registradas', 'sku')

        # INDICES GLOBALES
        if DB_TYPE == 'SQLITE':
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_codigo_maestro ON productos(codigo_barra_maestro)")  # NUEVO
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mov_sku_tipo ON movimientos(sku_producto, tipo_movimiento)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mov_fecha ON movimientos(fecha_evento)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mov_fecha_tipo ON movimientos(fecha_evento, tipo_movimiento)")  # NUEVO: índice compuesto
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_asig_sku ON asignacion_moviles(sku_producto)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_asig_movil ON asignacion_moviles(movil)")  # NUEVO: para filtros por móvil
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cons_fecha ON consumos_pendientes(fecha)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cons_estado ON consumos_pendientes(estado)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cons_movil ON consumos_pendientes(movil)")  # NUEVO: para filtros por móvil
        else:
            add_mysql_index('idx_productos_sku', 'productos', 'sku')
            add_mysql_index('idx_productos_codigo_maestro', 'productos', 'codigo_barra_maestro')  # NUEVO
            add_mysql_index('idx_mov_sku_tipo', 'movimientos', 'sku_producto, tipo_movimiento')
            add_mysql_index('idx_mov_fecha', 'movimientos', 'fecha_evento')
            add_mysql_index('idx_mov_fecha_tipo', 'movimientos', 'fecha_evento, tipo_movimiento')  # NUEVO: índice compuesto
            add_mysql_index('idx_asig_sku', 'asignacion_moviles', 'sku_producto')
            add_mysql_index('idx_asig_movil', 'asignacion_moviles', 'movil')  # NUEVO: para filtros por móvil
            add_mysql_index('idx_cons_fecha', 'consumos_pendientes', 'fecha')
            add_mysql_index('idx_cons_estado', 'consumos_pendientes', 'estado')
            add_mysql_index('idx_cons_movil', 'consumos_pendientes', 'movil')  # NUEVO: para filtros por móvil


        # MIGRACIÓN AUTOMÁTICA DE MÓVILES (Asegurar que todos existan)
        from config import ALL_MOVILES
        logger.info(f"⚙️ Verificando {len(ALL_MOVILES)} móviles...")
        
        if DB_TYPE == 'MYSQL':
            # Preparar valores para inserción masiva
            # MySQL: INSERT IGNORE INTO ... VALUES (%s, 1), (%s, 1), ...
            placeholders = ", ".join(["(%s, 1)"] * len(ALL_MOVILES))
            query = f"INSERT IGNORE INTO moviles (nombre, activo) VALUES {placeholders}"
            try:
                # Usar un timeout específico si es soportado, o confiar en el global
                cursor.execute(query, tuple(ALL_MOVILES))
                logger.info("✅ Migración de móviles completada.")
            except Exception as e:
                logger.warning(f"⚠️ Error en migración masiva MySQL: {e}")
                # Fallback uno a uno si la masiva falla o es lenta (opcional)
        else:
            # SQLite: INSERT OR IGNORE
            for mv in ALL_MOVILES:
                try:
                    run_query(cursor, "INSERT OR IGNORE INTO moviles (nombre, activo) VALUES (?, 1)", (mv,))
                except: pass

        conn.commit()
        return True
        
    except Exception as e:
        engine = "MySQL" if DB_TYPE == 'MYSQL' else "SQLite"
        safe_messagebox("Error Crítico", f"❌ Error de {engine} al inicializar la base de datos:\n\n{e}")
        sys.exit(1)
    finally:
        if conn: close_connection(conn)

def diagnosticar_duplicados_movil(movil):
    """Diagnóstico: Identifica duplicados exactos en asignacion_moviles"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT movil, sku_producto, COUNT(*) as count, SUM(cantidad) as total
            FROM asignacion_moviles 
            WHERE movil = ?
            GROUP BY movil, sku_producto
            HAVING COUNT(*) > 1
        """, (movil,))
        
        duplicados = cursor.fetchall()
        return duplicados
        
    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def limpiar_productos_duplicados():
    """Elimina productos duplicados manteniendo el registro más reciente"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Encontrar SKUs duplicados en BODEGA
        run_query(cursor, """
            SELECT sku, COUNT(*) as count 
            FROM productos 
            WHERE ubicacion = 'BODEGA'
            GROUP BY sku 
            HAVING COUNT(*) > 1
        """)
        
        duplicados = cursor.fetchall()
        
        if not duplicados:
            return 0, "No se encontraron productos duplicados"
        
        eliminados = 0
        for sku, count in duplicados:
            # Mantener el registro más reciente y eliminar los demás
            run_query(cursor, """
                DELETE FROM productos 
                WHERE sku = ? AND ubicacion = 'BODEGA'
                AND id NOT IN (
                    SELECT id FROM productos 
                    WHERE sku = ? AND ubicacion = 'BODEGA' 
                    ORDER BY fecha_creacion DESC 
                    LIMIT 1
                )
            """, (sku, sku))
            eliminados += cursor.rowcount
        
        conn.commit()
        return eliminados, f"Se eliminaron {eliminados} registros duplicados"
        
    except Exception as e:
        return 0, f"Error al limpiar duplicados: {e}"
    finally:
        if conn: close_connection(conn)

def limpiar_duplicados_asignacion_moviles():
    """Limpia registros duplicados en la tabla asignacion_moviles y consolida cantidades - CORREGIDA"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Diagnosticar duplicados primero
        run_query(cursor, """
            SELECT movil, sku_producto, COUNT(*) as count, SUM(cantidad) as total
            FROM asignacion_moviles 
            GROUP BY movil, sku_producto
            HAVING COUNT(*) > 1
        """)
        duplicados = cursor.fetchall()
        
        if not duplicados:
            return True, "No se encontraron duplicados en asignación móviles"
        
        logger.info(f"Encontrados {len(duplicados)} SKUs duplicados en asignación móviles")
        
        # Crear tabla temporal con datos consolidados
        run_query(cursor, """
            CREATE TEMPORARY TABLE temp_asignacion AS
            SELECT movil, sku_producto, SUM(cantidad) as cantidad_total
            FROM asignacion_moviles 
            GROUP BY movil, sku_producto
        """)
        
        # Eliminar todos los registros originales
        run_query(cursor, "DELETE FROM asignacion_moviles")
        
        # Reinsertar datos consolidados
        run_query(cursor, """
            INSERT INTO asignacion_moviles (movil, sku_producto, cantidad)
            SELECT movil, sku_producto, cantidad_total 
            FROM temp_asignacion 
            WHERE cantidad_total > 0
        """)
        
        # Eliminar tabla temporal
        run_query(cursor, "DROP TABLE temp_asignacion")
        
        conn.commit()
        return True, f"Duplicados en asignación móviles limpiados exitosamente. {len(duplicados)} registros consolidados."
        
    except Exception as e:
        return False, f"Error al limpiar duplicados de asignación: {e}"
    finally:
        if conn: close_connection(conn)

def verificar_y_corregir_duplicados_completo(silent=False):
    """Realiza una limpieza completa de duplicados en todas las tablas."""
    if not silent: logger.info("🔍 Iniciando verificación y corrección de duplicados...")
    
    # 1. Limpiar duplicados en productos
    eliminados_prod, mensaje_prod = limpiar_productos_duplicados()
    if not silent: logger.info(f"📦 Productos: {mensaje_prod}")
    
    # 2. Limpiar duplicados en asignacion_moviles
    # Solo limpiamos esto SI detectamos que hay duplicados para evitar re-escritura total lenta
    conn = get_db_connection()
    if DB_TYPE == 'MYSQL':
        cursor = conn.cursor(buffered=True)
    else:
        cursor = conn.cursor()
    run_query(cursor, "SELECT COUNT(*) FROM (SELECT 1 FROM asignacion_moviles GROUP BY movil, sku_producto HAVING COUNT(*) > 1) as sub")
    tiene_duplicados = cursor.fetchone()[0] > 0
    conn.close()

    if tiene_duplicados:
        _, mensaje_asign = limpiar_duplicados_asignacion_moviles()
        if not silent: logger.info(f"🚚 Asignación Móviles: {mensaje_asign}")
    elif not silent:
        logger.info("🚚 Asignación Móviles: No se encontraron duplicados.")
    
    if not silent: logger.info("✅ Verificación completada.")
    return True

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
            run_query(cursor, "SELECT COUNT(*) FROM productos WHERE sku = ? AND ubicacion = 'BODEGA'", (sku,))
            if cursor.fetchone()[0] == 0:
                sql_prod = "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista) VALUES (?, ?, ?, ?, ?)"
                run_query(cursor, sql_prod, (nombre, sku, 0, "BODEGA", secuencia_vista))
                
                sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado) VALUES (?, ?, ?, ?, ?, ?)"
                run_query(cursor, sql_mov, (sku, 'INICIAL (0)', 0, None, fecha_hoy, None))
                inserted_count += 1
                
        conn.commit()
        return inserted_count > 0
        
    except Exception as e:
        logger.error(f"Error al poblar datos iniciales: {e}")
        return False
    finally:
        if conn: close_connection(conn)

def anadir_producto(nombre, sku, cantidad, ubicacion, secuencia_vista, minimo_stock=10, categoria='General', marca='N/A', fecha_evento=None):
    """Inserta un nuevo producto con datos enriquecidos."""
    conn = None
    try:
        # Validación
        try:
            sku = validate_sku(sku)
            cantidad = validate_quantity(cantidad, allow_zero=True, allow_negative=False)
            from utils.validators import sanitize_string
            nombre = sanitize_string(nombre)
        except ValidationError as ve:
             return False, f"Datos inválidos: {ve}"

        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        if not fecha_evento: fecha_evento = date.today().isoformat()
        
        sql = """
            INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, minimo_stock, categoria, marca) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        run_query(cursor, sql, (nombre, sku, cantidad, ubicacion, secuencia_vista, minimo_stock, categoria, marca))
        
        sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado) VALUES (?, ?, ?, ?, ?, ?)"
        run_query(cursor, sql_mov, (sku, 'ENTRADA (Inicial)', cantidad, None, fecha_evento, None))
        
        conn.commit()
        return True, f"Producto '{nombre}' (SKU: {sku}) añadido exitosamente en {ubicacion}."
        
    except sqlite3.IntegrityError:
        return False, f"Error: El SKU '{sku}' ya existe en la ubicación '{ubicacion}'. Verifique la ubicación y la Secuencia de Vista."
    except Exception as e:
        return False, f"Ocurrió un error al insertar: {e}"
    finally:
        if conn: close_connection(conn)

def verificar_stock_disponible(sku, cantidad_requerida, ubicacion='BODEGA'):
    """
    Verifica si hay material suficiente en una ubicación.
    Retorna (boolean, stock_actual)
    Nota: Deja propagar excepciones de BD para manejo superior.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, "SELECT cantidad FROM productos WHERE sku = ? AND ubicacion = ?", (sku, ubicacion))
        res = cursor.fetchone()
        
        if not res:
            return False, 0
            
        stock_actual = res[0]
        return stock_actual >= cantidad_requerida, stock_actual
        
    finally:
        if conn: close_connection(conn)

def registrar_movimiento_gui(sku, tipo_movimiento, cantidad_afectada, movil_afectado=None, fecha_evento=None, paquete_asignado=None, observaciones=None, documento_referencia=None, target_db_name=None, existing_conn=None, sucursal_context=None, seriales=None):
    """
    Registra un movimiento, actualiza la cantidad en Bodega/Asignación y maneja la ubicación DESCARTE.
    """
    conn = None
    should_close = True
    try:
        # Validación de entrada
        try:
            sku = validate_sku(sku)
            cantidad_afectada = validate_quantity(cantidad_afectada, allow_zero=False, allow_negative=False)
            if movil_afectado:
                 # Aceptar SANTIAGO como destino especial además de las móviles del contexto
                 if movil_afectado.upper() == 'SANTIAGO':
                     movil_afectado = 'SANTIAGO'
                 else:
                     from config import CURRENT_CONTEXT
                     movil_afectado = validate_movil(movil_afectado, CURRENT_CONTEXT['MOVILES'])
            
            if observaciones:
                observaciones = validate_observaciones(observaciones)
            
            # Formatear seriales para observaciones si se proveen
            if seriales:
                seriales_str = ", ".join(seriales)
                if observaciones:
                    observaciones = f"{observaciones} | Series: {seriales_str}"
                else:
                    observaciones = f"Series: {seriales_str}"
                
        except ValidationError as ve:
            logger.warning(f"Intento de movimiento inválido: {ve}")
            return False, f"Datos inválidos: {ve}"

        if existing_conn:
            conn = existing_conn
            should_close = False
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
                cursor = conn.cursor()
        else:
            conn = get_db_connection(target_db=target_db_name)
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
                cursor = conn.cursor()
        
        if not fecha_evento: 
             return False, "Error de Fecha: La fecha del evento es obligatoria."
        
        if paquete_asignado in ("NINGUNO", "PERSONALIZADO"):
             # Para efectos de la tabla asignacion_moviles, tratamos PERSONALIZADO como una entrada específica
             # pero validamos que no se convierta en None si el usuario quiere trackearlo aparte.
             # Si es NINGUNO, lo normalizamos a None para COALESCE(paquete, 'NINGUNO')
             if paquete_asignado == "NINGUNO":
                 paquete_asignado = None
        
        # SUCURSAL CONTEXTO INTELIGENTE
        from config import MOVILES_SANTIAGO
        sucursal = sucursal_context
        if not sucursal:
            if movil_afectado and movil_afectado in MOVILES_SANTIAGO:
                sucursal = 'SANTIAGO'
            elif movil_afectado:
                sucursal = 'CHIRIQUI'
            else:
                import os
                sucursal = 'SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI'

        paquete_para_stock = paquete_asignado # El que usaremos para descontar de asignacion_moviles
        
        run_query(cursor, "SELECT cantidad, nombre, secuencia_vista FROM productos WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (sku, sucursal))
        resultado_bodega = cursor.fetchone()
        
        if not resultado_bodega:
            if tipo_movimiento not in ('ENTRADA', 'ABASTO'):
                return False, f"Producto con SKU '{sku}' no encontrado en BODEGA o no existe una entrada de inventario válida."
            else:
                stock_bodega_actual = 0
                temp_data = next(((n, s) for n, current_sku, s in PRODUCTOS_INICIALES if current_sku == sku), (f"Producto temporal {sku}", '999'))
                nombre_producto, secuencia_vista = temp_data
        else:
            stock_bodega_actual, nombre_producto, secuencia_vista = resultado_bodega
        
        stock_asignado = 0
        if movil_afectado and tipo_movimiento in ('SALIDA_MOVIL', 'RETORNO_MOVIL', 'CONSUMO_MOVIL'):
             # Para CONSUMO_MOVIL y RETORNO_MOVIL (Auditoría): buscar stock TOTAL en el móvil
             # si no se especifica un paquete O SI EL MATERIAL ES COMPARTIDO (debe verse en todo el móvil)
             is_shared = sku in MATERIALES_COMPARTIDOS
             
             if (tipo_movimiento in ('CONSUMO_MOVIL', 'RETORNO_MOVIL') and not paquete_asignado) or is_shared:
                 # Suma total del SKU en el móvil, independiente del paquete (FILTRADO POR SUCURSAL)
                 sql_asig = "SELECT COALESCE(SUM(cantidad), 0) FROM asignacion_moviles WHERE sku_producto = ? AND UPPER(TRIM(movil)) = UPPER(TRIM(?)) AND sucursal = ?"
                 run_query(cursor, sql_asig, (sku, movil_afectado, sucursal))
                 asignacion_actual = cursor.fetchone()
                 stock_asignado = float(asignacion_actual[0]) if asignacion_actual and asignacion_actual[0] is not None else 0
             else:
                 # Si no se especifica paquete, asumimos 'NINGUNO' para la consulta
                 pq_query = paquete_asignado if paquete_asignado else 'NINGUNO'
                 
                 sql_asig = "SELECT cantidad FROM asignacion_moviles WHERE sku_producto = ? AND UPPER(TRIM(movil)) = UPPER(TRIM(?)) AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?"
                 run_query(cursor, sql_asig, (sku, movil_afectado, pq_query, sucursal))
                 
                 asignacion_actual = cursor.fetchone()
                 stock_asignado = float(asignacion_actual[0]) if asignacion_actual and asignacion_actual[0] is not None else 0
        
        cantidad_bodega_cambio = 0
        cantidad_asignacion_cambio = 0
        cantidad_descarte_cambio = 0 
        
        if tipo_movimiento in ('ENTRADA', 'ABASTO'):
            if not resultado_bodega:
                run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, sucursal) VALUES (?, ?, ?, ?, ?, ?)",
                               (nombre_producto, sku, cantidad_afectada, "BODEGA", secuencia_vista, sucursal))
            else:
                cantidad_bodega_cambio = cantidad_afectada
            
        elif tipo_movimiento == 'SALIDA_MOVIL':
            if stock_bodega_actual < cantidad_afectada:
                return False, f"Stock insuficiente en Bodega para {nombre_producto}. Solo hay {stock_bodega_actual} unidades."
                
            cantidad_bodega_cambio = -cantidad_afectada
            cantidad_asignacion_cambio = cantidad_afectada
            
        elif tipo_movimiento == 'RETORNO_MOVIL':
            if movil_afectado and stock_asignado < cantidad_afectada: 
                 return False, f"Stock insuficiente en {movil_afectado} para el retorno. Solo tiene {stock_asignado} unidades."
                 
            cantidad_bodega_cambio = cantidad_afectada
            cantidad_asignacion_cambio = -cantidad_afectada
            
        elif tipo_movimiento == 'CONSUMO_MOVIL':
            if movil_afectado and stock_asignado < cantidad_afectada:
                 return False, f"Error: El {movil_afectado} solo tiene {stock_asignado} unidades asignadas de '{nombre_producto}'."
                                     
            cantidad_asignacion_cambio = -cantidad_afectada
            
        elif tipo_movimiento == TIPO_MOVIMIENTO_DESCARTE: 
            if movil_afectado:
                if stock_asignado < cantidad_afectada:
                    return False, f"Stock insuficiente en {movil_afectado} para descarte. Solo tiene {stock_asignado} unidades de {nombre_producto}."
                cantidad_asignacion_cambio = -cantidad_afectada
            else:
                if stock_bodega_actual < cantidad_afectada:
                    return False, f"Stock insuficiente en Bodega para {nombre_producto}. Solo hay {stock_bodega_actual} unidades para descarte."
                cantidad_bodega_cambio = -cantidad_afectada
                
            cantidad_descarte_cambio = cantidad_afectada 
            
        elif tipo_movimiento == 'SALIDA':  # NUEVO: Salida individual desde bodega
            if stock_bodega_actual < cantidad_afectada:
                return False, f"Stock insuficiente en Bodega para {nombre_producto}. Solo hay {stock_bodega_actual} unidades."
                
            cantidad_bodega_cambio = -cantidad_afectada

        if cantidad_bodega_cambio != 0:
            if cantidad_bodega_cambio < 0:
                abs_cambio = abs(cantidad_bodega_cambio)
                rc = run_query(cursor, "UPDATE productos SET cantidad = cantidad - ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ? AND cantidad >= ?", 
                               (abs_cambio, sku, sucursal, abs_cambio))
                if rc == 0:
                     if not existing_conn: conn.rollback()
                     return False, f"Error atómico: Stock insuficiente en Bodega para {nombre_producto}. Probablemente modificado por otra sesión."
            else:
                run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", 
                               (cantidad_bodega_cambio, sku, sucursal))
            
        if cantidad_descarte_cambio > 0:
            run_query(cursor, "SELECT sku FROM productos WHERE sku = ? AND ubicacion = ? AND sucursal = ?", (sku, UBICACION_DESCARTE, sucursal))
            
        # 4. ACTUALIZAR ESTADO DE SERIES SI SE PROVEEN
        if seriales and tipo_movimiento == 'CONSUMO_MOVIL':
            for s in seriales:
                run_query(cursor, """
                    UPDATE series_registradas 
                    SET estado = 'CONSUMIDO', ubicacion = 'CONSUMIDO'
                    WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?
                """, (s, s, sucursal))
            descarte_existe = cursor.fetchone()
            
            if descarte_existe:
                 run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = ? AND sucursal = ?",
                                (cantidad_descarte_cambio, sku, UBICACION_DESCARTE, sucursal))
            else:
                run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, sucursal) VALUES (?, ?, ?, ?, ?, ?)",
                               (nombre_producto, sku, cantidad_descarte_cambio, UBICACION_DESCARTE, f'{secuencia_vista}z', sucursal))

        # LOGICA CORREGIDA Y ROBUSTA PARA ASIGNACION MOVILES (POR PAQUETE)
        if movil_afectado and cantidad_asignacion_cambio != 0:
             
             # Para CONSUMO_MOVIL y RETORNO_MOVIL (sin paquete específico) O MATERIALES COMPARTIDOS: 
             # deducir del paquete que realmente tiene stock
             is_shared = sku in MATERIALES_COMPARTIDOS
             if (tipo_movimiento in ('CONSUMO_MOVIL', 'RETORNO_MOVIL')) and cantidad_asignacion_cambio < 0 and (not paquete_asignado or is_shared):
                 # Obtener todas las filas con stock para este SKU en este móvil (FILTRADO POR SUCURSAL)
                 sql_rows = "SELECT COALESCE(paquete, 'NINGUNO'), cantidad FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND sucursal = ? AND cantidad > 0 ORDER BY cantidad DESC"
                 run_query(cursor, sql_rows, (sku, movil_afectado, sucursal))
                 filas_con_stock = cursor.fetchall()
                 
                 pendiente_descontar = abs(cantidad_asignacion_cambio)
                 for fila_pq, fila_qty in filas_con_stock:
                     if pendiente_descontar <= 0:
                         break
                     descontar_de_fila = min(fila_qty, pendiente_descontar)
                     nueva_qty_fila = fila_qty - descontar_de_fila
                     pendiente_descontar -= descontar_de_fila
                     
                     if nueva_qty_fila > 0:
                         run_query(cursor, "UPDATE asignacion_moviles SET cantidad = ? WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?",
                                        (nueva_qty_fila, sku, movil_afectado, fila_pq, sucursal))
                     else:
                         run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?",
                                        (sku, movil_afectado, fila_pq, sucursal))
             else:
                 pq_actual = paquete_para_stock if paquete_para_stock else 'NINGUNO'
                 
                 # 1. Obtener suma total actual para ese paquete específico (FILTRADO POR SUCURSAL)
                 sql_sel = "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?"
                 run_query(cursor, sql_sel, (sku, movil_afectado, pq_actual, sucursal))
                 resultado_asignacion = cursor.fetchone()
                 
                 valor_actual = 0.0
                 if resultado_asignacion and resultado_asignacion[0] is not None:
                     valor_actual = float(resultado_asignacion[0])
                      
                 nueva_cantidad_asignacion = valor_actual + cantidad_asignacion_cambio
                 
                 # 2. UPSERT: Atomic update or Delete+Insert
                 if DB_TYPE == 'MYSQL':
                     # Usar ON DUPLICATE KEY UPDATE para mayor robustez en MySQL (incluyendo sucursal)
                     sql_upsert = """
                        INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad, sucursal) 
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad)
                     """
                     # IMPORTANTE: pq_actual ya está normalizado a 'NINGUNO' si era None o vacío
                     if nueva_cantidad_asignacion > 0:
                         cursor.execute(sql_upsert, (sku, movil_afectado, pq_actual, nueva_cantidad_asignacion, sucursal))
                     else:
                         sql_del = "DELETE FROM asignacion_moviles WHERE sku_producto = %s AND movil = %s AND COALESCE(paquete, 'NINGUNO') = %s AND sucursal = %s"
                         cursor.execute(sql_del, (sku, movil_afectado, pq_actual, sucursal))
                 else:
                     # Standard SQLite approach: Delete then Insert
                     sql_del = "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?"
                     run_query(cursor, sql_del, (sku, movil_afectado, pq_actual, sucursal))
 
                     if nueva_cantidad_asignacion > 0:
                         sql_ins = "INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad, sucursal) VALUES (?, ?, ?, ?, ?)"
                         run_query(cursor, sql_ins, (sku, movil_afectado, pq_actual, nueva_cantidad_asignacion, sucursal))

        # REGISTRO DE MOVIMIENTO (BITÁCORA) - FILTRADO POR SUCURSAL
        sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia, sucursal) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        run_query(cursor, sql_mov, (sku, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia, sucursal))

        # Verificar si se debe marcar recordatorio como completado
        if tipo_movimiento in ['RETORNO_MOVIL', 'CONSUMO_MOVIL'] and movil_afectado and paquete_asignado in ['PAQUETE A', 'PAQUETE B']:
            tipo_recordatorio = 'RETORNO' if tipo_movimiento == 'RETORNO_MOVIL' else 'CONCILIACION'
            run_query(cursor, """
                UPDATE recordatorios_pendientes 
                SET completado = 1, fecha_completado = CURRENT_TIMESTAMP
                WHERE movil = ? AND paquete = ? AND tipo_recordatorio = ? 
                AND fecha_recordatorio = ? AND completado = 0
            """, (movil_afectado, paquete_asignado, tipo_recordatorio, fecha_evento))
        
        if should_close:
            conn.commit()
        
        if tipo_movimiento == TIPO_MOVIMIENTO_DESCARTE:
            mensaje_final = f"✅ Descarte registrado para SKU {sku} ({cantidad_afectada} unidades)."
        elif tipo_movimiento in ('ENTRADA', 'ABASTO'):
            tipo_label = "Abasto" if tipo_movimiento == 'ABASTO' else "Entrada"
            mensaje_final = f"✅ {tipo_label} registrada para SKU {sku} ({cantidad_afectada} unidades)."
        else:
            movil_msg = f" a/desde el {movil_afectado}" if movil_afectado else ""
            paquete_msg = f" (Paq: {paquete_asignado})" if paquete_asignado else ""
            mensaje_final = f"✅ Movimiento {tipo_movimiento} registrado para SKU {sku} ({cantidad_afectada} unidades){movil_msg}{paquete_msg}."
        
        return True, mensaje_final

    except Exception as e:
        if conn and should_close:
            conn.rollback()
        logger.error(f"Error en registrar_movimiento_gui para SKU {sku}: {e}")
        return False, f"Error en la base de datos: {str(e)}"
    finally:
        if conn and should_close:
            close_connection(conn)


# FUNCIONES PARA PRÉSTAMOS SANTIAGO
def registrar_prestamo_santiago(sku, cantidad, fecha_evento, observaciones=None):
    """
    Registra una TRANSFERENCIA desde Bodega Local a Santiago.
    1. Resta de Bodega Local (SALIDA).
    2. Suma a Bodega Santiago (ENTRADA/ABASTO).
    """
    conn = None
    try:
        # Validación
        try:
            sku = validate_sku(sku)
            cantidad = validate_quantity(cantidad, allow_zero=False, allow_negative=False)
            if observaciones:
                 from utils.validators import validate_observaciones
                 observaciones = validate_observaciones(observaciones)
        except ValidationError as ve:
             return False, f"Datos inválidos: {ve}"

        # 1. VERIFICACIÓN LOCAL
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, "SELECT cantidad, nombre FROM productos WHERE sku = ? AND ubicacion = 'BODEGA'", (sku,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, f"El producto con SKU '{sku}' no existe en BODEGA Local."
        
        stock_actual, nombre = resultado
        if stock_actual < cantidad:
            return False, f"Stock insuficiente. Solo hay {stock_actual} unidades disponibles en BODEGA Local."
        
        conn.close() # Cerramos conexión de lectura previa
        conn = None 

        # 2. EJECUTAR TRANSFERENCIA (ATÓMICA IDEALMENTE, PERO SEQUENCIAL AQUÍ)
        
        # PASO A: Restar de Local (Chiriquí)
        obs_salida = f"TRANSFERENCIA A SANTIAGO - {observaciones}" if observaciones else "TRANSFERENCIA A SANTIAGO"
        exito_salida, msg_salida = registrar_movimiento_gui(sku, 'SALIDA', cantidad, None, fecha_evento, None, obs_salida)
        
        if not exito_salida:
            return False, f"Error al descontar de inventario local: {msg_salida}"

        # PASO B: Sumar a Santiago
        # Necesitamos el nombre de la DB de Santiago desde config
        obs_entrada = f"TRANSFERENCIA DESDE CHIRIQUI - {observaciones}" if observaciones else "TRANSFERENCIA DESDE CHIRIQUI"
        # Usamos 'ENTRADA' para que sume a Bodega Santiago. Si no existe el producto allá, lo crea.
        exito_entrada, msg_entrada = registrar_movimiento_gui(sku, 'ENTRADA', cantidad, None, fecha_evento, None, obs_entrada, sucursal_context='SANTIAGO')
        
        if exito_entrada:
             # PASO C: Registrar en prestamos_activos (Local) para seguimiento?
             # El usuario quiere "sumar al apartado de Santiago", lo cual hicimos con el paso B.
             # ¿Mantenemos el registro de "prestamos_activos" localmente?
             # El usuario dijo "implementa el plan", y el plan decía "Step 1 (Source)... Step 2 (Target)".
             # No mencionó eliminar el rastreo de préstamos activos, pero al ser "Transferencia" quizas ya no es un "Préstamo" retornable.
             # Sin embargo, para mantener funcionalidad de "Devolución" si fuera necesario, podríamos mantenerlo.
             # Pero "Transferencia" implica movimiento permanente.
             # El usuario pidio "sumarle los datos al apartado de Santiago y restar a Chiriqui".
             # Voy a comentar la inserción en prestamos_activos ya que ahora es una transferencia real de stock.
             # SI mantenemos prestamos_activos, duplicariamos stock logic (uno en tabla prestamos, otro en DB Santiago).
             return True, f"Transferencia exitosa: {cantidad} unidades enviadas a Santiago."
        else:
             # ROLLBACK MANUAL SERÍA IDEAL AQUÍ PERO COMPLEJO
             return True, f"¡ATENCIÓN! Se descontó de Local pero falló ingreso en Santiago: {msg_entrada}. Contacte soporte."

    except Exception as e:
        return False, f"Error de proceso: {e}"
    finally:
        if conn: close_connection(conn)

def registrar_devolucion_santiago(sku, cantidad, seriales_nuevos, fecha_evento, observaciones=None):
    """
    Registra una devolución desde Santiago a Bodega Local.
    - Descuenta de asignacion_moviles donde movil='SANTIAGO'
    - Suma a Bodega Local (ENTRADA)
    - Registra los seriales nuevos en series_registradas con ubicacion='BODEGA'
    Los seriales devueltos pueden ser DISTINTOS a los enviados originalmente.
    """
    conn = None
    try:
        sku = validate_sku(sku)
        cantidad = validate_quantity(cantidad, allow_zero=False, allow_negative=False)
        if observaciones:
            from utils.validators import validate_observaciones
            observaciones = validate_observaciones(observaciones)
    except ValidationError as ve:
        return False, f"Datos inválidos: {ve}"

    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()

        # 1. Verificar stock asignado a SANTIAGO
        if DB_TYPE == 'MYSQL':
            sql_asig = "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = %s AND movil = 'SANTIAGO'"
        else:
            sql_asig = "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = ? AND movil = 'SANTIAGO'"
        cursor.execute(sql_asig, (sku,))
        res = cursor.fetchone()
        stock_santiago = float(res[0]) if res and res[0] else 0.0

        if stock_santiago < cantidad:
            return False, f"Santiago solo tiene {stock_santiago} unidades asignadas de '{sku}'. No se puede devolver {cantidad}."

        # 2. Descontar de asignacion_moviles SANTIAGO
        nueva_asig = stock_santiago - cantidad
        if DB_TYPE == 'MYSQL':
            cursor.execute("DELETE FROM asignacion_moviles WHERE sku_producto = %s AND movil = 'SANTIAGO'", (sku,))
            if nueva_asig > 0:
                cursor.execute("INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad) VALUES (%s, 'SANTIAGO', NULL, %s)", (sku, nueva_asig))
        else:
            cursor.execute("DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = 'SANTIAGO'", (sku,))
            if nueva_asig > 0:
                cursor.execute("INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad) VALUES (?, 'SANTIAGO', NULL, ?)", (sku, nueva_asig))

        # 3. Sumar a Bodega Local
        run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = 'BODEGA'", (cantidad, sku))

        # 4. Registrar movimiento
        obs_final = f"DEVOLUCIÓN SANTIAGO - {observaciones}" if observaciones else "DEVOLUCIÓN SANTIAGO"
        run_query(cursor, """
            INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, observaciones)
            VALUES (?, 'RETORNO_MOVIL', ?, 'SANTIAGO', ?, ?)
        """, (sku, cantidad, fecha_evento, obs_final))

        # 5. Registrar seriales nuevos en Bodega (si los hay)
        if seriales_nuevos:
            for serial in seriales_nuevos:
                if not serial:
                    continue
                # Verificar si el serial ya existe
                run_query(cursor, "SELECT id FROM series_registradas WHERE serial_number = ?", (serial,))
                existe = cursor.fetchone()
                if existe:
                    # Actualizar ubicación a BODEGA y quitar paquete
                    run_query(cursor, "UPDATE series_registradas SET ubicacion = 'BODEGA', paquete = NULL WHERE serial_number = ?", (serial,))
                else:
                    # Insertar nuevo serial
                    run_query(cursor, """
                        INSERT INTO series_registradas (sku, serial_number, ubicacion, fecha_ingreso, paquete)
                        VALUES (?, ?, 'BODEGA', ?, NULL)
                    """, (sku, serial, fecha_evento))

        conn.commit()
        seriales_msg = f" ({len(seriales_nuevos)} seriales registrados)" if seriales_nuevos else ""
        return True, f"Devolución registrada: {cantidad} unidades de '{sku}' desde Santiago a Bodega{seriales_msg}."

    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        return False, f"Error al registrar devolución: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_prestamos_activos():
    """
    Obtiene todos los préstamos activos.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT sku, nombre_producto, SUM(cantidad_prestada) as total_prestado, 
                   MIN(fecha_prestamo) as primera_fecha, GROUP_CONCAT(observaciones, '; ') as observaciones
            FROM prestamos_activos 
            WHERE estado = 'ACTIVO'
            GROUP BY sku, nombre_producto
            ORDER BY primera_fecha DESC
        """)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def obtener_historial_prestamos_completo():
    """
    Obtiene el historial completo de préstamos.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT sku, nombre_producto, cantidad_prestada, fecha_prestamo, 
                   fecha_devolucion, estado, observaciones
            FROM prestamos_activos 
            ORDER BY fecha_prestamo DESC, sku ASC
        """)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

# FUNCIONES PARA RECORDATORIOS - MEJORADAS
def crear_recordatorio(movil, paquete, tipo_recordatorio, fecha_recordatorio):
    """
    Crea un nuevo recordatorio.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Verificar si ya existe un recordatorio no completado para esta combinación
        run_query(cursor, """
            SELECT COUNT(*) FROM recordatorios_pendientes 
            WHERE movil = ? AND paquete = ? AND tipo_recordatorio = ? 
            AND fecha_recordatorio = ? AND completado = 0
        """, (movil, paquete, tipo_recordatorio, fecha_recordatorio))
        
        if cursor.fetchone()[0] == 0:
            run_query(cursor, """
                INSERT INTO recordatorios_pendientes (movil, paquete, tipo_recordatorio, fecha_recordatorio)
                VALUES (?, ?, ?, ?)
            """, (movil, paquete, tipo_recordatorio, fecha_recordatorio))
            conn.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error al crear recordatorio: {e}")
        return False
    finally:
        if conn: close_connection(conn)

def obtener_recordatorios_pendientes(fecha=None):
    """
    Obtiene los recordatorios pendientes para una fecha específica o para hoy.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        if fecha is None:
            fecha = date.today().isoformat()
        
        run_query(cursor, """
            SELECT id, movil, paquete, tipo_recordatorio, fecha_recordatorio
            FROM recordatorios_pendientes 
            WHERE fecha_recordatorio = ? AND completado = 0
            ORDER BY movil, tipo_recordatorio
        """, (fecha,))
        
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener recordatorios: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_recordatorios_todos(fecha=None):
    """
    Obtiene TODOS los recordatorios para una fecha específica, incluyendo completados.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        if fecha is None:
            fecha = date.today().isoformat()
        
        run_query(cursor, """
            SELECT id, movil, paquete, tipo_recordatorio, fecha_recordatorio, completado
            FROM recordatorios_pendientes 
            WHERE fecha_recordatorio = ?
            ORDER BY movil, tipo_recordatorio
        """, (fecha,))
        
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener todos los recordatorios: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def marcar_recordatorio_completado(id_recordatorio):
    """
    Marca un recordatorio como completado.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, """
            UPDATE recordatorios_pendientes 
            SET completado = 1, fecha_completado = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (id_recordatorio,))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error al marcar recordatorio como completado: {e}")
        return False
    finally:
        if conn: close_connection(conn)

def eliminar_recordatorios_completados():
    """
    Elimina los recordatorios que ya han sido completados.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, "DELETE FROM recordatorios_pendientes WHERE completado = 1")
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error al eliminar recordatorios completados: {e}")
        return False
    finally:
        if conn: close_connection(conn)

def verificar_y_crear_recordatorios_salida(fecha_salida):
    """
    Verifica si hay salidas en una fecha y crea recordatorios automáticamente.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Obtener todas las salidas del día para paquetes A y B
        run_query(cursor, """
            SELECT DISTINCT movil_afectado, paquete_asignado
            FROM movimientos 
            WHERE tipo_movimiento = 'SALIDA_MOVIL' 
            AND fecha_evento = ?
            AND paquete_asignado IN ('PAQUETE A', 'PAQUETE B')
            AND movil_afectado IS NOT NULL
        """, (fecha_salida,))
        
        salidas = cursor.fetchall()
        
        if not salidas:
            return False, "No se encontraron salidas para crear recordatorios"
        
        # Calcular fechas de recordatorios
        try:
            fecha_salida_date = datetime.strptime(fecha_salida, '%Y-%m-%d').date()
        except ValueError:
            return False, "Formato de fecha incorrecto"
            
        fecha_retorno = fecha_salida_date + timedelta(days=1)
        fecha_conciliacion = fecha_salida_date + timedelta(days=2)
        
        recordatorios_creados = 0
        
        for movil, paquete in salidas:
            if movil and paquete:
                # Crear recordatorio de retorno
                if crear_recordatorio(movil, paquete, 'RETORNO', fecha_retorno.isoformat()):
                    recordatorios_creados += 1
                
                # Crear recordatorio de conciliación
                if crear_recordatorio(movil, paquete, 'CONCILIACION', fecha_conciliacion.isoformat()):
                    recordatorios_creados += 1
        
        return True, f"Se crearon {recordatorios_creados} recordatorios automáticamente"
        
    except Exception as e:
        return False, f"Error al verificar y crear recordatorios: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_inventario():
    """Obtiene todos los productos enriquecidos para la tabla principal."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, """
            SELECT id, nombre, sku, cantidad, ubicacion, categoria, marca, minimo_stock 
            FROM productos 
            ORDER BY 
            CASE ubicacion
                WHEN 'BODEGA' THEN 1
                WHEN 'DESCARTE' THEN 3
                ELSE 2
            END,
            secuencia_vista ASC 
        """)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)
            
def obtener_inventario_para_exportar():
    """Obtiene todos los campos del inventario, incluyendo secuencia_vista y fecha_creacion, para exportar."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        sql_query = """
        SELECT ubicacion, secuencia_vista, sku, nombre, cantidad, fecha_creacion
        FROM productos 
        ORDER BY ubicacion DESC, secuencia_vista ASC
        """
        run_query(cursor, sql_query) 
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def obtener_todos_los_skus_para_movimiento(target_db=None, sucursal_context=None):
    """
    Obtiene todos los SKUs y nombres únicos del inventario, y su cantidad en BODEGA (si existe).
    """
    conn = None
    try:
        conn = get_db_connection(target_db=target_db)
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # MODIFICADO: Obtener TODOS los productos únicos (no solo BODEGA)
        sql_unique_skus = """
            SELECT DISTINCT p.nombre, p.sku, p.secuencia_vista
            FROM productos p
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_unique_skus)
        all_products_raw = cursor.fetchall()
        
        import os
        sucursal = sucursal_context or ('SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI')

        # Obtenemos stock en BODEGA para mostrar disponibilidad, filtrado por sucursal
        sql_bodega_stock = """
            SELECT sku, SUM(cantidad) as total
            FROM productos
            WHERE ubicacion = 'BODEGA' AND sucursal = ?
            GROUP BY sku
        """
        run_query(cursor, sql_bodega_stock, (sucursal,))
        bodega_stock = {sku: cantidad for sku, cantidad in cursor.fetchall()}
        
        result = []
        skus_procesados = set()
        
        for nombre, sku, secuencia_vista in all_products_raw:
            if sku not in skus_procesados:  # CLAVE: Verificar que no sea duplicado
                cantidad = bodega_stock.get(sku, 0)  # 0 si no hay en BODEGA
                result.append((nombre, sku, cantidad))
                skus_procesados.add(sku)
            
        return result
    except Exception as e:
        logger.error(f"Error al obtener todos los SKUs para movimiento: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_ultima_salida_movil(movil):
    """Obtiene la última salida realizada a un móvil específico"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = """
            SELECT sku_producto, cantidad_afectada 
            FROM movimientos 
            WHERE tipo_movimiento = 'SALIDA_MOVIL' 
            AND movil_afectado = ? 
            AND fecha_movimiento = (
                SELECT MAX(fecha_movimiento) 
                FROM movimientos 
                WHERE tipo_movimiento = 'SALIDA_MOVIL' 
                AND movil_afectado = ?
            )
        """
        run_query(cursor, sql_query, (movil, movil))
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def obtener_asignacion_movil(movil):
    """Obtiene el inventario actual asignado a un móvil específico (usado en Consiliación)."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        sql_query = """
             SELECT 
                 p.nombre, a.sku_producto, SUM(a.cantidad) as cantidad_total
             FROM asignacion_moviles a
             JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA' 
             WHERE a.movil = ? AND a.cantidad > 0
             GROUP BY a.sku_producto, p.nombre, p.secuencia_vista  -- CORREGIDO: GROUP BY para evitar duplicados
             ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_query, (movil,))
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def obtener_asignacion_movil_con_paquetes(movil):
    """
    Obtiene el stock exacto por paquete (PAQUETE A, PAQUETE B, CARRO, SIN PAQUETE)
    sin aplicar compensaciones incorrectas.
    Basado 100% en movimientos reales - CORREGIDO: SIN DUPLICADOS.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()

        # DETERMINAR FILTRO DE SUCURSAL
        import os
        sucursal_target = 'SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI'

        sql_total = """
            SELECT p.nombre, a.sku_producto, SUM(a.cantidad) as total
            FROM asignacion_moviles a
            JOIN (SELECT sku, nombre, secuencia_vista FROM productos WHERE UPPER(TRIM(sucursal)) = ? OR sucursal IS NULL OR sucursal = '' GROUP BY sku, nombre, secuencia_vista) p ON a.sku_producto = p.sku
            WHERE UPPER(TRIM(a.movil)) = UPPER(TRIM(?)) AND a.cantidad > 0 
            AND (UPPER(TRIM(a.sucursal)) = ? OR a.sucursal IS NULL OR a.sucursal = '')
            GROUP BY a.sku_producto, p.nombre, p.secuencia_vista
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_total, (sucursal_target, movil, sucursal_target))
        productos_asignados = cursor.fetchall()

        if not productos_asignados:
            return []

        # --- NUEVO: Encontrar el punto de corte (última limpieza total) ---
        # Solo procesamos movimientos posteriores a la última limpieza del móvil para evitar stock "fantasma"
        sql_last_clean = """
            SELECT MAX(id) FROM movimientos 
            WHERE UPPER(TRIM(movil_afectado)) = UPPER(TRIM(?)) 
            AND tipo_movimiento = 'LIMPIEZA_MOVIL' 
            AND (paquete_asignado = 'TODOS' OR paquete_asignado IS NULL)
        """
        run_query(cursor, sql_last_clean, (movil,))
        row_clean = cursor.fetchone()
        last_cleaning_id = row_clean[0] if row_clean and row_clean[0] else 0

        resultado = []

        # 2. Optimización N+1: Obtener todos los movimientos relevantes para el móvil de una sola vez
        sql_todos_movs = """
            SELECT sku_producto, tipo_movimiento, cantidad_afectada, paquete_asignado
            FROM movimientos 
            WHERE UPPER(TRIM(movil_afectado)) = UPPER(TRIM(?))
            AND tipo_movimiento IN ('SALIDA_MOVIL','RETORNO_MOVIL','CONSUMO_MOVIL')
            AND id > ?
            ORDER BY fecha_movimiento ASC, id ASC
        """
        run_query(cursor, sql_todos_movs, (movil, last_cleaning_id))
        todos_movimientos = cursor.fetchall()

        # Agrupar movimientos por SKU
        movimientos_por_sku = {}
        for row in todos_movimientos:
            s_sku = row[0]
            if s_sku not in movimientos_por_sku:
                movimientos_por_sku[s_sku] = []
            movimientos_por_sku[s_sku].append((row[1], row[2], row[3]))

        # 3. Procesar cada SKU
        for nombre, sku, total_real in productos_asignados:
            
            # Inicializar los saldos con lo que dice la tabla asignacion_moviles DIRECTAMENTE
            # Esto evita que 'PAQUETE B' se muestre como 'PAQUETE A' por prioridades de relleno.
            sql_pqs = """
                SELECT COALESCE(paquete, 'SIN_PAQUETE'), SUM(cantidad) 
                FROM asignacion_moviles 
                WHERE sku_producto = ? AND UPPER(TRIM(movil)) = UPPER(TRIM(?)) 
                AND (UPPER(TRIM(sucursal)) = ? OR sucursal IS NULL OR sucursal = '')
                GROUP BY paquete
            """
            run_query(cursor, sql_pqs, (sku, movil, sucursal_target))
            filas_pqs = cursor.fetchall()
            
            saldos = {
                "PAQUETE A": 0, "PAQUETE B": 0, "CARRO": 0, 
                "PERSONALIZADO": 0, "SIN_PAQUETE": 0
            }
            
            for p_name, p_qty in filas_pqs:
                p_key = p_name if p_name in saldos else "SIN_PAQUETE"
                if p_name == "NINGUNO": p_key = "SIN_PAQUETE"
                saldos[p_key] = p_qty

            # Guardar resultado final para ese SKU
            resultado.append((
                nombre,
                sku,
                total_real,
                saldos["PAQUETE A"],
                saldos["PAQUETE B"],
                saldos["CARRO"],
                saldos["SIN_PAQUETE"],
                saldos["PERSONALIZADO"]
            ))

        return resultado

    except Exception as e:
        logger.error(f"Error en obtener_asignacion_movil_con_paquetes: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_reporte_asignacion_moviles(movil=None):
    """Obtiene el inventario asignado a TODOS los móviles, opcionalmente filtrado por un móvil específico."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = """
             SELECT 
                 a.movil, p.nombre, a.sku_producto, SUM(a.cantidad) as cantidad_total
             FROM asignacion_moviles a
             JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
             WHERE a.cantidad > 0
             GROUP BY a.movil, a.sku_producto, p.nombre  -- CORREGIDO: GROUP BY para evitar duplicados
        """
        params = []
        
        if movil and movil != "TODOS":
            sql_query += " AND a.movil = ?"
            params.append(movil)
            
        sql_query += " ORDER BY a.movil ASC, p.secuencia_vista ASC"
            
        run_query(cursor, sql_query, params)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def eliminar_producto(sku):
    """Elimina un producto y su historial de movimientos y asignación. Elimina todas las ubicaciones de ese SKU."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, "SELECT nombre FROM productos WHERE sku = ? LIMIT 1", (sku,))
        if not cursor.fetchone():
            return False, f"No se encontró ningún producto con el SKU '{sku}'."
            
        run_query(cursor, "DELETE FROM productos WHERE sku = ?", (sku,))
        run_query(cursor, "DELETE FROM movimientos WHERE sku_producto = ?", (sku,))
        run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ?", (sku,))
        run_query(cursor, "DELETE FROM prestamos_activos WHERE sku = ?", (sku,))

        conn.commit()
        
        return True, f"Producto con SKU '{sku}' (incluyendo todas sus ubicaciones y historial) eliminado exitosamente."
            
    except Exception as e:
        return False, f"Ocurrió un error al intentar eliminar el producto: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_historial_producto(sku, fecha_inicio=None, fecha_fin=None):
    """Obtiene el historial de movimientos de un producto por SKU, con filtro de rango de fechas de evento, incluyendo el paquete asignado."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = """
            SELECT 
                p.nombre, 
                m.tipo_movimiento, 
                m.cantidad_afectada, 
                m.movil_afectado, 
                m.paquete_asignado,
                m.fecha_movimiento,
                m.fecha_evento,
                m.observaciones
            FROM movimientos m
            JOIN productos p ON m.sku_producto = p.sku
            WHERE m.sku_producto = ?
        """
        params = [sku]
        
        if fecha_inicio:
            sql_query += " AND m.fecha_evento >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            sql_query += " AND m.fecha_evento <= ?"
            params.append(fecha_fin)
            
        sql_query += " ORDER BY m.fecha_movimiento DESC"

        run_query(cursor, sql_query, params)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def obtener_abastos_resumen():
    """Obtiene un resumen de los abastos realizados, agrupados por fecha y referencia."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # DETERMINAR FILTRO DE SUCURSAL
        import os
        is_santiago = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'
        sucursal_target = 'SANTIAGO' if is_santiago else 'CHIRIQUI'

        # Agrupar por fecha y documento de referencia (o "Sin Referencia" si es NULL)
        # Contar items y sumar total de unidades
        sql_query = """
            SELECT 
                fecha_evento,
                COALESCE(documento_referencia, 'Sin Referencia') as referencia,
                COUNT(*) as items,
                SUM(cantidad_afectada) as total_unidades,
                MAX(fecha_movimiento) as ultima_modificacion
            FROM movimientos
            WHERE tipo_movimiento IN ('ABASTO', 'RETORNO_MOVIL', 'DEVOLUCION_SANTIAGO')
            AND (sucursal = ? OR (sucursal IS NULL AND ? = 'CHIRIQUI'))
            GROUP BY fecha_evento, documento_referencia, tipo_movimiento
            ORDER BY fecha_evento DESC, ultima_modificacion DESC
        """
        run_query(cursor, sql_query, (sucursal_target, sucursal_target))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener resumen de abastos: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_detalle_abasto(fecha, referencia):
    """Obtiene los detalles de un abasto específico."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # DETERMINAR FILTRO DE SUCURSAL
        import os
        is_santiago = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'
        sucursal_target = 'SANTIAGO' if is_santiago else 'CHIRIQUI'

        sql_query = """
            SELECT 
                m.id,
                p.nombre,
                m.sku_producto,
                m.cantidad_afectada,
                m.documento_referencia,
                m.observaciones
            FROM movimientos m
            JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA' 
            WHERE m.tipo_movimiento = 'ABASTO' 
            AND m.fecha_evento = ? 
            AND COALESCE(m.documento_referencia, 'Sin Referencia') = ?
            AND (m.sucursal = ? OR (m.sucursal IS NULL AND ? = 'CHIRIQUI'))
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_query, (fecha, referencia, sucursal_target, sucursal_target))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener detalle de abasto: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def actualizar_movimiento_abasto(id_movimiento, nueva_cantidad, nueva_referencia):
    """Actualiza la cantidad y referencia de un movimiento de abasto, ajustando el stock."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # 1. Obtener datos actuales del movimiento
        run_query(cursor, "SELECT sku_producto, cantidad_afectada FROM movimientos WHERE id = ?", (id_movimiento,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, "Movimiento no encontrado."
            
        sku, cantidad_anterior = resultado
        
        # 2. Calcular diferencia
        diferencia = nueva_cantidad - cantidad_anterior
        
        # 3. Actualizar stock en Bodega
        if diferencia != 0:
            run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = 'BODEGA'", (diferencia, sku))
            
        # 4. Actualizar movimiento
        run_query(cursor, """
            UPDATE movimientos 
            SET cantidad_afectada = ?, documento_referencia = ?
            WHERE id = ?
        """, (nueva_cantidad, nueva_referencia, id_movimiento))
        
        conn.commit()
        return True, "Abasto actualizado correctamente."
        
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Error al actualizar abasto: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_historial_producto_para_exportar(sku, fecha_inicio=None, fecha_fin=None):
    """Obtiene el historial de movimientos de un producto por SKU con todos los campos relevantes para exportar, con filtro de fecha, incluyendo el paquete."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = """
            SELECT 
                m.id, m.fecha_evento, m.tipo_movimiento, m.cantidad_afectada, 
                m.movil_afectado, m.paquete_asignado, m.fecha_movimiento, m.observaciones
            FROM movimientos m
            WHERE m.sku_producto = ?
        """
        params = [sku]
        
        if fecha_inicio:
            sql_query += " AND m.fecha_evento >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            sql_query += " AND m.fecha_evento <= ?"
            params.append(fecha_fin)
            
        sql_query += " ORDER BY m.fecha_movimiento DESC"

        run_query(cursor, sql_query, params)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: close_connection(conn)

def obtener_reporte_consumo(fecha_inicio, fecha_fin):
    """Obtiene el consumo total de material (SALIDA, CONSUMO_MOVIL, DESCARTE) entre dos fechas."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = f"""
            SELECT 
                p.nombre, 
                m.sku_producto, 
                SUM(m.cantidad_afectada) AS Consumo_Total
            FROM movimientos m
            JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE 
                m.tipo_movimiento IN ({', '.join(['?' for _ in TIPOS_CONSUMO])}) AND
                m.fecha_evento BETWEEN ? AND ?
            GROUP BY 
                m.sku_producto, p.nombre
            ORDER BY 
                p.secuencia_vista ASC
        """
        
        params = TIPOS_CONSUMO + [fecha_inicio, fecha_fin]
        run_query(cursor, sql_query, params)
        return cursor.fetchall()
        
    except Exception as e:
        logger.error(f"Error al generar reporte de consumo: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_reporte_abasto(fecha_inicio, fecha_fin):
    """Obtiene el abasto/entrada total de material (ENTRADA, ABASTO) entre two fechas."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = f"""
            SELECT 
                p.nombre, 
                m.sku_producto, 
                SUM(m.cantidad_afectada) AS Abasto_Total
            FROM movimientos m
            JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE 
                m.tipo_movimiento IN ({', '.join(['?' for _ in TIPOS_ABASTO])}) AND
                m.fecha_evento BETWEEN ? AND ?
            GROUP BY 
                m.sku_producto, p.nombre
            ORDER BY 
                p.secuencia_vista ASC
        """
        
        params = TIPOS_ABASTO + [fecha_inicio, fecha_fin]
        run_query(cursor, sql_query, params)
        return cursor.fetchall()
        
    except Exception as e:
        logger.error(f"Error al generar reporte de abasto: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_stock_actual_y_moviles():
    """Obtiene el stock actual en bodega y el total asignado a móviles por cada SKU."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # SUCURSAL CONTEXTO
        import os
        sucursal = 'SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI'

        # OPTIMIZADO: Consolidar 5 queries en 1 sola usando CTEs para mejor rendimiento
        if DB_TYPE == 'MYSQL':
            sql_consolidada = f"""
                WITH stock_bodega AS (
                    SELECT sku, SUM(cantidad) as cantidad
                    FROM productos 
                    WHERE ubicacion = 'BODEGA' AND sucursal = '{sucursal}'
                    GROUP BY sku
                ),
                stock_moviles AS (
                    SELECT sku_producto, SUM(cantidad) as cantidad
                    FROM asignacion_moviles am
                    JOIN (SELECT sku FROM productos WHERE sucursal = '{sucursal}' GROUP BY sku) p ON am.sku_producto = p.sku
                    WHERE cantidad > 0
                    GROUP BY sku_producto
                ),
                consumo_total AS (
                    SELECT sku_producto, SUM(cantidad_afectada) as cantidad
                    FROM movimientos 
                    WHERE tipo_movimiento IN ({{}}) AND sucursal = '{sucursal}'
                    GROUP BY sku_producto
                ),
                abasto_total AS (
                    SELECT sku_producto, SUM(cantidad_afectada) as cantidad
                    FROM movimientos 
                    WHERE tipo_movimiento IN ({{}}) AND sucursal = '{sucursal}'
                    GROUP BY sku_producto
                )
                SELECT 
                    p.nombre, 
                    p.sku, 
                    COALESCE(sb.cantidad, 0) as stock_bodega,
                    COALESCE(sm.cantidad, 0) as stock_moviles,
                    COALESCE(sb.cantidad, 0) + COALESCE(sm.cantidad, 0) as stock_total,
                    COALESCE(ct.cantidad, 0) as consumo,
                    COALESCE(at.cantidad, 0) as abasto
                FROM productos p
                LEFT JOIN stock_bodega sb ON p.sku = sb.sku
                LEFT JOIN stock_moviles sm ON p.sku = sm.sku_producto
                LEFT JOIN consumo_total ct ON p.sku = ct.sku_producto
                LEFT JOIN abasto_total at ON p.sku = at.sku_producto
                WHERE p.ubicacion = 'BODEGA' AND p.sucursal = '{sucursal}'
                ORDER BY p.secuencia_vista ASC
            """.format(
                ','.join(['%s' for _ in TIPOS_CONSUMO]),
                ','.join(['%s' for _ in TIPOS_ABASTO])
            )
            run_query(cursor, sql_consolidada, TIPOS_CONSUMO + TIPOS_ABASTO)
        else:
            # SQLite también soporta CTEs desde versión 3.8.3
            sql_consolidada = """
                WITH stock_bodega AS (
                    SELECT sku, SUM(cantidad) as cantidad
                    FROM productos 
                    WHERE ubicacion = 'BODEGA'
                    GROUP BY sku
                ),
                stock_moviles AS (
                    SELECT sku_producto, SUM(cantidad) as cantidad
                    FROM asignacion_moviles 
                    WHERE cantidad > 0
                    GROUP BY sku_producto
                ),
                consumo_total AS (
                    SELECT sku_producto, SUM(cantidad_afectada) as cantidad
                    FROM movimientos 
                    WHERE tipo_movimiento IN ({})
                    GROUP BY sku_producto
                ),
                abasto_total AS (
                    SELECT sku_producto, SUM(cantidad_afectada) as cantidad
                    FROM movimientos 
                    WHERE tipo_movimiento IN ({})
                    GROUP BY sku_producto
                )
                SELECT 
                    p.nombre, 
                    p.sku, 
                    COALESCE(sb.cantidad, 0) as stock_bodega,
                    COALESCE(sm.cantidad, 0) as stock_moviles,
                    COALESCE(sb.cantidad, 0) + COALESCE(sm.cantidad, 0) as stock_total,
                    COALESCE(ct.cantidad, 0) as consumo,
                    COALESCE(at.cantidad, 0) as abasto
                FROM productos p
                LEFT JOIN stock_bodega sb ON p.sku = sb.sku
                LEFT JOIN stock_moviles sm ON p.sku = sm.sku_producto
                LEFT JOIN consumo_total ct ON p.sku = ct.sku_producto
                LEFT JOIN abasto_total at ON p.sku = at.sku_producto
                WHERE p.ubicacion = 'BODEGA'
                ORDER BY p.secuencia_vista ASC
            """.format(
                ','.join(['?' for _ in TIPOS_CONSUMO]),
                ','.join(['?' for _ in TIPOS_ABASTO])
            )
            run_query(cursor, sql_consolidada, TIPOS_CONSUMO + TIPOS_ABASTO)
        
        return cursor.fetchall()
        
    except Exception as e:
        logger.error(f"❌ Error en obtener_stock_actual_y_moviles: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def obtener_estadisticas_reales():
    """Obtiene estadísticas reales para el dashboard"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # DETERMINAR FILTRO DE SUCURSAL
        import os
        is_santiago = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'
        sucursal_target = 'SANTIAGO' if is_santiago else 'CHIRIQUI'
        
        # 1. Productos en Bodega (contar productos únicos en BODEGA de esta sucursal)
        run_query(cursor, """
            SELECT COUNT(DISTINCT sku) 
            FROM productos 
            WHERE ubicacion = 'BODEGA' AND cantidad > 0 AND sucursal = ?
        """, (sucursal_target,))
        productos_bodega = cursor.fetchone()[0]
        
        # 2. Móviles Activos (contar móviles con productos asignados de esta sucursal)
        if is_santiago:
            moviles_activos = 0
        else:
            run_query(cursor, """
                SELECT COUNT(DISTINCT movil) 
                FROM asignacion_moviles am
                JOIN (SELECT sku FROM productos WHERE sucursal = ? GROUP BY sku) p ON am.sku_producto = p.sku
                WHERE cantidad > 0
            """, (sucursal_target,))
            moviles_activos = cursor.fetchone()[0]
        
        # 3. Stock Total (suma de todo el stock en BODEGA de esta sucursal)
        run_query(cursor, """
            SELECT SUM(cantidad) 
            FROM productos 
            WHERE ubicacion = 'BODEGA' AND sucursal = ?
        """, (sucursal_target,))
        stock_total_result = cursor.fetchone()[0]
        stock_total = stock_total_result if stock_total_result else 0
        
        # 4. Préstamos Activos (Solo Santiago verá préstamos santiago)
        if is_santiago:
            run_query(cursor, "SELECT COUNT(*) FROM movimientos WHERE tipo_movimiento = 'PRESTAMO_SANTIAGO' AND sucursal = 'SANTIAGO'")
            prestamos_activos = cursor.fetchone()[0]
        else:
            run_query(cursor, "SELECT COUNT(*) FROM prestamos_activos WHERE estado = 'ACTIVO'")
            prestamos_activos = cursor.fetchone()[0]
        
        # 5. Productos con Bajo Stock (en esta sucursal)
        run_query(cursor, """
            SELECT COUNT(*) 
            FROM productos 
            WHERE ubicacion = 'BODEGA' AND cantidad < minimo_stock AND cantidad > 0 AND sucursal = ?
        """, (sucursal_target,))
        bajo_stock = cursor.fetchone()[0]
        
        return {
            "productos_bodega": productos_bodega,
            "moviles_activos": moviles_activos,
            "stock_total": stock_total,
            "prestamos_activos": prestamos_activos,
            "bajo_stock": bajo_stock
        }
    except Exception as e:
        logger.error(f"❌ Error en obtener_estadisticas_reales: {e}")
        return {
            "productos_bodega": 0, "moviles_activos": 0, "stock_total": 0,
            "prestamos_activos": 0, "bajo_stock": 0
        }
        return {
            "productos_bodega": 0,
            "moviles_activos": 0,
            "stock_total": 0,
            "stock_total": 0,
            "prestamos_activos": 0,
            "bajo_stock": 0
        }
    finally:
        if conn: close_connection(conn)

def exportar_a_csv(encabezados, datos, nombre_archivo):
    """
    Exporta datos a un archivo CSV.
    Retorna (boolean, mensaje)
    """
    try:
        with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as archivo:
            writer = csv.writer(archivo)
            writer.writerow(encabezados)
            writer.writerows(datos)
        return True, f"Datos exportados exitosamente a {nombre_archivo}"
    except Exception as e:
        return False, f"Error al exportar los datos: {e}"

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

def obtener_movimientos_por_rango(fecha_inicio, fecha_fin):
    """
    Obtiene todos los movimientos en un rango de fechas.
    Retorna lista de tuplas con detalles del movimiento.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql_query = """
            SELECT 
                m.id, m.sku_producto, m.tipo_movimiento, m.cantidad_afectada, 
                m.movil_afectado, m.fecha_evento, p.nombre, m.observaciones
            FROM movimientos m
            LEFT JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE m.fecha_evento BETWEEN ? AND ?
            ORDER BY m.fecha_evento DESC
        """
        
        run_query(cursor, sql_query, (fecha_inicio, fecha_fin))
        return cursor.fetchall()
        
    except Exception as e:
        logger.error(f"Error al obtener movimientos por rango: {e}")
        return []
    finally:
        if conn: close_connection(conn)

# --- FUNCIONES PARA PORTAL MÓVIL (PUNTO 5) ---

def registrar_consumo_pendiente(movil, sku, cantidad, tecnico, ticket, fecha, colilla=None, contrato=None, ayudante=None, paquete=None):
    """Guarda un reporte proveniente del portal móvil (Punto 5)."""
    conn = None
    try:
        # LÓGICA DE ENRUTAMIENTO (NUEVO): Detectar si es Santiago
        target_db = None
        from config import MOVILES_SANTIAGO
        
        if movil in MOVILES_SANTIAGO:
            pass
            logger.info(f"[ROUTING] Redirigiendo consumo de {movil} a {target_db}")
            
        conn = get_db_connection(target_db=target_db)
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # SUCURSAL CONTEXTO
        sucursal = 'SANTIAGO' if movil in MOVILES_SANTIAGO else 'CHIRIQUI'
        
        run_query(cursor, """
            INSERT INTO consumos_pendientes (movil, sku, cantidad, tecnico_nombre, ayudante_nombre, ticket, fecha, colilla, num_contrato, paquete, sucursal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (movil, sku, cantidad, tecnico, ayudante, ticket, fecha, colilla, contrato, paquete or 'NINGUNO', sucursal))
        conn.commit()
        return True, "Registro guardado"
    except Exception as e:
        return False, str(e)
    finally:
        if conn: close_connection(conn)

def eliminar_consumo_pendiente(id_consumo):
    """Elimina un consumo pendiente específico por su ID."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, "DELETE FROM consumos_pendientes WHERE id = ?", (id_consumo,))
        conn.commit()
        return True, "Registro eliminado correctamente."
    except Exception as e:
        return False, f"Error al eliminar registro: {e}"
    finally:
        if conn: close_connection(conn)

def eliminar_consumos_pendientes_por_movil(movil):
    """Elimina todos los consumos pendientes de un móvil específico."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        # Usar LIKE o UPPER para mayor flexibilidad si es necesario
        run_query(cursor, "DELETE FROM consumos_pendientes WHERE UPPER(movil) = UPPER(?)", (movil,))
        conn.commit()
        logger.info(f"🧹 Consumos pendientes eliminados para el móvil: {movil}")
        return True, f"Consumos pendientes de {movil} eliminados."
    except Exception as e:
        logger.error(f"Error al eliminar consumos de {movil}: {e}")
        return False, f"Error: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_consumos_pendientes(fecha_inicio=None, fecha_fin=None, estado=None, moviles_filtro=None, limite=None, paquete=None):
    """
    Obtiene consumos reportados por móviles filtrando opcionalmente por rango de fechas y móviles específicos.
    estado: Si es None, busca 'PENDIENTE' y 'AUTO_APROBADO' (Petición usuario Móvil 200).
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # DETERMINAR FILTRO DE SUCURSAL
        from config import MOVILES_SANTIAGO, MOVILES_DISPONIBLES
        import os
        is_santiago = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'
        
        # Base query
        sql_query = """
            SELECT c.id, c.movil, c.sku, p.nombre, c.cantidad, c.tecnico_nombre, c.ticket, c.fecha, c.colilla, c.num_contrato, c.ayudante_nombre, c.seriales_usados, c.paquete
            FROM consumos_pendientes c
            LEFT JOIN productos p ON c.sku = p.sku AND p.ubicacion = 'BODEGA' 
            AND (p.sucursal = c.sucursal OR p.sucursal IS NULL OR c.sucursal IS NULL)
            WHERE 1=1
        """
        
        # AUTO-FILTRO POR SUCURSAL (Si no hay un filtro manual específico de móviles)
        if not moviles_filtro or len(moviles_filtro) == 0:
            target_moviles = MOVILES_SANTIAGO if is_santiago else MOVILES_DISPONIBLES
            placeholders = ','.join(['?' for _ in target_moviles])
            sql_query += f" AND c.movil IN ({placeholders})"
            params = list(target_moviles)
        else:
            params = []
        
        # Filtro de estado optimizado
        if estado:
            sql_query += " AND c.estado = ?"
            params.append(estado)
        else:
            # SI NO HAY ESTADO, MOSTRAR PENDIENTES Y AUTO_APROBADOS (Para ver lo "recién enviado")
            sql_query += " AND c.estado IN ('PENDIENTE', 'AUTO_APROBADO')"

        # OPTIMIZADO: Filtrar por móviles en SQL en lugar de Python
        if moviles_filtro and len(moviles_filtro) > 0:
            placeholders = ','.join(['?' for _ in moviles_filtro])
            sql_query += f" AND c.movil IN ({placeholders})"
            params.extend(moviles_filtro)
        
        if fecha_inicio and fecha_fin:
            # Asegurar inclusividad del día final (hasta 23:59:59)
            sql_query += " AND c.fecha >= ? AND c.fecha <= ?"
            params.extend([fecha_inicio, f"{fecha_fin} 23:59:59"])
        elif fecha_inicio:
            sql_query += " AND c.fecha >= ?"
            params.append(fecha_inicio)
        elif fecha_fin:
            sql_query += " AND c.fecha <= ?"
            params.append(f"{fecha_fin} 23:59:59")
            
        if paquete and paquete != 'TODOS':
            sql_query += " AND COALESCE(UPPER(TRIM(c.paquete)), 'NINGUNO') = ?"
            params.append(paquete.strip().upper())
            
        sql_query += " ORDER BY c.fecha_registro DESC"
        
        # NUEVO: Agregar LIMIT para evitar cargar miles de registros
        if limite:
            sql_query += f" LIMIT {int(limite)}"
        
        run_query(cursor, sql_query, tuple(params))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener consumos pendientes: {e}")
        return []
    finally:
        if conn: close_connection(conn)


def obtener_detalles_moviles():
    """Retorna un diccionario {nombre_movil: {conductor, ayudante}}"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, "SELECT nombre, conductor, ayudante FROM moviles WHERE activo = 1")
        filas = cursor.fetchall()
        
        # Si la tabla existe pero está vacía, o si la consulta falla abajo, usamos fallback
        if not filas:
             from config import MOVILES_DETAILS_FALLBACK
             return MOVILES_DETAILS_FALLBACK
             
        return {f[0]: {"conductor": f[1] or "", "ayudante": f[2] or ""} for f in filas}
        
    except Exception as e:
        logger.error(f"⚠️ Error en obtener_detalles_moviles (usando fallback): {e}")
        from config import MOVILES_DETAILS_FALLBACK
        return MOVILES_DETAILS_FALLBACK
    finally:
        if conn: close_connection(conn)

def obtener_inventario_movil(movil):
    """
    Retorna el inventario actual de un móvil específico como diccionario {sku: cantidad}.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # DETERMINAR FILTRO DE SUCURSAL
        from config import MOVILES_SANTIAGO
        suc_filter = 'SANTIAGO' if movil in MOVILES_SANTIAGO else 'CHIRIQUI'

        sql = "SELECT sku_producto, SUM(cantidad) FROM asignacion_moviles WHERE movil = %s AND sucursal = %s GROUP BY sku_producto" if DB_TYPE == 'MYSQL' else "SELECT sku_producto, SUM(cantidad) FROM asignacion_moviles WHERE movil = ? AND sucursal = ? GROUP BY sku_producto"
            
        run_query(cursor, sql, (movil, suc_filter))
        resultados = cursor.fetchall()
        
        return {row[0]: row[1] for row in resultados if row[1] > 0}
        
    except Exception as e:
        logger.error(f"❌ Error al obtener inventario de {movil}: {e}")
        return {}
    finally:
        if conn: close_connection(conn)

def obtener_ultimos_movimientos(limite=15):
    """
    Obtiene los últimos movimientos registrados en el sistema.
    Retorna lista de tuplas: (id, fecha_evento, tipo, producto, cantidad, usuario/movil)
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Obtener movimientos según motor de base de datos (Optimizado para latencia y compatibilidad)
        
        # DETERMINAR FILTRO DE SUCURSAL
        import os
        is_santiago = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'
        sucursal_target = 'SANTIAGO' if is_santiago else 'CHIRIQUI'

        if DB_TYPE == 'MYSQL':
            sql_query = """
                SELECT 
                    m.id,
                    DATE_FORMAT(m.fecha_evento, '%Y-%m-%d') as fecha,
                    m.tipo_movimiento,
                    COALESCE(p.nombre, m.sku_producto) as nombre,
                    m.cantidad_afectada,
                    COALESCE(m.movil_afectado, '-') as detalle
                FROM movimientos m
                LEFT JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
                WHERE m.sucursal = %s OR (m.sucursal IS NULL AND %s = 'CHIRIQUI')
                ORDER BY m.fecha_movimiento DESC
                LIMIT %s
            """
            cursor.execute(sql_query, (sucursal_target, sucursal_target, limite))
        else:
            sql_query = """
                SELECT 
                    m.id,
                    strftime('%Y-%m-%d', m.fecha_evento) as fecha,
                    m.tipo_movimiento,
                    COALESCE(p.nombre, m.sku_producto) as nombre,
                    m.cantidad_afectada,
                    COALESCE(m.movil_afectado, '-') as detalle
                FROM movimientos m
                LEFT JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
                WHERE m.sucursal = ? OR (m.sucursal IS NULL AND ? = 'CHIRIQUI')
                ORDER BY m.fecha_movimiento DESC
                LIMIT ?
            """
            cursor.execute(sql_query, (sucursal_target, sucursal_target, limite))
        
        return cursor.fetchall()
        
    finally:
        if conn: close_connection(conn)

def obtener_historial_completo(limite=500, filtro_texto=None, sucursal_context=None):
    """
    Obtiene el historial completo de movimientos con filtros opcionales.
    """
    conn = None
    try:
        from config import CURRENT_CONTEXT
        sucursal_target = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql = """
            SELECT 
                m.id,
                m.fecha_movimiento,
                m.tipo_movimiento,
                COALESCE(p.nombre, m.sku_producto) as nombre,
                m.cantidad_afectada,
                COALESCE(m.movil_afectado, '-') as detalle,
                COALESCE(m.observaciones, '') as obs
            FROM movimientos m
            LEFT JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE (m.sucursal = ? OR (m.sucursal IS NULL AND ? = 'CHIRIQUI'))
        """
        params = [sucursal_target, sucursal_target]
        
        if filtro_texto:
            sql += """ AND (
                m.sku_producto LIKE ? OR 
                m.tipo_movimiento LIKE ? OR 
                m.movil_afectado LIKE ? OR 
                m.observaciones LIKE ? OR 
                m.documento_referencia LIKE ? OR 
                COALESCE(p.nombre, '') LIKE ?
            )"""
            params.extend([f"%{filtro_texto}%"] * 6)
            
        sql += " ORDER BY m.id DESC LIMIT ?"
        params.append(limite)
        
        if DB_TYPE == 'MYSQL':
            sql = sql.replace('?', '%s')
            
        run_query(cursor, sql, tuple(params))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error en obtener_historial_completo: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def buscar_equipo_global(termino, sucursal_context=None):
    """
    Busca un equipo por MAC o Serial y retorna su estado y ubicación actual.
    """
    conn = None
    try:
        from config import CURRENT_CONTEXT
        sucursal_target = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        termino_clean = str(termino).strip().upper()
        logger.info(f"🔎 Buscando equipo global: '{termino_clean}' en sucursal: '{sucursal_target}'")
        
        sql = """
            SELECT 
                s.serial_number,
                s.mac_number,
                s.sku,
                COALESCE((SELECT nombre FROM productos WHERE sku = s.sku LIMIT 1), 'Equipo Desconocido') as nombre,
                s.ubicacion,
                s.estado,
                s.paquete
            FROM series_registradas s
            WHERE (UPPER(s.serial_number) = ? OR UPPER(s.mac_number) = ?)
              AND (UPPER(s.sucursal) = UPPER(?) OR (s.sucursal IS NULL AND UPPER(?) = 'CHIRIQUI'))
        """
        
        if DB_TYPE == 'MYSQL':
            sql = sql.replace('?', '%s')
            
        run_query(cursor, sql, (termino_clean, termino_clean, sucursal_target, sucursal_target))
        res = cursor.fetchone()
        
        if not res:
            logger.warning(f"❌ No se encontró resultado para '{termino_clean}' con sucursal '{sucursal_target}'")
        else:
            logger.info(f"✅ Resultado encontrado: {res[2]} ({res[4]})")
        
        if res:
            res_list = list(res)
            serial, mac, sku, nombre, ubicacion, estado, paquete = res_list
            
            # Inicializar info extra
            movil_final = None
            contrato_final = None
            
            # --- PLAN A: Buscar en consumos_pendientes (Búsqueda Directa por Serial/MAC) ---
            sql_c = """
                SELECT movil, num_contrato 
                FROM consumos_pendientes 
                WHERE (seriales_usados LIKE ? OR seriales_usados LIKE ?)
                  AND sucursal = ?
                ORDER BY id DESC LIMIT 1
            """
            pattern_s = f'%"{serial}"%' if serial else "%\"___NONE___\"%"
            pattern_m = f'%"{mac}"%' if mac else "%\"___NONE___\"%"
            
            run_query(cursor, sql_c, (pattern_s, pattern_m, sucursal_target))
            cons_extra = cursor.fetchone()
            
            if cons_extra:
                movil_final, contrato_final = cons_extra
            else:
                # --- PLAN B: Buscar en movimientos (Observaciones o Documento) ---
                sql_m = """
                    SELECT movil_afectado, documento_referencia 
                    FROM movimientos 
                    WHERE sku_producto = ? 
                      AND (observaciones LIKE ? OR documento_referencia LIKE ?)
                      AND tipo_movimiento IN ('CONSUMO_MOVIL', 'SALIDA_MOVIL')
                      AND sucursal = ?
                    ORDER BY CASE WHEN tipo_movimiento = 'CONSUMO_MOVIL' THEN 1 ELSE 2 END, id DESC LIMIT 1
                """
                pattern_search = f"%{serial}%" if serial else (f"%{mac}%" if mac else "___NONE___")
                run_query(cursor, sql_m, (sku, pattern_search, pattern_search, sucursal_target))
                mov_extra = cursor.fetchone()
                
                if mov_extra:
                    movil_final, contrato_final = mov_extra
                else:
                    # --- PLAN C: Heurística por Paquete (Última salida de ese SKU/Paquete) ---
                    if paquete and paquete != 'NINGUNO':
                        sql_h = """
                            SELECT movil_afectado, documento_referencia 
                            FROM movimientos 
                            WHERE sku_producto = ? AND paquete_asignado = ? AND sucursal = ?
                              AND tipo_movimiento = 'SALIDA_MOVIL'
                            ORDER BY id DESC LIMIT 1
                        """
                        run_query(cursor, sql_h, (sku, paquete, sucursal_target))
                        mov_h = cursor.fetchone()
                        if mov_h:
                            movil_final, contrato_final = mov_h

            # Agregar info extra al resultado (siempre 2 elementos adicionales)
            res_list.extend([movil_final, contrato_final])
                
            return tuple(res_list)
            
        return None
    except Exception as e:
        logger.error(f"Error en buscar_equipo_global: {e}")
        return None
    finally:
        if conn: close_connection(conn)

# =================================================================
# GESTIÓN DE MÓVILES (CRUD)
# =================================================================

def crear_movil(nombre, patente=None, conductor=None, ayudante=None):
    """Crea un nuevo móvil en la base de datos."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, """
            INSERT INTO moviles (nombre, patente, conductor, ayudante, activo) 
            VALUES (?, ?, ?, ?, 1)
        """, (nombre, patente, conductor, ayudante))
        conn.commit()
        return True, f"Móvil '{nombre}' creado con éxito."
    except sqlite3.IntegrityError:
        return False, f"El móvil '{nombre}' ya existe."
    except Exception as e:
        return False, str(e)
    finally:
        if conn: close_connection(conn)

def obtener_moviles(solo_activos=True):
    """Obtiene la lista de móviles. Retorna lista de tuplas (nombre, patente, conductor, ayudante, activo)."""
    conn = None
    try:
        from config import CURRENT_CONTEXT
        moviles_permitidos = CURRENT_CONTEXT.get('MOVILES', [])
        
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        query = "SELECT nombre, patente, conductor, ayudante, activo FROM moviles"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY nombre ASC"
            
        run_query(cursor, query)
        rows = cursor.fetchall()
        
        if moviles_permitidos:
            return [r for r in rows if r[0] in moviles_permitidos]
        return rows
    except Exception as e:
        logger.error(f"Error al obtener móviles: {e}")
        # Fallback: Intentar obtener nombres si la consulta completa falla
        try:
            return [(m, '', '', '', 1) for m in obtener_nombres_moviles(solo_activos=solo_activos)]
        except:
            return []
    finally:
        if conn: close_connection(conn)

def obtener_nombres_moviles(solo_activos=True):
    """
    Retorna una LISTA de STRINGS con los nombres de los móviles.
    Tenta obtenerlos de la base de datos, pero los filtra para solo mostrar
    los que pertenecen a la sucursal actual (según config).
    """
    from config import CURRENT_CONTEXT
    moviles_permitidos = CURRENT_CONTEXT.get('MOVILES', [])
    
    try:
        moviles = obtener_moviles(solo_activos)
        if moviles:
            # Filtrar por los permitidos de la sucursal activa
            filtrados = [m[0] for m in moviles if m[0] in moviles_permitidos]
            if filtrados:
                return filtrados
    except Exception as e:
        logger.warning(f"Error consultando móviles de DB, usando fallback: {e}")
    
    # Fallback si la DB falla o está vacía
    return moviles_permitidos

def editar_movil(nombre_actual, nuevo_nombre, nueva_patente, nuevo_conductor, nuevo_ayudante):
    """Edita los datos de un móvil."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, """
            UPDATE moviles 
            SET nombre = ?, patente = ?, conductor = ?, ayudante = ?
            WHERE nombre = ?
        """, (nuevo_nombre, nueva_patente, nuevo_conductor, nuevo_ayudante, nombre_actual))
        
        if nombre_actual != nuevo_nombre:
            # Actualizar referencias en otras tablas
            run_query(cursor, "UPDATE asignacion_moviles SET movil = ? WHERE movil = ?", (nuevo_nombre, nombre_actual))
            run_query(cursor, "UPDATE movimientos SET movil_afectado = ? WHERE movil_afectado = ?", (nuevo_nombre, nombre_actual))
            run_query(cursor, "UPDATE recordatorios_pendientes SET movil = ? WHERE movil = ?", (nuevo_nombre, nombre_actual))
            
        conn.commit()
        return True, f"Móvil '{nombre_actual}' actualizado con éxito."
    except sqlite3.IntegrityError:
        return False, "El nuevo nombre ya existe."
    except Exception as e:
        return False, f"Error al actualizar: {e}"
    finally:
        if conn: close_connection(conn)

def eliminar_movil(nombre):
    """
    Marca un móvil como inactivo (Soft Delete).
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Verificar si tiene asignación
        run_query(cursor, "SELECT COUNT(*) FROM asignacion_moviles WHERE movil = ? AND cantidad > 0", (nombre,))
        if cursor.fetchone()[0] > 0:
            return False, "No se puede eliminar: El móvil tiene productos asignados. Realice un retorno o traslado primero."

        run_query(cursor, "UPDATE moviles SET activo = 0 WHERE nombre = ?", (nombre,))
        conn.commit()
        return True, f"Móvil '{nombre}' desactivado correctamente (archivado)."
    except Exception as e:
        return False, f"Error al eliminar: {e}"
    finally:
        if conn: close_connection(conn)

# =================================================================
# CONFIGURACIÓN DE EMPRESA
# =================================================================

def obtener_configuracion():
    """Obtiene los datos de configuración de la empresa."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(dictionary=True)
        else:
            conn.row_factory = sqlite3.Row
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
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

# =================================================================
# GESTIÓN DE USUARIOS Y AUTENTICACIÓN
# =================================================================

def autenticar_usuario(username, password):
    """Verifica credenciales de usuario."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(dictionary=True)
        else:
            conn.row_factory = sqlite3.Row
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
                cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT id, usuario, rol 
            FROM usuarios 
            WHERE usuario = ? AND password = ?
        """, (username, password))
        
        row = cursor.fetchone()
        if row:
            if DB_TYPE == 'MYSQL':
                return row
            else:
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
# =============================================================================================
# GESTIÓN DE SERIES (NUEVO)
# =============================================================================================

def verificar_serie_existe(serial, sku=None, ubicacion_requerida=None, estado_requerido=None):
    """
    Verifica si una serie (Serial o MAC) ya existe en la base de datos.
    """
    conn = None
    try:
        conn = get_db_connection()
        # MySQL requiere cursores con buffer para evitar "Unread result found"
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        ph = '%s' if DB_TYPE == 'MYSQL' else '?'
        
        # Buscar en serial_number O mac_number
        query = f"SELECT sku, estado, ubicacion, serial_number, mac_number FROM series_registradas WHERE serial_number = {ph} OR mac_number = {ph}"
        params = (serial, serial)
            
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        if result:
            sku_existente, estado, ubicacion, s_found, m_found = result
            tipo = "Serial" if s_found == serial else "MAC"
            
            # Validaciones adicionales para Salida
            if estado_requerido and estado != estado_requerido:
                return True, f"La {tipo} '{serial}' no está DISPONIBLE (Estado actual: {estado})"
            
            if ubicacion_requerida and ubicacion != ubicacion_requerida:
                return True, f"La {tipo} '{serial}' no está en {ubicacion_requerida} (Ubicación actual: {ubicacion})"
                
            return True, f"La {tipo} '{serial}' ya existe (SKU: {sku_existente}, Estado: {estado}, Ubicación: {ubicacion})"
            
        return False, "Disponible"

    except Exception as e:
        logger.error(f"Error verificando serie: {e}")
        # IMPORTANTE: Si hay un error de conexión, retornar False para permitir reintento
        return False, f"Error de verificación: {e}"
    finally:
        if conn: close_connection(conn)

def registrar_series_bulk(series_data, fecha_ingreso=None, paquete=None):
    """
    Registra múltiples series en una transacción.
    series_data: Lista de dicts [{sku, serial, mac, ubicacion}, ...]
    fecha_ingreso: Opcional, fecha de registro (YYYY-MM-DD)
    paquete: Opcional, paquete al que pertenecen (ej: PAQUETE A)
    """
    if not fecha_ingreso:
        fecha_ingreso = date.today().isoformat()
        
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        ph = '%s' if DB_TYPE == 'MYSQL' else '?'
        sql = f"""
            INSERT INTO series_registradas (sku, serial_number, mac_number, estado, ubicacion, fecha_ingreso, paquete, sucursal)
            VALUES ({ph}, {ph}, {ph}, 'DISPONIBLE', {ph}, {ph}, {ph}, {ph})
        """
        
        # SUCURSAL CONTEXTO (Fallback)
        import os
        default_sucursal = 'SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI'

        # Preparar datos (SKU, SERIAL, MAC, UBICACION, FECHA, PAQUETE, SUCURSAL)
        data_to_insert = []
        for item in series_data:
            mac = item.get('mac') # Puede ser None
            # Priorizar sucursal del item, luego la global
            item_sucursal = item.get('sucursal', default_sucursal)
            # Priorizar paquete del item, luego el global
            item_paquete = item.get('paquete', paquete)
            data_to_insert.append((item['sku'], item['serial'], mac, item['ubicacion'], fecha_ingreso, item_paquete, item_sucursal))
            
        cursor.executemany(sql, data_to_insert)
        conn.commit()
        return True, f"{len(data_to_insert)} items registrados correctamente."
        
    except sqlite3.IntegrityError as e:
        return False, f"Error de integridad (posible duplicado de Serial o MAC): {e}"
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Error al registrar series: {e}"
    finally:
        if conn: close_connection(conn)

# =================================================================
# FUNCIONES PARA ASIGNACIÓN DE SERIALES A MÓVILES
# =================================================================

def obtener_info_serial(serial_number):
    """
    Busca un serial en series_registradas y retorna su SKU y ubicación.
    Busca en serial_number Y mac_number para soportar escaneo por MAC.
    Retorna: (sku, ubicacion) o (None, None) si no se encuentra
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        serial_clean = str(serial_number).strip().upper()
        
        # Buscar en serial_number O mac_number (para soportar MACs)
        sql = """
            SELECT sku, ubicacion
            FROM series_registradas
            WHERE UPPER(serial_number) = ? OR UPPER(mac_number) = ?
            LIMIT 1
        """
        
        run_query(cursor, sql, (serial_clean, serial_clean))
        result = cursor.fetchone()
        
        if result:
            return result[0], result[1]
        return None, None
        
    finally:
        if conn: close_connection(conn)


def obtener_detalles_serial(serial_number):
    """
    Retorna un diccionario con detalles del serial (sku, ubicacion, serial_number, mac_number).
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        serial_clean = str(serial_number).strip().upper()
        
        sql = """
            SELECT sku, ubicacion, serial_number, mac_number
            FROM series_registradas
            WHERE UPPER(serial_number) = ? OR UPPER(mac_number) = ?
            LIMIT 1
        """
        
        run_query(cursor, sql, (serial_clean, serial_clean))
        result = cursor.fetchone()
        
        if result:
            return {
                'sku': result[0],
                'ubicacion': result[1],
                'serial_number': result[2],
                'mac_number': result[3]
            }
        return None
        
    except Exception as e:
        logger.error(f"[ERROR] obtener_detalles_serial: {e}")
        return None
    finally:
        if conn: close_connection(conn)



def actualizar_ubicacion_serial(serial_number, nueva_ubicacion, paquete=None, existing_conn=None, sucursal_context=None):
    """
    Actualiza la ubicación de un serial específico.
    Retorna: (exito: bool, mensaje: str)
    Allows re-using existing_conn.
    """
    conn = None
    should_close = True
    try:
        if existing_conn:
            conn = existing_conn
            should_close = False
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
                cursor = conn.cursor()
        else:
            conn = get_db_connection()
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
                cursor = conn.cursor()
        
        # Resolver sucursal si no se proporciona
        sucursal = sucursal_context
        if not sucursal:
            import os
            sucursal = 'SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI'

        # Normalizar paquete para persistencia y filtros
        pq_norm = paquete if paquete else 'NINGUNO'

        sql = """
            UPDATE series_registradas
            SET ubicacion = ?, paquete = ?
            WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?
        """
        
        run_query(cursor, sql, (nueva_ubicacion, pq_norm, serial_number, serial_number, sucursal))
        
        if should_close:
            conn.commit()
            
        return True, "Ubicación actualizada"
        
    except Exception as e:
        if conn and should_close: conn.rollback()
        logger.error(f"Error actualizando ubicación serial: {e}")
        return False, f"Error: {e}"
    finally:
        if conn and should_close:
            close_connection(conn)

def obtener_series_por_sku_y_ubicacion(sku, ubicacion, paquete=None):
    """
    Retorna una lista de seriales (MACs) para un SKU en una ubicación específica,
    opcionalmente filtrado por paquete.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql = "SELECT serial_number, mac_number FROM series_registradas WHERE sku = ? AND UPPER(TRIM(ubicacion)) = UPPER(TRIM(?)) AND estado = 'DISPONIBLE'"
        params = [sku, ubicacion]
        
        if paquete and paquete != "TODOS":
            # Permitir NULL o NINGUNO como fallback
            sql += " AND (UPPER(TRIM(paquete)) = UPPER(TRIM(?)) OR paquete IS NULL OR paquete = '' OR UPPER(TRIM(paquete)) = 'NINGUNO')"
            params.append(paquete)
            
        run_query(cursor, sql, params)
        return cursor.fetchall()
        
    except Exception as e:
        logger.error(f"Error obteniendo series: {e}")
        return []
    finally:
        if conn: close_connection(conn)


def incrementar_asignacion_movil(nombre_movil, sku, cantidad):
    """
    Incrementa la cantidad asignada en asignacion_moviles.
    Si no existe el registro, lo crea.
    Retorna: (exito: bool, mensaje: str)
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Primero verificar si existe
        sql_check = """
            SELECT cantidad_total
            FROM asignacion_moviles
            WHERE nombre_movil = ? AND sku_producto = ?
        """
        run_query(cursor, sql_check, (nombre_movil, sku))
        result = cursor.fetchone()
        
        if result:
            # Actualizar cantidad existente
            nueva_cantidad = result[0] + cantidad
            sql_update = """
                UPDATE asignacion_moviles
                SET cantidad_total = ?
                WHERE nombre_movil = ? AND sku_producto = ?
            """
            run_query(cursor, sql_update, (nueva_cantidad, nombre_movil, sku))
        else:
            # Crear nuevo registro
            # Obtener nombre del producto
            sql_producto = "SELECT nombre FROM productos WHERE sku = ?"
            run_query(cursor, sql_producto, (sku,))
            producto_result = cursor.fetchone()
            nombre_producto = producto_result[0] if producto_result else "Producto Desconocido"
            
            sql_insert = """
                INSERT INTO asignacion_moviles (nombre_movil, nombre_producto, sku_producto, cantidad_total)
                VALUES (?, ?, ?, ?)
            """
            run_query(cursor, sql_insert, (nombre_movil, nombre_producto, sku, cantidad))
        
        conn.commit()
        return True, f"Asignación actualizada: +{cantidad} para {sku}"
        
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Error al incrementar asignación: {e}"
    finally:
        if conn: close_connection(conn)

# =================================================================
# FUNCIONES PARA RETORNO MANUAL DE MATERIALES (AUDITORÍA)
# =================================================================

def obtener_asignacion_movil_activa(movil):
    """
    Obtiene todos los productos asignados a un móvil con cantidad > 0
    
    Returns:
        List of tuples: (sku, nombre_producto, cantidad)
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Obtener asignaciones actuales del móvil
        query = """
            SELECT a.sku_producto, p.nombre, a.cantidad
            FROM asignacion_moviles a
            INNER JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE a.movil = ? AND a.cantidad > 0
            ORDER BY p.nombre
        """
        run_query(cursor, query, (movil,))
        return cursor.fetchall()
        
    except Exception as e:
        logger.error(f"Error al obtener asignación de móvil: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def procesar_retorno_manual(movil, sku, cantidad, fecha_evento, observaciones=None):
    """
    Procesa un retorno manual desde móvil a bodega
    
    Returns:
        tuple: (exito: bool, mensaje: str)
    """
    conn = None
    try:
        # Validar que el móvil tenga material asignado
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT cantidad FROM asignacion_moviles 
            WHERE sku_producto = ? AND movil = ?
        """, (sku, movil))
        
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, f"El móvil {movil} no tiene material asignado del SKU {sku}"
        
        cantidad_asignada = resultado[0]
        
        if cantidad > cantidad_asignada:
            return False, f"Cantidad a retornar ({cantidad}) excede la cantidad asignada ({cantidad_asignada})"
        
        conn.close()
        
        # Crear observación descriptiva
        obs_final = f"RETORNO MANUAL desde Auditoría"
        if observaciones:
            obs_final += f" - {observaciones}"
        
        # Procesar retorno usando función existente
        exito, mensaje = registrar_movimiento_gui(
            sku=sku,
            tipo_movimiento='RETORNO_MOVIL',
            cantidad_afectada=cantidad,
            movil_afectado=movil,
            fecha_evento=fecha_evento,
            paquete_asignado=None,
            observaciones=obs_final
        )
        
        return exito, mensaje
        
    except Exception as e:
        return False, f"Error al procesar retorno: {e}"
    finally:
        if conn: close_connection(conn)

def obtener_sku_por_codigo_barra(codigo_barra):
    """
    Busca un producto por su código de barra y retorna el SKU.
    Retorna None si no se encuentra.
    Incluye normalización automática de comillas/apóstrofes.
    """
    if not codigo_barra: return None
    
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # NORMALIZACIÓN CENTRAL: Reemplazar comillas por guiones
        raw_code = str(codigo_barra).strip().upper()
        codigo = raw_code.replace("'", "-").replace("´", "-").replace("`", "-")
        
        # 1. Buscar en columna codigo_barra (Legacy/Original)
        try:
             query = "SELECT sku FROM productos WHERE codigo_barra = ? OR codigo_barra = ? LIMIT 1"
             run_query(cursor, query, (codigo, raw_code))
             result = cursor.fetchone()
             if result:
                 return result[0]
        except:
             pass 
        
        # 2. Buscar en columna codigo_barra_maestro (NUEVO SISTEMA)
        try:
             # Logic expanded to handle ' vs - mismatch
             candidates = [codigo, raw_code]
             
             # Reverse Normalization: If input has dashes, try replacing with single quotes
             # DB has 1'2'16 but scanner reads 1-2-16
             if "-" in raw_code:
                 candidates.append(raw_code.replace("-", "'"))
                 
             for cand in candidates:
                 query_maestro = "SELECT sku FROM productos WHERE codigo_barra_maestro = ? LIMIT 1"
                 run_query(cursor, query_maestro, (cand,))
                 result_maestro = cursor.fetchone()
                 if result_maestro:
                     return result_maestro[0]
        except:
             pass

        # 3. Fallback: Buscar si el codigo ES el SKU
        query_sku = "SELECT sku FROM productos WHERE sku = ? OR sku = ? LIMIT 1"
        run_query(cursor, query_sku, (codigo, raw_code))
        result_sku = cursor.fetchone()
        if result_sku:
            return result_sku[0]
            
        return None
    except Exception as e:
        logger.error(f"Error buscando por código de barra: {e}")
        return None
    finally:
        if conn: close_connection(conn)

def identificar_codigo_escaneado_gui(codigo):
    """
    Combina obtener_info_serial y obtener_sku_por_codigo_barra en una SOLA conexión.
    Esto reduce drásticamente el lag (handshake de red) en aplicaciones GUI.
    Retorna: (sku_encontrado, es_serial, ubicacion_serial)
    """
    if not codigo: return None, False, None
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
            
        raw_code = str(codigo).strip().upper()
        codigo_norm = raw_code.replace("'", "-").replace("´", "-").replace("`", "-")
        
        # 1. Intentar como Serial/MAC (series_registradas)
        sql_serial = "SELECT sku, ubicacion FROM series_registradas WHERE UPPER(serial_number) = ? OR UPPER(mac_number) = ? LIMIT 1"
        run_query(cursor, sql_serial, (raw_code, raw_code))
        result_serial = cursor.fetchone()
        
        if result_serial:
            return result_serial[0], True, result_serial[1]
            
        # 2. Intentar como Material (productos: codigo_barra)
        try:
             query_cb = "SELECT sku FROM productos WHERE codigo_barra = ? OR codigo_barra = ? LIMIT 1"
             run_query(cursor, query_cb, (codigo_norm, raw_code))
             result_cb = cursor.fetchone()
             if result_cb: return result_cb[0], False, None
        except: pass
        
        # 3. Intentar como Maestro (productos: codigo_barra_maestro)
        try:
             candidates = [codigo_norm, raw_code]
             if "-" in raw_code: candidates.append(raw_code.replace("-", "'"))
             for cand in candidates:
                 query_maestro = "SELECT sku FROM productos WHERE codigo_barra_maestro = ? LIMIT 1"
                 run_query(cursor, query_maestro, (cand,))
                 result_maestro = cursor.fetchone()
                 if result_maestro: return result_maestro[0], False, None
        except: pass
        
        # 4. Fallback directo a SKU
        query_sku = "SELECT sku FROM productos WHERE sku = ? OR sku = ? LIMIT 1"
        run_query(cursor, query_sku, (codigo_norm, raw_code))
        result_sku = cursor.fetchone()
        if result_sku: return result_sku[0], False, None
        
        return None, False, None
        
    except Exception as e:
        logger.error(f"Error en identificar_codigo_escaneado_gui: {e}")
        return None, False, None
    finally:
        if conn: close_connection(conn)


def obtener_sku_por_serial(serial):
    """
    Busca el SKU asociado a un número de serie (MAC, etc) en la tabla series_registradas.
    Retorna (sku, existe, ubicacion)
    """
    if not serial: return None, False, None
    
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Reemplazos básicos para evitar errores de scanner
        serial_clean = str(serial).strip().upper().replace("'", "-")
        
        # Búsqueda insensible a mayúsculas: busca en serial_number O mac_number
        sql = "SELECT sku, ubicacion FROM series_registradas WHERE UPPER(serial_number) = UPPER(?) OR UPPER(mac_number) = UPPER(?) LIMIT 1"
        run_query(cursor, sql, (serial_clean, serial_clean))
        result = cursor.fetchone()
        
        if result:
            return result[0], True, result[1]
            
        return None, False, None

    except Exception as e:
        logger.error(f"❌ Error en obtener_sku_por_serial: {e}")
        return None, False, None
    finally:
        if conn: close_connection(conn)


# =================================================================
# FUNCIONES PARA SISTEMA DE ESCANEO UNIVERSAL
# Agregado: 2026-02-11
# =================================================================

def buscar_producto_por_codigo_barra_maestro(codigo_barra):
    """
    Busca un producto por su código de barra maestro o por SKU.
    Incluye normalización automática de comillas/apóstrofes.
    
    Args:
        codigo_barra: Código de barra maestro o SKU del producto
        
    Returns:
        dict con información del producto o None si no existe
    """
    if not codigo_barra: return None
    
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # NORMALIZACIÓN CENTRAL: Reemplazar comillas por guiones
        raw_code = str(codigo_barra).strip().upper()
        codigo = raw_code.replace("'", "-").replace("´", "-").replace("`", "-")
        
        # Buscar por código de barra (maestro o legacy) O por SKU (case-insensitive)
        run_query(cursor, """
            SELECT p.sku, p.nombre, p.cantidad as stock
            FROM productos p
            WHERE (UPPER(TRIM(p.codigo_barra_maestro)) IN (?, ?) 
               OR UPPER(TRIM(p.codigo_barra)) IN (?, ?)
               OR UPPER(TRIM(p.sku)) IN (?, ?))
               AND p.ubicacion = 'BODEGA'
            LIMIT 1
        """, (codigo, raw_code, codigo, raw_code, codigo, raw_code))
        
        resultado = cursor.fetchone()
        if not resultado:
            return None
            
        sku, nombre, stock = resultado
        
        # Determinar si tiene seriales
        from config import PRODUCTOS_CON_CODIGO_BARRA
        tiene_seriales = sku in PRODUCTOS_CON_CODIGO_BARRA
        
        return {
            'sku': sku,
            'nombre': nombre,
            'stock_actual': stock,
            'tiene_seriales': tiene_seriales
        }
    except Exception as e:
        logger.error(f"Error buscando producto por código de barra {codigo_barra}: {e}")
        return None
    finally:
        if conn: 
            close_connection(conn)




def obtener_producto_nombre(sku):
    """Obtiene el nombre de un producto por su SKU"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        run_query(cursor, "SELECT nombre FROM productos WHERE sku = ? LIMIT 1", (sku,))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Exception as e:
        logger.error(f"Error obteniendo nombre de producto: {e}")
        return None
    finally:
        if conn:
            close_connection(conn)


def buscar_producto_por_mac(mac_address):
    """
    Busca un producto por su MAC/serial en la tabla series_registradas.
    
    Args:
        mac_address: MAC o serial del equipo
        
    Returns:
        dict con información del producto o None si no existe
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Normalizar MAC (uppercase y trim)
        mac = mac_address.strip().upper()
        
        # Buscar en tabla series_registradas
        run_query(cursor, """
            SELECT s.sku, p.nombre, s.ubicacion, s.mac_number
            FROM series_registradas s
            JOIN productos p ON s.sku = p.sku
            WHERE UPPER(TRIM(s.mac_number)) = ? AND s.estado = 'DISPONIBLE'
            LIMIT 1
        """, (mac,))
        
        resultado = cursor.fetchone()
        if not resultado:
            return None
            
        sku, nombre, ubicacion, mac_number = resultado
        
        # Verificar que esté en BODEGA
        if ubicacion != 'BODEGA':
            logger.warning(f"MAC {mac} encontrado pero no está en BODEGA (ubicación: {ubicacion})")
            return None
        
        return {
            'sku': sku,
            'nombre': nombre,
            'serial_mac': mac_number,
            'ubicacion': ubicacion,
            'tiene_seriales': True,
            'es_mac': True  # Flag para identificar que fue búsqueda por MAC
        }
    except Exception as e:
        logger.error(f"Error buscando producto por MAC {mac_address}: {e}")
        return None
    finally:
        if conn: 
            close_connection(conn)



def actualizar_codigo_barra_maestro(sku, codigo_barra_maestro):
    """
    Actualiza el código de barra maestro de un producto.
    
    Args:
        sku: SKU del producto
        codigo_barra_maestro: Nuevo código de barra maestro
    
    Returns:
        tuple (exito: bool, mensaje: str)
    """
    conn = None
    try:
        # NORMALIZAR código escaneado (convertir caracteres problemáticos del scanner)
        if codigo_barra_maestro:
            # Reemplazar comillas arriba/acentos por guiones
            codigo_barra_maestro = codigo_barra_maestro.replace('´', '-')
            codigo_barra_maestro = codigo_barra_maestro.replace('`', '-')
            codigo_barra_maestro = codigo_barra_maestro.replace('′', '-')
            codigo_barra_maestro = codigo_barra_maestro.strip().upper()
        
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Verificar si el código ya existe en otro producto
        if codigo_barra_maestro:
            run_query(cursor, """
                SELECT sku FROM productos 
                WHERE codigo_barra_maestro = ? AND sku != ?
                LIMIT 1
            """, (codigo_barra_maestro, sku))
            
            if cursor.fetchone():
                return False, f"El código de barra '{codigo_barra_maestro}' ya está asignado a otro producto"
        
        # Actualizar en todas las ubicaciones (el código maestro pertenece al SKU)
        run_query(cursor, """
            UPDATE productos 
            SET codigo_barra_maestro = ?
            WHERE sku = ?
        """, (codigo_barra_maestro, sku))
        
        conn.commit()
        logger.info(f"Código de barra maestro actualizado: {sku} -> {codigo_barra_maestro}")
        return True, "Código de barra actualizado exitosamente"
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error actualizando código de barra maestro: {e}")
        return False, f"Error: {e}"
    finally:
        if conn:
            close_connection(conn)


def registrar_abasto_batch(items_abasto, fecha_evento, numero_abasto=None):
    """
    Registra múltiples items de abasto en una sola transacción.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Iniciar transacción explícita
        if DB_TYPE == 'MYSQL':
            cursor.execute("START TRANSACTION")
        else:
            cursor.execute("BEGIN IMMEDIATE")
        
        total_unidades = 0
        series_globales = []
        
        # SUCURSAL CONTEXTO
        import os
        sucursal = 'SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI'

        for item in items_abasto:
            sku = item['sku']
            cantidad = item['cantidad']
            seriales = item.get('seriales', [])
            
            observacion = f"Abasto por escaneo"
            if numero_abasto:
                observacion += f" #{numero_abasto}"
            
            # 1. Registrar movimiento
            # The original instruction snippet was a bit confusing, assuming the intent is to pass 'sucursal'
            # to registrar_movimiento_gui if it supports it, or to directly insert if not.
            # Given the existing call, we'll add 'sucursal' as a new argument.
            exito, msg = registrar_movimiento_gui(
                sku=sku,
                tipo_movimiento='ABASTO',
                cantidad_afectada=cantidad,
                fecha_evento=fecha_evento,
                documento_referencia=numero_abasto,
                existing_conn=conn,
                sucursal_context=sucursal
            )
            
            if not exito:
                conn.rollback()
                return False, f"Error en {sku}: {msg}"
            
            # 2. Preparar seriales para registro masivo
            if seriales:
                for ser_item in seriales:
                    if isinstance(ser_item, dict):
                        s_val = ser_item.get('serial')
                        m_val = ser_item.get('mac')
                    else:
                        s_val = str(ser_item)
                        m_val = None
                    
                    if s_val:
                        series_globales.append({
                            'sku': sku,
                            'serial': s_val,
                            'mac': m_val,
                            'ubicacion': 'BODEGA',
                            'sucursal': sucursal
                        })
            
            total_unidades += cantidad
        
        # 3. Registrar todas las series (usando la función robusta que ya actualizamos)
        if series_globales:
            # Importante: Aquí 'paquete' es None porque es BODEGA inicial
            ok_s, msg_s = registrar_series_bulk(series_globales, fecha_ingreso=fecha_evento, paquete=None)
            if not ok_s:
                conn.rollback()
                return False, msg_s
                
        conn.commit()
        return True, f"Abasto registrado: {len(items_abasto)} productos, {total_unidades} unidades."
        
    except Exception as e:
        if conn:
            conn.rollback()
        error_msg = f"Error al registrar abasto batch: {e}"
        logger.error(error_msg)
        return False, error_msg
    finally:
        if conn:
            close_connection(conn)




def eliminar_consumos_pendientes_por_movil(movil):
    """
    Elimina todos los consumos pendientes asociados a un móvil específico.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        ph = '%s' if DB_TYPE == 'MYSQL' else '?'
        
        # Eliminar consumos pendientes
        sql_del = f"DELETE FROM consumos_pendientes WHERE UPPER(TRIM(movil)) = UPPER(TRIM({ph}))"
        cursor.execute(sql_del, (movil,))
        count = cursor.rowcount
        
        conn.commit()
        logger.info(f"📋 Consumos pendientes eliminados para {movil}: {count} registros.")
        return True, f"Se han eliminado {count} consumos pendientes para el {movil}."
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error al eliminar consumos pendientes: {e}")
        return False, f"Error al eliminar consumos: {e}"
    finally:
        if conn: close_connection(conn)

def resetear_stock_movil(movil, paquete):
    """
    Elimina la asignación de un móvil para un paquete específico o para TODO.
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        ph = '%s' if DB_TYPE == 'MYSQL' else '?'
        
        from config import CURRENT_CONTEXT
        sucursal_active = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
        # Normalizar nombres para comparación robusta
        movil_norm = movil.strip().upper()
        paquete_norm = paquete.strip().upper()
        
        # Caso 1: Resetear TODO el móvil
        if paquete_norm == 'TODOS':
            # 1. Contar items a eliminar
            sql_check = f"SELECT SUM(cantidad) FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = {ph} AND sucursal = {ph}"
            cursor.execute(sql_check, (movil_norm, sucursal_active))
            res = cursor.fetchone()
            total_items = res[0] if res and res[0] else 0
            
            # 2. Eliminar asignaciones
            sql_del = f"DELETE FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = {ph} AND sucursal = {ph}"
            cursor.execute(sql_del, (movil_norm, sucursal_active))
            
            # 3. Resetear Series (Equipos) -> Volver a BODEGA y paquete NINGUNO
            sql_reset_series = f"UPDATE series_registradas SET ubicacion = 'BODEGA', estado = 'DISPONIBLE', paquete = 'NINGUNO' WHERE UPPER(TRIM(ubicacion)) = {ph} AND sucursal = {ph}"
            cursor.execute(sql_reset_series, (movil_norm, sucursal_active))

            # 4. Limpiar Consumos Pendientes (TOTAL)
            sql_del_cons = f"DELETE FROM consumos_pendientes WHERE UPPER(TRIM(movil)) = {ph} AND sucursal = {ph}"
            cursor.execute(sql_del_cons, (movil_norm, sucursal_active))
            
            observacion = f"Limpieza TOTAL del móvil {movil_norm} (PIN 0440)"
        
        # Caso 2: Resetear un paquete específico
        else:
            # 1. Contar items
            sql_check = f"SELECT SUM(cantidad) FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = {ph} AND COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} AND sucursal = {ph}"
            cursor.execute(sql_check, (movil_norm, paquete_norm, sucursal_active))
            res = cursor.fetchone()
            total_items = res[0] if res and res[0] else 0
            
            # 2. Eliminar asignaciones del paquete
            sql_del = f"DELETE FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = {ph} AND COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} AND sucursal = {ph}"
            cursor.execute(sql_del, (movil_norm, paquete_norm, sucursal_active))

            # 3. Resetear Series correspondientes al paquete -> Volver a BODEGA y paquete NINGUNO
            sql_reset_series = f"UPDATE series_registradas SET ubicacion = 'BODEGA', estado = 'DISPONIBLE', paquete = 'NINGUNO' WHERE UPPER(TRIM(ubicacion)) = {ph} AND COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} AND sucursal = {ph}"
            cursor.execute(sql_reset_series, (movil_norm, paquete_norm, sucursal_active))
            
            # --- NUEVO: Limpiar Consumos Pendientes del paquete ---
            sql_del_cons = f"DELETE FROM consumos_pendientes WHERE UPPER(TRIM(movil)) = {ph} AND COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} AND sucursal = {ph}"
            cursor.execute(sql_del_cons, (movil_norm, paquete_norm, sucursal_active))
            
            observacion = f"Limpieza de {paquete_norm} en móvil {movil_norm} (PIN 0440)"
        
        # Registrar movimiento de 'LIMPIEZA'
        sql_mov = """
            INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, 
                                   paquete_asignado, fecha_evento, observaciones)
            VALUES ('N/A', 'LIMPIEZA_MOVIL', ?, ?, ?, CURRENT_DATE, ?)
        """
        run_query(cursor, sql_mov, (total_items, movil, paquete, observacion))
        
        conn.commit()
        logger.info(f"🧹 Móvil {movil} ({paquete}) limpiado: {total_items} registros eliminados.")
        return True, f"Se ha limpiado el {movil} ({paquete}) correctamente. Se eliminaron registros de {total_items} unidades de stock."
        
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error al resetear stock de móvil: {e}")
        return False, f"Error al resetear stock: {e}"
    finally:
        if conn: close_connection(conn)

def registrar_danado_directo(sku, cantidad, tecnico, observaciones=None, seriales=None, sucursal_context=None, paquete=None):
    """
    Registra material o equipos DAÑADOS. 
    Para equipo, detecta su ubicación automáticamente (Bodega o Móvil) y lo descarga.
    Para material, lo descarga de BODEGA por defecto si es reporte directo, o del móvil si se proveen datos.
    """
    from config import UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE
    from datetime import date
    import os
    import json
    
    if not seriales:
        # Reutilizamos la lógica de consumo directo para materiales
        # Si técnico es una móvil, intentamos descontar de ahí si se desea, 
        # pero para simplificar registrar_danado_directo sin seriales suele ser desde bodega o descarga general.
        return registrar_consumo_directo(
            sku=sku,
            cantidad=cantidad,
            movil=tecnico if tecnico else 'BODEGA',
            tecnico=tecnico,
            fecha_evento=date.today().isoformat(),
            seriales=seriales,
            observaciones=observaciones if observaciones else "Reporte de Material Dañado",
            tipo_custom=TIPO_MOVIMIENTO_DESCARTE,
            paquete=paquete
        )
        
    # Lógica para EQUIPOS (detectando ubicación en vivo)
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # Determinar sucursal del contexto si es posible
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context if sucursal_context else CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        fecha_evento = date.today().isoformat()
        obs = observaciones if observaciones else "Reporte de Equipo Dañado"
        
        exitos = 0
        errores = []
        
        for sn in seriales:
            # 1. Obtener ubicación REAL y SKU del equipo
            run_query(cursor, "SELECT ubicacion, sku, paquete FROM series_registradas WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?", (sn, sn, sucursal))
            row = cursor.fetchone()
            if not row:
                errores.append(f"Serial/MAC {sn} no encontrado.")
                continue
                
            loc_real = row[0]
            sku_real = row[1]
            pq_real = row[2] if row[2] else 'NINGUNO'
            
            # 2. Descontar del inventario lógico según ubicación
            if loc_real == 'BODEGA':
                # Descontar de la tabla 'productos'
                run_query(cursor, "SELECT cantidad FROM productos WHERE sku = ? AND ubicacion = ? AND sucursal = ?", (sku_real, loc_real, sucursal))
                prod_row = cursor.fetchone()
                if prod_row:
                    run_query(cursor, "UPDATE productos SET cantidad = cantidad - 1 WHERE sku = ? AND ubicacion = ? AND sucursal = ?", (sku_real, loc_real, sucursal))
                else:
                    logger.warning(f"Equipo {sn} en BODEGA pero no hay stock en tabla productos.")
            else:
                # Descontar de la tabla 'asignacion_moviles' (Móvil)
                sql_asig = "SELECT cantidad FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?"
                run_query(cursor, sql_asig, (sku_real, loc_real, pq_real, sucursal))
                asig_row = cursor.fetchone()
                
                if asig_row:
                    nueva_qty = max(0, float(asig_row[0]) - 1)
                    if nueva_qty > 0:
                        run_query(cursor, "UPDATE asignacion_moviles SET cantidad = ? WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?",
                                       (nueva_qty, sku_real, loc_real, pq_real, sucursal))
                    else:
                        run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?",
                                       (sku_real, loc_real, pq_real, sucursal))
                else:
                    logger.warning(f"Equipo {sn} en {loc_real} pero no hay stock en tabla asignacion_moviles.")
            
            # Registrar Movimiento
            run_query(cursor, """
                INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, 
                                       fecha_evento, observaciones, sucursal) 
                VALUES (?, ?, 1, ?, ?, ?, ?)
            """, (sku_real, TIPO_MOVIMIENTO_DESCARTE, loc_real, fecha_evento, f"{obs} [Desde: {loc_real}]", sucursal))
            
            # Actualizar la serie
            run_query(cursor, "UPDATE series_registradas SET ubicacion = ?, estado = ? WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?",
                        (UBICACION_DESCARTE, 'DESCARTE', sn, sn, sucursal))
                        
            # Asegurar que el inventario contable en DESCARTE se incremente
            run_query(cursor, "SELECT sku FROM productos WHERE sku = ? AND ubicacion = ? AND sucursal = ?", (sku_real, UBICACION_DESCARTE, sucursal))
            descarte_existe = cursor.fetchone()
            if descarte_existe:
                run_query(cursor, "UPDATE productos SET cantidad = cantidad + 1 WHERE sku = ? AND ubicacion = ? AND sucursal = ?", 
                                (sku_real, UBICACION_DESCARTE, sucursal))
            else:
                # Corregido: 'secuencia' -> 'secuencia_vista'
                run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, sucursal) SELECT nombre, sku, 1, ?, '99z', ? FROM productos WHERE sku = ? LIMIT 1", 
                               (UBICACION_DESCARTE, sucursal, sku_real))
            
            exitos += 1
            
        conn.commit()
        if exitos == 0:
            return False, f"Ningún equipo procesado. Errores: {', '.join(errores)}"
        elif errores:
            return True, f"Parcialmente exitoso. Se dañaron {exitos} equipos. Errores: {', '.join(errores)}"
            
        return True, "Dañado(s) registrado(s) correctamente."
        
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error en registrar_danado_directo para equipos: {e}")
        return False, str(e)
    finally:
        if conn: close_connection(conn)

def registrar_consumo_directo(sku, cantidad, movil, tecnico, ayudante=None, ticket=None, colilla=None, fecha_evento=None, seriales=None, observaciones=None, tipo_custom=None, target_db=None, sucursal_context=None, paquete=None):
    """
    Registra un consumo directo desde BODEGA para la sucursal de Santiago o Móvil.
    """
    conn = None
    try:
        conn = get_db_connection(target_db=target_db)
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        from datetime import date
        if not fecha_evento: fecha_evento = date.today().isoformat()

        # SUCURSAL CONTEXTO
        import os
        sucursal = sucursal_context or ('SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI')

        # 1. Verificar stock en BODEGA (AISLADO)
        run_query(cursor, "SELECT cantidad, nombre FROM productos WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (sku, sucursal))
        res = cursor.fetchone()
        if not res:
            return False, f"El producto {sku} no existe en Bodega {sucursal}."
        
        stock_actual, nombre_prod = res
        if stock_actual < cantidad:
            return False, f"Stock insuficiente en Bodega {sucursal} ({stock_actual} disponibles)."
            
        # 2. Restar de Bodega
        run_query(cursor, "UPDATE productos SET cantidad = cantidad - ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (cantidad, sku, sucursal))
        
        # 3. Registrar Movimiento
        tipo_mov = tipo_custom if tipo_custom else 'CONSUMO_DIRECTO'
        obs_mov = observaciones or f"Consumo Directo Santiago - Ticket: {ticket}"
        
        # SUCURSAL CONTEXTO
        import os
        sucursal = sucursal_context or ('SANTIAGO' if os.environ.get('SANTIAGO_DIRECT_MODE') == '1' else 'CHIRIQUI')

        sql_mov = """
            INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, 
                                   fecha_evento, observaciones, documento_referencia, sucursal) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        run_query(cursor, sql_mov, (sku, tipo_mov, cantidad, movil, fecha_evento, obs_mov, ticket, sucursal))
        
        # 4. Registrar en consumos_pendientes (Audit Trail)
        seriales_json = json.dumps(seriales) if seriales else None
        pq_final = paquete if paquete else 'NINGUNO'
        
        # En consumos_pendientes, el ticket se guarda en 'ticket' y 'num_contrato'
        run_query(cursor, """
            INSERT INTO consumos_pendientes 
            (movil, sku, cantidad, tecnico_nombre, ayudante_nombre, ticket, fecha, colilla, num_contrato, seriales_usados, estado, paquete, sucursal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AUTO_APROBADO', ?, ?)
        """, (movil, sku, cantidad, tecnico, ayudante or '', ticket, fecha_evento, colilla or '', ticket, seriales_json, pq_final, sucursal))
        
        # 5. Manejar Seriales
        if seriales:
            # Si es descarte, marcamos como tal, si no como consumido (Baja)
            new_loc = 'CONSUMIDO'
            new_status = 'BAJA'
            if tipo_mov == 'DESCARTE':
                new_loc = 'DESCARTE'
                new_status = 'DESCARTE'
                
            for sn in seriales:
                # Actualizar tanto por serial como por MAC por seguridad
                run_query(cursor, "UPDATE series_registradas SET ubicacion = ?, estado = ? WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?", 
                          (new_loc, new_status, sn, sn, sucursal))
                
        conn.commit()
        return True, f"Consumo directo de {cantidad} {nombre_prod} registrado exitosamente."
        
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error en registrar_consumo_directo: {e}")
        return False, str(e)
    finally:
        if conn: close_connection(conn)

def verificar_seriales_bodega(seriales, sucursal_context='CHIRIQUI', target_db=None):
    """
    Verifica si una lista de seriales existe en la BODEGA de la sucursal especificada.
    Retorna (True, None) si todos existen, o (False, mensaje) con los faltantes.
    """
    if not seriales: return True, None
    conn = None
    try:
        conn = get_db_connection(target_db=target_db)
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sucursal = sucursal_context.upper()
        faltantes = []
        for sn in seriales:
            clean_sn = sn.strip().upper()
            sql = """
                SELECT id FROM series_registradas 
                WHERE (UPPER(serial_number) = ? OR UPPER(mac_number) = ?) 
                AND ubicacion = 'BODEGA' 
                AND sucursal = ?
            """
            run_query(cursor, sql, (clean_sn, clean_sn, sucursal))
            if not cursor.fetchone():
                faltantes.append(sn)
        
        if faltantes:
            return False, f"Los siguientes seriales/MACs no están registrados en Bodega {sucursal}: {', '.join(faltantes)}"
        
        return True, None
    except Exception as e:
        logger.error(f"Error en verificar_seriales_bodega: {e}")
        return False, f"Error de validación: {e}"
    finally:
        if conn: close_connection(conn)

