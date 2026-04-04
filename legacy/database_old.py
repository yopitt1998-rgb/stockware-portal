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

        # MIGRACIÓN: Renombrar CALCAMONIA a Sticker (SKU 2-7-07)
        try:
            run_query(cursor, "UPDATE productos SET nombre = 'Sticker' WHERE sku = '2-7-07'")
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

        # 11. TABLA TECNICOS (NUEVO)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS tecnicos (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
                nombre VARCHAR(255) NOT NULL UNIQUE,
                activo INTEGER DEFAULT 1,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 10. TABLA FALTANTES (NUEVO - Historial de Discrepancias)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS faltantes_registrados (
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
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
                id {INT_TYPE} PRIMARY KEY {AUTOINC},
                faltante_id {INT_TYPE} NOT NULL,
                serial VARCHAR(255) NOT NULL,
                FOREIGN KEY (faltante_id) REFERENCES faltantes_registrados(id)
            )
        """)

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

        # Migración faltantes_registrados: añadir paquete
        try:
            if DB_TYPE == 'MYSQL':
                cursor.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'faltantes_registrados' AND column_name = 'paquete'")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("ALTER TABLE faltantes_registrados ADD COLUMN paquete VARCHAR(100) DEFAULT 'NINGUNO'")
            else:
                cursor.execute("PRAGMA table_info(faltantes_registrados)")
                cols = [c[1] for c in cursor.fetchall()]
                if 'paquete' not in cols:
                    cursor.execute("ALTER TABLE faltantes_registrados ADD COLUMN paquete TEXT DEFAULT 'NINGUNO'")
        except Exception as e:
            logger.warning(f"Error migrando faltantes_registrados (paquete): {e}")

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
    """
    try:
        from config import CURRENT_CONTEXT
        sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        with db_session() as (conn, cursor):
            run_query(cursor, "SELECT cantidad FROM productos WHERE sku = ? AND ubicacion = ? AND sucursal = ?", (sku, ubicacion, sucursal))
            res = cursor.fetchone()
            if not res:
                return False, 0
            stock_actual = res[0]
            return stock_actual >= cantidad_requerida, stock_actual
    except Exception as e:
        logger.error(f"Error en verificar_stock_disponible: {e}")
        return False, 0

def registrar_movimiento_gui(sku, tipo_movimiento, cantidad_afectada, movil_afectado=None, fecha_evento=None, paquete_asignado=None, observaciones=None, documento_referencia=None, target_db_name=None, existing_conn=None, sucursal_context=None, seriales=None):
    """
    Registra un movimiento, actualiza la cantidad en Bodega/Asignación y maneja la ubicación DESCARTE.
    """
    try:
        # Validación de entrada
        sku = validate_sku(sku)
        cantidad_afectada = validate_quantity(cantidad_afectada, allow_zero=False, allow_negative=False)
        if movil_afectado:
            if movil_afectado.upper() == 'SANTIAGO':
                movil_afectado = 'SANTIAGO'
            else:
                from config import CURRENT_CONTEXT
                movil_afectado = validate_movil(movil_afectado, CURRENT_CONTEXT['MOVILES'])
        
        if observaciones:
            observaciones = validate_observaciones(observaciones)
        
        if seriales:
            seriales_str = ", ".join(seriales)
            observaciones = f"{observaciones} | Series: {seriales_str}" if observaciones else f"Series: {seriales_str}"
                
        if not fecha_evento: 
             return False, "Error de Fecha: La fecha del evento es obligatoria."
        
        if paquete_asignado in ("NINGUNO", "PERSONALIZADO"):
             if paquete_asignado == "NINGUNO":
                 paquete_asignado = None
        
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

        paquete_para_stock = paquete_asignado
        
        with db_session(target_db=target_db_name, existing_conn=existing_conn) as (conn, cursor):
            run_query(cursor, "SELECT cantidad, nombre, secuencia_vista FROM productos WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (sku, sucursal))
            resultado_bodega = cursor.fetchone()
            
            if not resultado_bodega:
                run_query(cursor, "SELECT 0, nombre, secuencia_vista FROM productos WHERE sku = ? AND ubicacion = 'BODEGA' LIMIT 1", (sku,))
                resultado_bodega = cursor.fetchone()

            if not resultado_bodega:
                if tipo_movimiento not in ('ENTRADA', 'ABASTO'):
                    return False, f"Producto con SKU '{sku}' no encontrado en BODEGA (ni local {sucursal} ni global)."
                else:
                    stock_bodega_actual = 0
                    temp_data = next(((n, s) for n, current_sku, s in PRODUCTOS_INICIALES if current_sku == sku), (f"Producto temporal {sku}", '999'))
                    nombre_producto, secuencia_vista = temp_data
            else:
                stock_bodega_actual, nombre_producto, secuencia_vista = resultado_bodega
            
            stock_asignado = 0
            if movil_afectado and tipo_movimiento in ('SALIDA_MOVIL', 'RETORNO_MOVIL', 'CONSUMO_MOVIL'):
                 is_shared = sku in MATERIALES_COMPARTIDOS
                 
                 if (tipo_movimiento in ('CONSUMO_MOVIL', 'RETORNO_MOVIL') and not paquete_asignado) or is_shared:
                     sql_asig = "SELECT COALESCE(SUM(cantidad), 0) FROM asignacion_moviles WHERE sku_producto = ? AND UPPER(TRIM(movil)) = UPPER(TRIM(?)) AND sucursal = ?"
                     run_query(cursor, sql_asig, (sku, movil_afectado, sucursal))
                     asignacion_actual = cursor.fetchone()
                     stock_asignado = float(asignacion_actual[0]) if asignacion_actual and asignacion_actual[0] is not None else 0
                 else:
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
            elif tipo_movimiento == 'SALIDA':
                if stock_bodega_actual < cantidad_afectada:
                    return False, f"Stock insuficiente en Bodega para {nombre_producto}. Solo hay {stock_bodega_actual} unidades."
                cantidad_bodega_cambio = -cantidad_afectada

            if cantidad_bodega_cambio != 0:
                if cantidad_bodega_cambio < 0:
                    abs_cambio = abs(cantidad_bodega_cambio)
                    rc = run_query(cursor, "UPDATE productos SET cantidad = cantidad - ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ? AND cantidad >= ?", 
                                   (abs_cambio, sku, sucursal, abs_cambio))
                    if rc == 0:
                         return False, f"Error atómico: Stock insuficiente en Bodega para {nombre_producto}. Probablemente modificado por otra sesión."
                else:
                    run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", 
                                   (cantidad_bodega_cambio, sku, sucursal))
            
            if seriales:
                if tipo_movimiento == 'CONSUMO_MOVIL' or tipo_movimiento == 'SALIDA':
                    for s in seriales:
                        run_query(cursor, "UPDATE series_registradas SET estado = 'CONSUMIDO', ubicacion = 'CONSUMIDO' WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?", (s, s, sucursal))
                elif tipo_movimiento == 'SALIDA_MOVIL' and movil_afectado:
                    for s in seriales:
                        run_query(cursor, "UPDATE series_registradas SET ubicacion = ?, paquete = ?, estado = 'ASIGNADO' WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?", (movil_afectado, paquete_asignado or 'NINGUNO', s, s, sucursal))
                elif tipo_movimiento == 'RETORNO_MOVIL':
                    for s in seriales:
                        run_query(cursor, "UPDATE series_registradas SET ubicacion = 'BODEGA', paquete = 'NINGUNO', estado = 'DISPONIBLE' WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?", (s, s, sucursal))

            if cantidad_descarte_cambio > 0:
                run_query(cursor, "SELECT sku FROM productos WHERE sku = ? AND ubicacion = ? AND sucursal = ?", (sku, UBICACION_DESCARTE, sucursal))
                descarte_existe = cursor.fetchone()
                if descarte_existe:
                     run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = ? AND sucursal = ?",
                                    (cantidad_descarte_cambio, sku, UBICACION_DESCARTE, sucursal))
                else:
                    run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, sucursal) VALUES (?, ?, ?, ?, ?, ?)",
                                   (nombre_producto, sku, cantidad_descarte_cambio, UBICACION_DESCARTE, f'{secuencia_vista}z', sucursal))

            if movil_afectado and cantidad_asignacion_cambio != 0:
                 is_shared = sku in MATERIALES_COMPARTIDOS
                 if (tipo_movimiento in ('CONSUMO_MOVIL', 'RETORNO_MOVIL')) and cantidad_asignacion_cambio < 0 and (not paquete_asignado or is_shared):
                     sql_rows = "SELECT COALESCE(paquete, 'NINGUNO'), cantidad FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND sucursal = ? AND cantidad > 0 ORDER BY cantidad DESC"
                     run_query(cursor, sql_rows, (sku, movil_afectado, sucursal))
                     filas_con_stock = cursor.fetchall()
                     pendiente_descontar = abs(cantidad_asignacion_cambio)
                     for fila_pq, fila_qty in filas_con_stock:
                         if pendiente_descontar <= 0: break
                         descontar_de_fila = min(fila_qty, pendiente_descontar)
                         nueva_qty_fila = fila_qty - descontar_de_fila
                         pendiente_descontar -= descontar_de_fila
                         if nueva_qty_fila > 0:
                             run_query(cursor, "UPDATE asignacion_moviles SET cantidad = ? WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (nueva_qty_fila, sku, movil_afectado, fila_pq, sucursal))
                         else:
                             run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (sku, movil_afectado, fila_pq, sucursal))
                 else:
                     pq_actual = paquete_para_stock if paquete_para_stock else 'NINGUNO'
                     sql_sel = "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?"
                     run_query(cursor, sql_sel, (sku, movil_afectado, pq_actual, sucursal))
                     resultado_asignacion = cursor.fetchone()
                     valor_actual = float(resultado_asignacion[0]) if resultado_asignacion and resultado_asignacion[0] is not None else 0.0
                     nueva_cantidad_asignacion = max(0, valor_actual + cantidad_asignacion_cambio)
                     
                     if DB_TYPE == 'MYSQL':
                         sql_upsert = "INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad, sucursal) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad)"
                         if nueva_cantidad_asignacion > 0:
                             cursor.execute(sql_upsert, (sku, movil_afectado, pq_actual, nueva_cantidad_asignacion, sucursal))
                         else:
                             run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (sku, movil_afectado, pq_actual, sucursal))
                     else:
                         run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (sku, movil_afectado, pq_actual, sucursal))
                         if nueva_cantidad_asignacion > 0:
                             run_query(cursor, "INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad, sucursal) VALUES (?, ?, ?, ?, ?)", (sku, movil_afectado, pq_actual, nueva_cantidad_asignacion, sucursal))

            sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia, sucursal) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            run_query(cursor, sql_mov, (sku, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia, sucursal))

            if tipo_movimiento in ['RETORNO_MOVIL', 'CONSUMO_MOVIL'] and movil_afectado and paquete_asignado in ['PAQUETE A', 'PAQUETE B']:
                tipo_recordatorio = 'RETORNO' if tipo_movimiento == 'RETORNO_MOVIL' else 'CONCILIACION'
                run_query(cursor, "UPDATE recordatorios_pendientes SET completado = 1, fecha_completado = CURRENT_TIMESTAMP WHERE movil = ? AND paquete = ? AND tipo_recordatorio = ? AND fecha_recordatorio = ? AND completado = 0", (movil_afectado, paquete_asignado, tipo_recordatorio, fecha_evento))
        
        movil_msg = f" a/desde el {movil_afectado}" if movil_afectado else ""
        paquete_msg = f" (Paq: {paquete_asignado})" if paquete_asignado else ""
        return True, f"✅ Movimiento {tipo_movimiento} registrado para SKU {sku} ({cantidad_afectada} unidades){movil_msg}{paquete_msg}."

    except Exception as e:
        logger.error(f"Error en registrar_movimiento_gui para SKU {sku}: {e}")
        return False, f"Error en la base de datos: {str(e)}"

# FUNCIONES PARA PRÉSTAMOS SANTIAGO
def registrar_prestamo_santiago(sku, cantidad, fecha_evento, observaciones=None):
    """
    Registra una TRANSFERENCIA desde Bodega Local a Santiago.
    """
    try:
        from utils.validators import validate_sku, validate_quantity
        sku = validate_sku(sku)
        cantidad = validate_quantity(cantidad)
        
        with db_session() as (conn, cursor):
            # 1. Registrar SALIDA desde Bodega Local (CHIRIQUI context)
            suc_local = 'CHIRIQUI' # Por definición los préstamos salen de David
            
            exito_local, msg_local = registrar_movimiento_gui(
                sku, 'SALIDA', cantidad, None, fecha_evento, 
                observaciones=f"Préstamo a Santiago: {observaciones or ''}",
                sucursal_context=suc_local,
                existing_conn=conn
            )
            
            if not exito_local:
                return False, f"Fallo en salida local: {msg_local}"
                
            # 2. Registrar ENTRADA en Bodega Santiago
            exito_santiago, msg_santiago = registrar_movimiento_gui(
                sku, 'ABASTO', cantidad, None, fecha_evento,
                observaciones=f"Préstamo recibido de David: {observaciones or ''}",
                sucursal_context='SANTIAGO',
                existing_conn=conn
            )
            
            if not exito_santiago:
                raise Exception(f"Fallo en entrada Santiago: {msg_santiago}")
                
            return True, "Préstamo registrado exitosamente en ambas sucursales."
            
    except Exception as e:
        logger.error(f"Error en registrar_prestamo_santiago: {e}")
        return False, f"Error: {e}"

def registrar_devolucion_santiago(sku, cantidad, seriales_nuevos, fecha_evento, observaciones=None):
    """
    Registra una devolución desde Santiago a Bodega Local.
    """
    try:
        sku = validate_sku(sku)
        cantidad = validate_quantity(cantidad, allow_zero=False, allow_negative=False)
        if observaciones:
            from utils.validators import validate_observaciones
            observaciones = validate_observaciones(observaciones)
            
        with db_session() as (conn, cursor):
            # 1. Verificar stock asignado a SANTIAGO (usando la conexión atómica)
            run_query(cursor, "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = ? AND movil = 'SANTIAGO'", (sku,))
            res = cursor.fetchone()
            stock_santiago = float(res[0]) if res and res[0] else 0.0

            if stock_santiago < cantidad:
                return False, f"Santiago solo tiene {stock_santiago} unidades asignadas de '{sku}'. No se puede devolver {cantidad}."

            # 2. Descontar de asignacion_moviles SANTIAGO
            # Reutilizamos registrar_movimiento_gui para mayor consistencia
            exito_salida, msg_salida = registrar_movimiento_gui(
                sku, 'RETORNO_MOVIL', cantidad, 'SANTIAGO', fecha_evento,
                observaciones=f"DEVOLUCIÓN A BODEGA: {observaciones or ''}",
                sucursal_context='CHIRIQUI', # El retorno se procesa en el contexto receptor
                existing_conn=conn
            )
            
            if not exito_salida:
                return False, f"Error en retorno Santiago: {msg_salida}"

            # 3. Registrar seriales nuevos en Bodega (si los hay)
            if seriales_nuevos:
                for serial in seriales_nuevos:
                    if not serial: continue
                    run_query(cursor, "SELECT id FROM series_registradas WHERE (serial_number = ? OR mac_number = ?)", (serial, serial))
                    existe = cursor.fetchone()
                    if existe:
                        run_query(cursor, "UPDATE series_registradas SET ubicacion = 'BODEGA', paquete = 'NINGUNO', estado = 'DISPONIBLE' WHERE (serial_number = ? OR mac_number = ?)", (serial, serial))
                    else:
                        run_query(cursor, "INSERT INTO series_registradas (sku, serial_number, ubicacion, fecha_ingreso, paquete, estado, sucursal) VALUES (?, ?, 'BODEGA', ?, 'NINGUNO', 'DISPONIBLE', 'CHIRIQUI')", (sku, serial, fecha_evento))

            return True, f"Devolución registrada: {cantidad} unidades de '{sku}' desde Santiago a Bodega."

    except Exception as e:
        logger.error(f"Error en registrar_devolucion_santiago: {e}")
        return False, f"Error al registrar devolución: {e}"


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
    try:
        with db_session() as (conn, cursor):
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
                return True
        return False
    except Exception as e:
        logger.error(f"Error al crear recordatorio: {e}")
        return False

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
    try:
        with db_session() as (conn, cursor):
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

def marcar_recordatorio_completado(id_recordatorio):
    """
    Marca un recordatorio como completado.
    """
    try:
        with db_session() as (conn, cursor):
            run_query(cursor, """
                UPDATE recordatorios_pendientes 
                SET completado = 1, fecha_completado = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (id_recordatorio,))
            return True
    except Exception as e:
        logger.error(f"Error al marcar recordatorio como completado: {e}")
        return False

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
        
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

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

def sincronizar_stock_bodega_serializado(sucursal_context=None, target_db=None):
    """
    Sincroniza la columna 'cantidad' de la tabla 'productos' (ubicacion='BODEGA')
    con el conteo real de series en 'series_registradas' (estado='DISPONIBLE', ubicacion='BODEGA').
    Solo para SKUs en PRODUCTOS_CON_CODIGO_BARRA.
    """
    conn = None
    try:
        from config import PRODUCTOS_CON_CODIGO_BARRA, CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
        conn = get_db_connection(target_db=target_db)
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()

        logger.info(f"Sincronizando stock serializado para sucursal: {sucursal}")
        
        # 1. Obtener conteo real desde series_registradas
        sql_counts = """
            SELECT sku, COUNT(*) as real_qty
            FROM series_registradas
            WHERE ubicacion = 'BODEGA' AND estado = 'DISPONIBLE' AND sucursal = ?
            AND sku IN ({})
            GROUP BY sku
        """.format(','.join(['?'] * len(PRODUCTOS_CON_CODIGO_BARRA)))
        
        params = [sucursal] + PRODUCTOS_CON_CODIGO_BARRA
        run_query(cursor, sql_counts, tuple(params))
        real_stock = {sku: qty for sku, qty in cursor.fetchall()}
        
        # 2. Asegurar que todos los productos serializados tengan una entrada en 'productos' para esa sucursal
        for sku in PRODUCTOS_CON_CODIGO_BARRA:
            qty = real_stock.get(sku, 0)
            
            # Ver si existe la entrada en productos
            run_query(cursor, "SELECT cantidad FROM productos WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (sku, sucursal))
            row = cursor.fetchone()
            
            if row is not None:
                if row[0] != qty:
                    run_query(cursor, "UPDATE productos SET cantidad = ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (qty, sku, sucursal))
                    logger.info(f"Stock sincronizado para {sku} en {sucursal}: {row[0]} -> {qty}")
            else:
                run_query(cursor, "SELECT nombre, secuencia_vista FROM productos WHERE sku = ? LIMIT 1", (sku,))
                meta = cursor.fetchone()
                if not meta:
                    from config import PRODUCTOS_INICIALES
                    temp_data = next(((n, s) for n, current_sku, s in PRODUCTOS_INICIALES if current_sku == sku), (f"Producto {sku}", '999'))
                    nombre, secuencia = temp_data
                else:
                    nombre, secuencia = meta
                
                run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista, sucursal) VALUES (?, ?, ?, ?, ?, ?)",
                               (nombre, sku, qty, "BODEGA", secuencia, sucursal))
                logger.info(f"Creada entrada de stock para {sku} en {sucursal} con qty {qty}")
                
        if not target_db:
            conn.commit()
            
        return True
    except Exception as e:
        logger.error(f"Error al sincronizar stock serializado: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: close_connection(conn)

def obtener_ultima_salida_movil(movil):
    """Obtiene todo el inventario actualmente asignado al móvil, reemplazando la lógica de solo la última salida."""
    try:
        asignaciones = obtener_asignacion_movil_con_paquetes(movil)
        return [(item[1], item[2]) for item in asignaciones if item[2] > 0]
    except Exception as e:
        logger.error(f"Error en obtener_ultima_salida_movil (ahora usa asignacion completa): {e}")
        return []

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
        from config import CURRENT_CONTEXT
        sucursal_target = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

        # Usamos LEFT JOIN para que no desaparezcan items si falla el cruce de productos maestro
        sql_total = """
            SELECT p.nombre, a.sku_producto, SUM(a.cantidad) as total, p.secuencia_vista
            FROM asignacion_moviles a
            LEFT JOIN (SELECT sku, MAX(nombre) as nombre, MAX(secuencia_vista) as secuencia_vista FROM productos GROUP BY sku) p ON a.sku_producto = p.sku
            WHERE UPPER(TRIM(a.movil)) = UPPER(TRIM(?)) AND a.cantidad > 0 
            AND (UPPER(TRIM(a.sucursal)) = ? OR a.sucursal IS NULL OR a.sucursal = '')
            GROUP BY a.sku_producto, p.nombre, p.secuencia_vista
        """
        run_query(cursor, sql_total, (movil, sucursal_target))
        productos_asignados_raw = cursor.fetchall()
        
        # Ordenamos en Python para evitar problemas con SQLite/MySQL orderBy handling con NULLs
        def sort_key(row):
            seq = row[3]
            try: return int(seq)
            except: return 9999
            
        productos_asignados_raw.sort(key=sort_key)
        
        productos_asignados = []
        for row in productos_asignados_raw:
            nombre = row[0] if row[0] else f"Desconocido ({row[1]})"
            productos_asignados.append((nombre, row[1], row[2]))

        if not productos_asignados:
            return []

        # --- NUEVO: Encontrar el punto de corte (última limpieza total) ---
        # Solo procesamos movimientos posteriores a la última limpieza del móvil para evitar stock "fantasma"
        sql_last_clean = """
            SELECT MAX(id) FROM movimientos 
            WHERE UPPER(TRIM(movil_afectado)) = UPPER(TRIM(?)) 
            AND tipo_movimiento = 'LIMPIEZA_MOVIL' 
            AND (paquete_asignado = 'TODOS' OR paquete_asignado IS NULL)
            AND (sucursal = ? OR (sucursal IS NULL AND ? = 'CHIRIQUI'))
        """
        run_query(cursor, sql_last_clean, (movil, sucursal_target, sucursal_target))
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
            AND (sucursal = ? OR (sucursal IS NULL AND ? = 'CHIRIQUI'))
            ORDER BY fecha_movimiento ASC, id ASC
        """
        run_query(cursor, sql_todos_movs, (movil, last_cleaning_id, sucursal_target, sucursal_target))
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
    try:
        from config import MOVILES_SANTIAGO
        sucursal = 'SANTIAGO' if movil in MOVILES_SANTIAGO else 'CHIRIQUI'
        
        with db_session() as (conn, cursor):
            run_query(cursor, """
                INSERT INTO consumos_pendientes (movil, sku, cantidad, tecnico_nombre, ayudante_nombre, ticket, fecha, colilla, num_contrato, paquete, sucursal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (movil, sku, cantidad, tecnico, ayudante, ticket, fecha, colilla, contrato, paquete or 'NINGUNO', sucursal))
            return True, "Registro guardado"
    except Exception as e:
        logger.error(f"Error en registrar_consumo_pendiente: {e}")
        return False, str(e)

def eliminar_consumo_pendiente(id_consumo):
    """Elimina un consumo pendiente específico por su ID."""
    try:
        with db_session() as (conn, cursor):
            run_query(cursor, "DELETE FROM consumos_pendientes WHERE id = ?", (id_consumo,))
            return True, "Registro eliminado correctamente."
    except Exception as e:
        logger.error(f"Error en eliminar_consumo_pendiente: {e}")
        return False, f"Error al eliminar registro: {e}"

def eliminar_consumos_pendientes_por_movil(movil):
    """Elimina todos los consumos pendientes de un móvil específico."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
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
    Si estado='TODOS', consolida datos de consumos_pendientes y la tabla de movimientos (Historial).
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # DETERMINAR FILTRO DE SUCURSAL/MOVILES PARA AMBAS TABLAS
        from config import CURRENT_CONTEXT
        sucursal_actual = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        target_moviles = moviles_filtro if moviles_filtro else CURRENT_CONTEXT.get('MOVILES', [])
        
        def build_query(table_type):
            if table_type == 'consumos':
                sql = """
                    SELECT c.id, c.movil, c.sku, COALESCE(p.nombre, '(SKU sin maestro)') as nombre, c.cantidad, c.tecnico_nombre, c.ticket, 
                           c.fecha, c.colilla, c.num_contrato, c.ayudante_nombre, c.seriales_usados, c.paquete, c.estado
                    FROM consumos_pendientes c
                    LEFT JOIN productos p ON c.sku = p.sku AND p.ubicacion = 'BODEGA' 
                    AND (p.sucursal = c.sucursal OR p.sucursal IS NULL)
                    WHERE 1=1
                """
                table_alias = "c"
                movil_col = "movil"
                date_col = "fecha"
                pq_col = "paquete"
                sucursal_col = "sucursal"
            else: # movimientos
                sql = """
                    SELECT m.id, m.movil_afectado as movil, m.sku_producto as sku, COALESCE(p.nombre, '(Histórico/Sin maestro)') as nombre, m.cantidad_afectada as cantidad, 
                           'Procesado Manual/Auto' as tecnico_nombre, m.documento_referencia as ticket, 
                           m.fecha_evento as fecha, '' as colilla, m.documento_referencia as num_contrato, 
                           '' as ayudante_nombre, '' as seriales_usados, m.paquete_asignado as paquete, 'PROCESADO' as estado
                    FROM movimientos m
                    LEFT JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA' AND (p.sucursal = m.sucursal OR p.sucursal IS NULL)
                    WHERE m.tipo_movimiento = 'CONSUMO_MOVIL'
                    AND m.movil_afectado NOT IN ('BODEGA', 'SANTIAGO', 'DESCARTE')
                """
                table_alias = "m"
                movil_col = "movil_afectado"
                date_col = "fecha_evento"
                pq_col = "paquete_asignado"
                sucursal_col = "sucursal"


            q_params = []
            
            # Filtro por móviles de la sucursal (o filtro manual)
            if target_moviles:
                placeholders = ','.join(['?' for _ in target_moviles])
                sql += f" AND {table_alias}.{movil_col} IN ({placeholders})"
                q_params.extend(target_moviles)
            elif sucursal_actual:
                 # Si no hay móviles específicos, al menos filtrar por sucursal si la tabla lo tiene
                 sql += f" AND {table_alias}.{sucursal_col} = ?"
                 q_params.append(sucursal_actual)

            # Filtro de fecha
            if fecha_inicio and fecha_fin:
                sql += f" AND {table_alias}.{date_col} >= ? AND {table_alias}.{date_col} <= ?"
                q_params.extend([fecha_inicio, f"{fecha_fin} 23:59:59"])
            elif fecha_inicio:
                sql += f" AND {table_alias}.{date_col} >= ?"
                q_params.append(fecha_inicio)
            elif fecha_fin:
                sql += f" AND {table_alias}.{date_col} <= ?"
                q_params.append(f"{fecha_fin} 23:59:59")
                
            # Filtro de paquete
            if paquete and paquete != 'TODOS':
                sql += f" AND COALESCE(UPPER(TRIM({table_alias}.{pq_col})), 'NINGUNO') = ?"
                q_params.append(paquete.strip().upper())
                
            return sql, q_params

        # CONSTRUCCIÓN DE LA CONSULTA FINAL
        params = []
        if estado == 'TODOS':
            sql_c, params_c = build_query('consumos')
            sql_m, params_m = build_query('movimientos')
            
            # Unir ambas tablas
            sql_query = f"({sql_c}) UNION ALL ({sql_m}) ORDER BY fecha DESC"
            params = params_c + params_m
        else:
            sql_query, params = build_query('consumos')
            
            # Filtro de estado para la tabla consumos_pendientes
            if estado:
                sql_query += " AND estado = ?"
                params.append(estado)
            else:
                sql_query += " AND estado IN ('PENDIENTE', 'AUTO_APROBADO')"
            
            sql_query += " ORDER BY fecha DESC"

        if limite:
            sql_query += f" LIMIT {int(limite)}"

        run_query(cursor, sql_query, tuple(params))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener consumos pendientes: {e}")
        return []
    finally:
        if conn: close_connection(conn)


def obtener_tecnicos(solo_activos=False):
    """Retorna una lista de técnicos [(id, nombre, activo)]"""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql = "SELECT id, nombre, activo FROM tecnicos"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY nombre ASC"
        
        run_query(cursor, sql)
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error en obtener_tecnicos: {e}")
        return []
    finally:
        if conn: close_connection(conn)

def crear_tecnico(nombre):
    """Crea un nuevo técnico."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        run_query(cursor, "INSERT INTO tecnicos (nombre) VALUES (?)", (nombre,))
        conn.commit()
        return True, f"Técnico '{nombre}' creado."
    except Exception as e:
        return False, str(e)
    finally:
        if conn: close_connection(conn)

def editar_tecnico(id_tecnico, nuevo_nombre):
    """Actualiza el nombre de un técnico."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        run_query(cursor, "UPDATE tecnicos SET nombre = ? WHERE id = ?", (nuevo_nombre, id_tecnico))
        conn.commit()
        return True, "Técnico actualizado."
    except Exception as e:
        return False, str(e)
    finally:
        if conn: close_connection(conn)

def eliminar_tecnico(id_tecnico, permanentemente=False):
    """Elimina o desactiva un técnico."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if permanentemente:
            run_query(cursor, "DELETE FROM tecnicos WHERE id = ?", (id_tecnico,))
        else:
            run_query(cursor, "UPDATE tecnicos SET activo = 0 WHERE id = ?", (id_tecnico,))
        conn.commit()
        return True, "Técnico eliminado/desactivado."
    except Exception as e:
        return False, str(e)
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
            return None

        logger.info(f"✅ Resultado encontrado: {res[2]} ({res[4]})")
        
        res_list = list(res)
        serial, mac, sku, nombre, ubicacion, estado, paquete = res_list
        
        # Inicializar info extra
        movil_final = None
        contrato_final = None
        fecha_final = None
        
        # --- PLAN A: Buscar en consumos_pendientes (Búsqueda Directa por Serial/MAC) ---
        sql_c = """
            SELECT movil, COALESCE(NULLIF(TRIM(num_contrato), ''), NULLIF(TRIM(ticket), '')), fecha 
            FROM consumos_pendientes 
            WHERE (seriales_usados LIKE ? OR seriales_usados LIKE ? OR seriales_usados LIKE ? OR seriales_usados LIKE ?)
              AND sucursal = ?
            ORDER BY id DESC LIMIT 1
        """
        pattern_s_json = f'%"{serial}"%' if serial else "%\"___NONE___\"%"
        pattern_m_json = f'%"{mac}"%' if mac else "%\"___NONE___\"%"
        pattern_s_raw = f'%{serial}%' if serial else "%___NONE___%"
        pattern_m_raw = f'%{mac}%' if mac else "%___NONE___%"
        
        run_query(cursor, sql_c, (pattern_s_json, pattern_m_json, pattern_s_raw, pattern_m_raw, sucursal_target))
        cons_extra = cursor.fetchone()
        
        if cons_extra:
            movil_final, contrato_final, fecha_final = cons_extra
            logger.info(f"   [PLAN A] Encontrado en consumos_pendientes: Movil={movil_final}, Contrato={contrato_final}, Fecha={fecha_final}")
        else:
            # --- PLAN B: Buscar en movimientos (Observaciones o Documento) ---
            sql_m = """
                SELECT movil_afectado, documento_referencia, fecha_evento 
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
                movil_final, contrato_final, fecha_final = mov_extra
                logger.info(f"   [PLAN B] Encontrado en movimientos: Movil={movil_final}, Contrato={contrato_final}, Fecha={fecha_final}")
            else:
                # --- PLAN C: Heurística por Paquete (Última salida de ese SKU/Paquete) ---
                if paquete and paquete != 'NINGUNO':
                    sql_h = """
                        SELECT movil_afectado, documento_referencia, fecha_evento 
                        FROM movimientos 
                        WHERE sku_producto = ? AND paquete_asignado = ? AND sucursal = ?
                          AND tipo_movimiento = 'SALIDA_MOVIL'
                        ORDER BY id DESC LIMIT 1
                    """
                    run_query(cursor, sql_h, (sku, paquete, sucursal_target))
                    mov_h = cursor.fetchone()
                    if mov_h:
                        movil_final, contrato_final, fecha_final = mov_h
                        logger.info(f"   [PLAN C] Heurística aplicada: Movil={movil_final}, Contrato={contrato_final}, Fecha={fecha_final}")

        # Agregar info extra al resultado (siempre 3 elementos adicionales)
        res_list.extend([movil_final, contrato_final, fecha_final])
        return tuple(res_list)

    except Exception as e:
        logger.error(f"Error en buscar_equipo_global: {e}")
        import traceback
        traceback.print_exc()
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

def registrar_series_bulk(series_data, fecha_ingreso=None, paquete=None, existing_conn=None):
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
        if existing_conn:
            conn = existing_conn
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
        if not existing_conn:
            conn.commit()
        
        # NUEVO: Sincronizar stock en la tabla productos después de un bulk exitoso
        try:
            # Identificar que sucursales se vieron afectadas
            sucursales_afectadas = list(set([d[-1] for d in data_to_insert]))
            for suc in sucursales_afectadas:
                sincronizar_stock_bodega_serializado(sucursal_context=suc)
        except Exception as e_sync:
            logger.error(f"Error en sincronización post-bulk: {e_sync}")

        return True, f"{len(data_to_insert)} items registrados correctamente."
        
    except Exception as e:
        if conn and not existing_conn: conn.rollback()
        return False, f"Error al registrar series: {e}"
    finally:
        if conn and not existing_conn: close_connection(conn)

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
        
        # Permitir seleccionar seriales que estén en la ubicación pedida O que sean FALTANTE si se pide BODEGA
        sql = """
            SELECT serial_number, mac_number 
            FROM series_registradas 
            WHERE sku = ? 
            AND (
                (UPPER(TRIM(ubicacion)) = UPPER(TRIM(?)) AND estado = 'DISPONIBLE')
                OR 
                (UPPER(TRIM(ubicacion)) = 'FALTANTE' AND UPPER(TRIM(?)) = 'BODEGA')
            )
        """
        params = [sku, ubicacion, ubicacion]
        
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


def obtener_todas_las_series_de_ubicacion(ubicacion, paquete=None):
    """
    Retorna todas las series (MACs) agrupadas por SKU para una ubicación específica.
    Optimizado para reducir round-trips en auditorías.
    
    Returns:
        Dict: { sku: [(serial, mac), ...] }
    """
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        sql = "SELECT sku, serial_number, mac_number FROM series_registradas WHERE UPPER(TRIM(ubicacion)) = UPPER(TRIM(?)) AND estado = 'DISPONIBLE'"
        params = [ubicacion]
        
        if paquete and paquete != "TODOS":
            sql += " AND (UPPER(TRIM(paquete)) = UPPER(TRIM(?)) OR paquete IS NULL OR paquete = '' OR UPPER(TRIM(paquete)) = 'NINGUNO')"
            params.append(paquete)
            
        run_query(cursor, sql, params)
        rows = cursor.fetchall()
        
        result = {}
        for sku, sn, mac in rows:
            if sku not in result: result[sku] = []
            result[sku].append((sn, mac))
        return result
        
    except Exception as e:
        logger.error(f"Error obteniendo todas las series de ubicación {ubicacion}: {e}")
        return {}
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
    Combina obtener_info_serial y obtener_sku_por_codigo_barra en una SOLA conexión y consulta.
    Optimizado para reducir el lag (handshake de red) en aplicaciones GUI.
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
        # Normalizaciones para compatibilidad de caracteres
        codigo_norm = raw_code.replace("'", "-").replace("´", "-").replace("`", "-")
        codigo_reverse = raw_code.replace("-", "'")
        
        # Búsqueda unificada con UNION ALL para máxima velocidad (1 round-trip)
        # Prioridades: 1. Serial, 2. Codigo Barra, 3. Maestro, 4. SKU
        sql = """
            SELECT sku, ubicacion, 1 as priority, 1 as is_serial FROM series_registradas 
            WHERE UPPER(serial_number) = ? OR UPPER(mac_number) = ?
            UNION ALL
            SELECT sku, NULL as ubicacion, 2 as priority, 0 as is_serial FROM productos 
            WHERE codigo_barra = ? OR codigo_barra = ?
            UNION ALL
            SELECT sku, NULL as ubicacion, 3 as priority, 0 as is_serial FROM productos 
            WHERE codigo_barra_maestro IN (?, ?, ?)
            UNION ALL
            SELECT sku, NULL as ubicacion, 4 as priority, 0 as is_serial FROM productos 
            WHERE sku = ? OR sku = ?
            ORDER BY priority ASC LIMIT 1
        """
        params = [
            raw_code, raw_code,                      # Serial/MAC
            codigo_norm, raw_code,                   # Codigo Barra
            codigo_norm, raw_code, codigo_reverse,   # Maestro
            codigo_norm, raw_code                    # SKU Directo
        ]
        
        run_query(cursor, sql, params)
        result = cursor.fetchone()
        
        if result:
            # Result: (sku, ubicacion, priority, is_serial)
            return result[0], bool(result[3]), result[1]
            
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

def obtener_diccionarios_escaneo(sucursal_context=None):
    """
    Descarga todos los seriales y códigos de barra a diccionarios en memoria.
    Optimiza drásticamente la velocidad del escáner al evitar queries por cada beep.
    Retorna: (serial_cache, barcode_cache)
    """
    conn = None
    serial_cache = {}
    barcode_cache = {}
    try:
        from config import CURRENT_CONTEXT
        sucursal_target = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()

        # 1. Cargar Seriales (MAC y Serial)
        sql_seriales = "SELECT sku, serial_number, mac_number, ubicacion FROM series_registradas WHERE sucursal = ?"
        run_query(cursor, sql_seriales, (sucursal_target,))
        for sku, s_num, m_num, ubicacion in cursor.fetchall():
            if s_num and s_num.strip():
                serial_cache[s_num.strip().upper()] = (sku, ubicacion)
            if m_num and m_num.strip():
                serial_cache[m_num.strip().upper()] = (sku, ubicacion)

        # 2. Cargar Códigos de Barra de Productos
        sql_barcodes = "SELECT sku, codigo_barra_maestro, codigo_barra FROM productos WHERE ubicacion = 'BODEGA'"
        run_query(cursor, sql_barcodes, ())
        for sku, maestro, legacy in cursor.fetchall():
            if maestro and maestro.strip():
                barcode_cache[maestro.strip().upper().replace("'", "-")] = sku
            if legacy and legacy.strip():
                barcode_cache[legacy.strip().upper().replace("'", "-")] = sku

        return serial_cache, barcode_cache

    except Exception as e:
        logger.error(f"❌ Error precargando diccionarios de escaneo: {e}")
        return {}, {}
    finally:
        if conn: close_connection(conn)


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


def registrar_abasto_batch(items_abasto, fecha_evento, numero_abasto=None, existing_conn=None):
    """
    Registra múltiples items de abasto en una sola transacción.
    """
    conn = None
    try:
        if existing_conn:
            conn = existing_conn
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
            
            # Iniciar transacción explícita
            if DB_TYPE == 'MYSQL':
                cursor.execute("START TRANSACTION")
            else:
                cursor.execute("BEGIN IMMEDIATE")
        
        total_unidades = 0
        series_globales = []
        
        # SUCURSAL CONTEXT
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
                if not existing_conn: conn.rollback()
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
        
        # 3. Registrar todas las series
        if series_globales:
            ok_s, msg_s = registrar_series_bulk(series_globales, fecha_ingreso=fecha_evento, paquete=None, existing_conn=conn)
            if not ok_s:
                if not existing_conn: conn.rollback()
                return False, msg_s
                
        if not existing_conn:
            conn.commit()
        return True, f"Abasto registrado: {len(items_abasto)} productos, {total_unidades} unidades."
        
    except Exception as e:
        if conn and not existing_conn:
            conn.rollback()
        error_msg = f"Error al registrar abasto batch: {e}"
        logger.error(error_msg)
        return False, error_msg
    finally:
        if conn and not existing_conn:
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
            sql_check = f"SELECT SUM(cantidad) FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = {ph} AND (COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} OR COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') IN ('NINGUNO', 'SIN_PAQUETE')) AND sucursal = {ph}"
            cursor.execute(sql_check, (movil_norm, paquete_norm, sucursal_active))
            res = cursor.fetchone()
            total_items = res[0] if res and res[0] else 0
            
            # 2. Eliminar asignaciones del paquete y huérfanos que fueron integrados en la auditoría
            sql_del = f"DELETE FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = {ph} AND (COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} OR COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') IN ('NINGUNO', 'SIN_PAQUETE')) AND sucursal = {ph}"
            cursor.execute(sql_del, (movil_norm, paquete_norm, sucursal_active))

            # 3. Resetear Series correspondientes al paquete -> Volver a BODEGA y paquete NINGUNO
            sql_reset_series = f"UPDATE series_registradas SET ubicacion = 'BODEGA', estado = 'DISPONIBLE', paquete = 'NINGUNO' WHERE UPPER(TRIM(ubicacion)) = {ph} AND (COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} OR COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') IN ('NINGUNO', 'SIN_PAQUETE')) AND sucursal = {ph}"
            cursor.execute(sql_reset_series, (movil_norm, paquete_norm, sucursal_active))
            
            # --- NUEVO: Limpiar Consumos Pendientes del paquete y huerfanos ---
            sql_del_cons = f"DELETE FROM consumos_pendientes WHERE UPPER(TRIM(movil)) = {ph} AND (COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') = {ph} OR COALESCE(UPPER(TRIM(paquete)), 'NINGUNO') IN ('NINGUNO', 'SIN_PAQUETE')) AND sucursal = {ph}"
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
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

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
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

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

def registrar_faltante_audit(movil, sku, cantidad, seriales=None, sucursal=None, observaciones=None, paquete=None, existing_conn=None):
    """Registra permanentemente un faltante detectado durante el retorno."""
    if not sucursal:
        from config import CURRENT_CONTEXT
        sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
    conn = None
    should_close = True
    try:
        if existing_conn:
            conn = existing_conn
            should_close = False
            cursor = conn.cursor(buffered=True) if DB_TYPE == 'MYSQL' else conn.cursor()
        else:
            conn = get_db_connection()
            cursor = conn.cursor(buffered=True) if DB_TYPE == 'MYSQL' else conn.cursor()
            
        sql = """
            INSERT INTO faltantes_registrados (movil, sku, cantidad, sucursal, observaciones, paquete)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        run_query(cursor, sql, (movil, sku, cantidad, sucursal, observaciones, paquete or 'NINGUNO'))
        
        faltante_id = cursor.lastrowid
        
        if seriales:
            for s in seriales:
                # 1. Registrar detalle
                run_query(cursor, "INSERT INTO seriales_faltantes_detalle (faltante_id, serial) VALUES (?, ?)", (faltante_id, s))
                
                # 2. Marcar serial como FALTANTE en series_registradas para que no aparezca en Bodega ni móvil
                # Usamos COALESCE para intentar con serial_number o mac_number
                run_query(cursor, """
                    UPDATE series_registradas 
                    SET ubicacion = 'FALTANTE', estado = 'FALTANTE'
                    WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?
                """, (s, s, sucursal))
        
        # 3. Restar de asignacion_moviles para mantener sincronía
        if cantidad > 0:
            # Primero intentar restar del paquete específico si se provee
            pq_update = paquete or 'NINGUNO'
            rc_asig = run_query(cursor, """
                UPDATE asignacion_moviles 
                SET cantidad = cantidad - ? 
                WHERE sku_producto = ? AND UPPER(TRIM(movil)) = UPPER(TRIM(?)) 
                AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ? AND cantidad >= ?
            """, (cantidad, sku, movil, pq_update, sucursal, cantidad))
            
            # Si no encontró en ese paquete (o cantidad insuficiente), intentar restar de CUALQUIER paquete del móvil
            if rc_asig == 0:
                # Obtener filas con stock para este SKU/móvil
                run_query(cursor, "SELECT id, cantidad FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND sucursal = ? AND cantidad > 0 ORDER BY cantidad DESC", (sku, movil, sucursal))
                filas = cursor.fetchall()
                pendiente = cantidad
                for f_id, f_qty in filas:
                    if pendiente <= 0: break
                    a_restar = min(f_qty, pendiente)
                    run_query(cursor, "UPDATE asignacion_moviles SET cantidad = cantidad - ? WHERE id = ?", (a_restar, f_id))
                    pendiente -= a_restar
                
                # Opcional: eliminar filas con cantidad 0
                run_query(cursor, "DELETE FROM asignacion_moviles WHERE cantidad <= 0 AND sku_producto = ? AND movil = ? AND sucursal = ?", (sku, movil, sucursal))
        
        logger.info(f"🚩 Faltante registrado: {movil} - {sku} x{cantidad} ({sucursal})")
        if should_close:
            conn.commit()
        return True, "Faltante registrado correctamente"
    except Exception as e:
        if conn and should_close: conn.rollback()
        logger.error(f"Error registrando faltante: {e}")
        return False, str(e)
    finally:
        if conn and should_close:
            close_connection(conn)

def registrar_faltante_manual(movil, sku, cantidad, seriales=None, paquete=None, fecha=None, observaciones=None, sucursal=None):
    """
    Registra un faltante de forma manual (fuera del proceso de retorno).
    'fecha' puede ser un string YYYY-MM-DD.
    """
    if not sucursal:
        from config import CURRENT_CONTEXT
        sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
    try:
        with db_session() as (conn, cursor):
            # Usar fecha manual si se provee, sino CURRENT_TIMESTAMP
            if fecha:
                sql = """
                    INSERT INTO faltantes_registrados (movil, sku, cantidad, sucursal, observaciones, paquete, fecha_audit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                run_query(cursor, sql, (movil, sku, cantidad, sucursal, observaciones or "Registro Manual", paquete or 'NINGUNO', fecha))
            else:
                sql = """
                    INSERT INTO faltantes_registrados (movil, sku, cantidad, sucursal, observaciones, paquete)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                run_query(cursor, sql, (movil, sku, cantidad, sucursal, observaciones or "Registro Manual", paquete or 'NINGUNO'))
            
            if seriales:
                faltante_id = cursor.lastrowid
                if not isinstance(seriales, list):
                    seriales = [seriales]
                for s in seriales:
                    run_query(cursor, "INSERT INTO seriales_faltantes_detalle (faltante_id, serial) VALUES (?, ?)", (faltante_id, s))
                    # También marcar el serial como FALTANTE en series_registradas
                    run_query(cursor, """
                        UPDATE series_registradas 
                        SET ubicacion = 'FALTANTE', estado = 'FALTANTE'
                        WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?
                    """, (s, s, sucursal))
            
            # SINCRONIZAR: Restar de asignacion_moviles
            if cantidad > 0:
                pq_norm = paquete or 'NINGUNO'
                cant_a_descontar = cantidad
                # Intentar restar del paquete objetivo
                rc = run_query(cursor, """
                    UPDATE asignacion_moviles SET cantidad = cantidad - ? 
                    WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ? AND cantidad >= ?
                """, (cant_a_descontar, sku, movil, pq_norm, sucursal, cant_a_descontar))
                
                if rc == 0:
                    # Fallback a cualquier paquete
                    run_query(cursor, "SELECT id, cantidad FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND sucursal = ? AND cantidad > 0", (sku, movil, sucursal))
                    filas_asig = cursor.fetchall()
                    for f_id, f_qty in filas_asig:
                        if cant_a_descontar <= 0: break
                        a_quitar = min(f_qty, cant_a_descontar)
                        run_query(cursor, "UPDATE asignacion_moviles SET cantidad = cantidad - ? WHERE id = ?", (a_quitar, f_id))
                        cant_a_descontar -= a_quitar
                
                # Limpiar
                run_query(cursor, "DELETE FROM asignacion_moviles WHERE cantidad <= 0 AND sku_producto = ? AND movil = ? AND sucursal = ?", (sku, movil, sucursal))

            logger.info(f"🚩 Faltante MANUAL registrado: {movil} - {sku} x{cantidad} en {paquete or 'NINGUNO'}")
            return True, "Faltante registrado correctamente"
    except Exception as e:
        logger.error(f"Error registrando faltante manual: {e}")
        return False, str(e)

def registrar_consumo_no_registrado(sku, cantidad, movil, fecha_evento, paquete=None, seriales=None, sucursal=None, observaciones=None):
    """
    Registra un consumo que el técnico olvidó reportar. 
    A diferencia del consumo normal, este asume que el equipo YA no está en el móvil 
    o bodega y regulariza el stock deduciéndolo de la última posición conocida.
    """
    if not sucursal:
        from config import CURRENT_CONTEXT
        sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
    if not observaciones:
        observaciones = "Consumo NO REGISTRADO (Reportado externamente)"
    
    try:
        # Si hay seriales, intentar detectar la ubicación REAL de cada uno
        # para determinar si es SALIDA (Bodega) o CONSUMO_MOVIL (Móvil)
        if seriales and len(seriales) > 0:
            # Por simplicidad, tomamos la ubicación del primero para determinar el tipo de movimiento del lote
            # (Lo ideal sería uno por uno, pero registrar_movimiento_gui procesa un lote del mismo tipo)
            _, loc_real = obtener_info_serial(seriales[0])
            if loc_real:
                is_bodega = "BODEGA" in loc_real.upper()
                tipo_mov = 'SALIDA' if is_bodega else 'CONSUMO_MOVIL'
                movil_target = None if is_bodega else loc_real
                obs_meta = f"{observaciones} [Auto-detectado en: {loc_real}]"
            else:
                is_bodega = movil and ("BODEGA" in movil.upper())
                tipo_mov = 'SALIDA' if is_bodega else 'CONSUMO_MOVIL'
                movil_target = None if is_bodega else movil
                obs_meta = observaciones
        else:
            # Lógica estándar para materiales (sin seriales)
            is_bodega = movil and ("BODEGA" in movil.upper())
            tipo_mov = 'SALIDA' if is_bodega else 'CONSUMO_MOVIL'
            movil_target = None if is_bodega else movil
            obs_meta = f"{observaciones} [Origen: {movil}]" if is_bodega else observaciones
        
        ok, msg = registrar_movimiento_gui(
            sku=sku, 
            tipo_movimiento=tipo_mov, 
            cantidad_afectada=cantidad, 
            movil_afectado=movil_target, 
            fecha_evento=fecha_evento, 
            paquete_asignado=paquete or 'NINGUNO', 
            observaciones=obs_meta, 
            seriales=seriales
        )
        if ok:
            logger.info(f"📝 Consumo no registrado regularizado: {sku} x{cantidad} en {movil} (Detectado como {tipo_mov})")
            return True, "Consumo regularizado correctamente"
        return False, msg
    except Exception as e:
        logger.error(f"Error en consumo no registrado: {e}")
        return False, str(e)

def obtener_historial_faltantes(movil=None, sucursal=None, fecha_inicio=None, fecha_fin=None):
    """Obtiene el historial de faltantes registrados."""
    try:
        with db_session() as (conn, cursor):
            sql = """
                SELECT f.id, f.movil, f.sku, p.nombre, f.cantidad, f.fecha_audit, f.observaciones,
                       (SELECT GROUP_CONCAT(serial) FROM seriales_faltantes_detalle WHERE faltante_id = f.id) as seriales,
                       f.paquete
                FROM faltantes_registrados f
                LEFT JOIN productos p ON f.sku = p.sku AND p.ubicacion = 'BODEGA'
                WHERE 1=1
            """
            params = []
            if movil:
                sql += " AND f.movil = ?"
                params.append(movil)
            if sucursal:
                sql += " AND f.sucursal = ?"
                params.append(sucursal)
            if fecha_inicio:
                sql += " AND DATE(f.fecha_audit) >= ?"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND DATE(f.fecha_audit) <= ?"
                params.append(fecha_fin)
                
            sql += " ORDER BY f.fecha_audit DESC"
            run_query(cursor, sql, tuple(params))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error obteniendo historial de faltantes: {e}")
        return []
