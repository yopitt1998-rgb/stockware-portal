import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
import csv
import shutil
from datetime import datetime, date, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session

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
        import traceback
        traceback.print_exc()
        print(f"❌ Error de {engine} al inicializar la base de datos:\n\n{e}")
        safe_messagebox("Error Crítico", f"❌ Error de {engine} al inicializar la base de datos:\n\n{e}")
        raise e
    finally:
        if conn: close_connection(conn)

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

