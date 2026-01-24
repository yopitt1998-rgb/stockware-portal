import sqlite3
import mysql.connector
import os
import sys
import csv
import shutil
from datetime import datetime, date, timedelta
from tkinter import messagebox
from config import (
    DATABASE_NAME,
    DB_TYPE,
    MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT,
    MOVILES_DISPONIBLES,
    UBICACION_DESCARTE,
    TIPO_MOVIMIENTO_DESCARTE,
    TIPOS_CONSUMO,
    TIPOS_ABASTO,
    PAQUETES_MATERIALES,
    PRODUCTOS_INICIALES
)

# =================================================================
# CONFIGURACIÓN DE CONEXIÓN (PUNTO 3)
# =================================================================

def get_db_connection():
    """Retorna una conexión activa (SQLite o MySQL) establecida en config.py."""
    if DB_TYPE == 'MYSQL':
        try:
            return mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASS,
                database=MYSQL_DB,
                port=MYSQL_PORT,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
        except Exception as e:
            # Fallback o error crítico
            print(f"❌ Error conectando a MySQL: {e}")
            raise e
    else:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def run_query(cursor, query, params=None):
    """
    Ejecuta una consulta ajustando la sintaxis según el motor de DB.
    Convierte '?' a '%s' si el motor es MySQL.
    """
    if DB_TYPE == 'MYSQL':
        query = query.replace('?', '%s')
    
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)

# =================================================================
# 2. FUNCIONES DE BASE DE DATOS (CRUD y Movimientos) - CORREGIDAS
# =================================================================

def inicializar_bd():
    """Crea la BD y las tablas necesarias. Compatible con SQLite y MySQL."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Auxiliares para compatibilidad
        AUTOINC = "AUTO_INCREMENT" if DB_TYPE == 'MYSQL' else "AUTOINCREMENT"
        TEXT_TYPE = "VARCHAR(255)" if DB_TYPE == 'MYSQL' else "TEXT"
        LONGTEXT = "LONGTEXT" if DB_TYPE == 'MYSQL' else "TEXT"
        INT_TYPE = "INT" if DB_TYPE == 'MYSQL' else "INTEGER"
        
        def check_column_exists(table, column):
            if DB_TYPE == 'MYSQL':
                cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
                return cursor.fetchone() is not None
            else:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                return column in columns

        def add_column_if_missing(table, column, type, default=None):
            if not check_column_exists(table, column):
                alter_query = f"ALTER TABLE {table} ADD COLUMN {column} {type}"
                if default is not None:
                    alter_query += f" DEFAULT {default}"
                cursor.execute(alter_query)
                print(f"🆕 Columna {column} añadida a {table}")

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
                UNIQUE INDEX (sku, ubicacion)
            )
        """
        cursor.execute(q_prod)
        add_column_if_missing('productos', 'minimo_stock', 'INTEGER', 10)
        add_column_if_missing('productos', 'categoria', 'VARCHAR(100)', "'General'")
        add_column_if_missing('productos', 'marca', 'VARCHAR(100)', "'N/A'")
        add_column_if_missing('productos', 'secuencia_vista', 'VARCHAR(20)')
        
        # 2. TABLA ASIGNACION_MOVILES
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS asignacion_moviles (
                id {INT_TYPE} {AUTOINC} PRIMARY KEY,
                sku_producto VARCHAR(50) NOT NULL,
                movil VARCHAR(100) NOT NULL,
                cantidad INTEGER NOT NULL DEFAULT 0,
                UNIQUE INDEX (sku_producto, movil)
            )
        """)
        
        # 3. TABLA MOVIMIENTOS
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
                observaciones {LONGTEXT}
            )
        """)
        add_column_if_missing('movimientos', 'movil_afectado', 'VARCHAR(100)')
        add_column_if_missing('movimientos', 'paquete_asignado', 'VARCHAR(50)')
        
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
        
        # 7. TABLA USUARIOS
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS usuarios (
                id {INT_TYPE} PRIMARY KEY {AUTOINC}, 
                usuario VARCHAR(50) UNIQUE, 
                password VARCHAR(255), 
                rol VARCHAR(20)
            )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO usuarios (usuario, password, rol) VALUES ('admin', 'admin123', 'ADMIN')")
            print("👤 Usuario administrador inicial creado (admin/admin123)")
            
        # 8. TABLA MOVILES
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
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        add_column_if_missing('consumos_pendientes', 'colilla', 'VARCHAR(255)')
        add_column_if_missing('consumos_pendientes', 'num_contrato', 'VARCHAR(255)')
        add_column_if_missing('consumos_pendientes', 'ayudante_nombre', 'VARCHAR(255)')

        # INDICES
        if DB_TYPE == 'SQLITE':
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku)")
        else:
            cursor.execute("SHOW INDEX FROM productos WHERE Key_name = 'idx_productos_sku'")
            if not cursor.fetchone():
                cursor.execute("CREATE INDEX idx_productos_sku ON productos(sku)")

        # MIGRACIÓN AUTOMÁTICA DE MÓVILES (Si la tabla está vacía)
        cursor.execute("SELECT COUNT(*) FROM moviles")
        if cursor.fetchone()[0] == 0:
            print("⚙️ Migrando lista estática de móviles...")
            for mv in MOVILES_DISPONIBLES:
                try:
                    cursor.execute("INSERT IGNORE INTO moviles (nombre, activo) VALUES (%s, 1)" if DB_TYPE == 'MYSQL' else "INSERT OR IGNORE INTO moviles (nombre, activo) VALUES (?, 1)", (mv,))
                except: pass

        conn.commit()
        return True
        
    except Exception as e:
        messagebox.showerror("Error Crítico", f"❌ Error de SQLite al inicializar la base de datos: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

def diagnosticar_duplicados_movil(movil):
    """Diagnóstico: Identifica duplicados exactos en asignacion_moviles"""
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error en diagnóstico: {e}")
        return []
    finally:
        if conn:
            conn.close()

def limpiar_productos_duplicados():
    """Elimina productos duplicados manteniendo el registro más reciente"""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn:
            conn.close()

def limpiar_duplicados_asignacion_moviles():
    """Limpia registros duplicados en la tabla asignacion_moviles y consolida cantidades - CORREGIDA"""
    conn = None
    try:
        conn = get_db_connection()
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
        
        print(f"Encontrados {len(duplicados)} SKUs duplicados en asignación móviles")
        
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
        if conn:
            conn.close()

def verificar_y_corregir_duplicados_completo(silent=False):
    """Realiza una limpieza completa de duplicados en todas las tablas."""
    if not silent: print("🔍 Iniciando verificación y corrección de duplicados...")
    
    # 1. Limpiar duplicados en productos
    eliminados_prod, mensaje_prod = limpiar_productos_duplicados()
    if not silent: print(f"📦 Productos: {mensaje_prod}")
    
    # 2. Limpiar duplicados en asignacion_moviles
    # Solo limpiamos esto SI detectamos que hay duplicados para evitar re-escritura total lenta
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    run_query(cursor, "SELECT COUNT(*) FROM (SELECT 1 FROM asignacion_moviles GROUP BY movil, sku_producto HAVING COUNT(*) > 1)")
    tiene_duplicados = cursor.fetchone()[0] > 0
    conn.close()

    if tiene_duplicados:
        _, mensaje_asign = limpiar_duplicados_asignacion_moviles()
        if not silent: print(f"🚚 Asignación Móviles: {mensaje_asign}")
    elif not silent:
        print("🚚 Asignación Móviles: No se encontraron duplicados.")
    
    if not silent: print("✅ Verificación completada.")
    return True

def poblar_datos_iniciales():
    """Inserta los productos de la lista inicial si no existen, con stock 0, solo en BODEGA."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Primero limpiar duplicados
        eliminados, mensaje = limpiar_productos_duplicados()
        print(f"Limpieza de duplicados: {mensaje}")
        
        # Limpiar duplicados en asignación móviles
        exito, mensaje_asignacion = limpiar_duplicados_asignacion_moviles()
        print(f"Limpieza de asignación móviles: {mensaje_asignacion}")
        
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
        print(f"Error al poblar datos iniciales: {e}")
        return False
    finally:
        if conn:
            conn.close()

def anadir_producto(nombre, sku, cantidad, ubicacion, secuencia_vista, minimo_stock=10, categoria='General', marca='N/A', fecha_evento=None):
    """Inserta un nuevo producto con datos enriquecidos."""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn:
            conn.close()

def verificar_stock_disponible(sku, cantidad_requerida, ubicacion='BODEGA'):
    """
    Verifica si hay material suficiente en una ubicación (Punto 5).
    Retorna (boolean, stock_actual)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        run_query(cursor, "SELECT cantidad FROM productos WHERE sku = ? AND ubicacion = ?", (sku, ubicacion))
        res = cursor.fetchone()
        if not res:
            return False, 0
        stock_actual = res[0]
        return stock_actual >= cantidad_requerida, stock_actual
    except Exception:
        return False, 0
    finally:
        if conn: conn.close()

def registrar_movimiento_gui(sku, tipo_movimiento, cantidad_afectada, movil_afectado=None, fecha_evento=None, paquete_asignado=None, observaciones=None, documento_referencia=None):
    """
    Registra un movimiento, actualiza la cantidad en Bodega/Asignación y maneja la ubicación DESCARTE.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if not fecha_evento: 
             return False, "Error de Fecha: La fecha del evento es obligatoria."
        
        if paquete_asignado == "NINGUNO":
             paquete_asignado = None
        
        run_query(cursor, "SELECT cantidad, nombre, secuencia_vista FROM productos WHERE sku = ? AND ubicacion = 'BODEGA'", (sku,))
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
             run_query(cursor, "SELECT cantidad FROM asignacion_moviles WHERE sku_producto = ? AND movil = ?", (sku, movil_afectado))
             asignacion_actual = cursor.fetchone()
             stock_asignado = asignacion_actual[0] if asignacion_actual else 0
        
        cantidad_bodega_cambio = 0
        cantidad_asignacion_cambio = 0
        cantidad_descarte_cambio = 0 
        
        if tipo_movimiento in ('ENTRADA', 'ABASTO'):
            if not resultado_bodega:
                run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista) VALUES (?, ?, ?, ?, ?)",
                               (nombre_producto, sku, cantidad_afectada, "BODEGA", secuencia_vista))
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
            if stock_bodega_actual < cantidad_afectada:
                return False, f"Stock insuficiente en Bodega para {nombre_producto}. Solo hay {stock_bodega_actual} unidades para descarte."
                
            cantidad_bodega_cambio = -cantidad_afectada
            cantidad_descarte_cambio = cantidad_afectada 
            
        elif tipo_movimiento == 'SALIDA':  # NUEVO: Salida individual desde bodega
            if stock_bodega_actual < cantidad_afectada:
                return False, f"Stock insuficiente en Bodega para {nombre_producto}. Solo hay {stock_bodega_actual} unidades."
                
            cantidad_bodega_cambio = -cantidad_afectada

        if cantidad_bodega_cambio != 0:
            run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = 'BODEGA'", 
                           (cantidad_bodega_cambio, sku))
            
        if cantidad_descarte_cambio > 0:
            run_query(cursor, "SELECT sku FROM productos WHERE sku = ? AND ubicacion = ?", (sku, UBICACION_DESCARTE))
            descarte_existe = cursor.fetchone()
            
            if descarte_existe:
                 run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = ?",
                                (cantidad_descarte_cambio, sku, UBICACION_DESCARTE))
            else:
                run_query(cursor, "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista) VALUES (?, ?, ?, ?, ?)",
                               (nombre_producto, sku, cantidad_descarte_cambio, UBICACION_DESCARTE, f'{secuencia_vista}z'))

        # LOGICA CORREGIDA Y ROBUSTA PARA ASIGNACION MOVILES
        if movil_afectado and cantidad_asignacion_cambio != 0:
             # 1. Obtener suma total actual (consolida duplicados si existen)
             run_query(cursor, "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = ? AND movil = ?", (sku, movil_afectado))
             resultado_asignacion = cursor.fetchone()
             asignacion_actual_total = resultado_asignacion[0] if resultado_asignacion and resultado_asignacion[0] is not None else 0
             
             # 2. Calcular nueva cantidad final
             nueva_cantidad_asignacion = asignacion_actual_total + cantidad_asignacion_cambio
             
             # 3. Borrar CUALQUIER registro existente para este SKU/Movil (limpieza de duplicados)
             run_query(cursor, "DELETE FROM asignacion_moviles WHERE sku_producto = ? AND movil = ?", (sku, movil_afectado))
             
             # 4. Insertar NUEVO registro único si la cantidad es positiva
             if nueva_cantidad_asignacion > 0:
                 run_query(cursor, "INSERT INTO asignacion_moviles (sku_producto, movil, cantidad) VALUES (?, ?, ?)",
                                (sku, movil_afectado, nueva_cantidad_asignacion))

        sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        run_query(cursor, sql_mov, (sku, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia))
        
        # Verificar si se debe marcar recordatorio como completado
        if tipo_movimiento in ['RETORNO_MOVIL', 'CONSUMO_MOVIL'] and movil_afectado and paquete_asignado in ['PAQUETE A', 'PAQUETE B']:
            tipo_recordatorio = 'RETORNO' if tipo_movimiento == 'RETORNO_MOVIL' else 'CONCILIACION'
            run_query(cursor, """
                UPDATE recordatorios_pendientes 
                SET completado = 1, fecha_completado = CURRENT_TIMESTAMP
                WHERE movil = ? AND paquete = ? AND tipo_recordatorio = ? 
                AND fecha_recordatorio = ? AND completado = 0
            """, (movil_afectado, paquete_asignado, tipo_recordatorio, fecha_evento))
        
        conn.commit()
        
        if tipo_movimiento == TIPO_MOVIMIENTO_DESCARTE:
            mensaje_final = f"✅ Descarte registrado para SKU {sku} ({cantidad_afectada} unidades)."
        elif tipo_movimiento in ('ENTRADA', 'ABASTO'):
            mensaje_final = f"✅ Entrada (Abasto) registrada para SKU {sku} ({cantidad_afectada} unidades)."
        else:
            movil_msg = f" a/desde el {movil_afectado}" if movil_afectado else ""
            paquete_msg = f" (Paq: {paquete_asignado})" if paquete_asignado else ""
            mensaje_final = f"✅ Movimiento {tipo_movimiento} registrado para SKU {sku} ({cantidad_afectada} unidades){movil_msg}{paquete_msg}."
            
        return True, mensaje_final

    except Exception as e:
        if conn: conn.rollback() 
        return False, f"Ocurrió un error al registrar el movimiento: {e}"
    except Exception as e:
         if conn: conn.rollback() 
         return False, f"Ocurrió un error inesperado: {e}"
    finally:
        if conn:
            conn.close()

# FUNCIONES PARA PRÉSTAMOS SANTIAGO
def registrar_prestamo_santiago(sku, cantidad, fecha_evento, observaciones=None):
    """
    Registra un préstamo desde Bodega a Santiago.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        run_query(cursor, "SELECT cantidad, nombre FROM productos WHERE sku = ? AND ubicacion = 'BODEGA'", (sku,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, f"El producto con SKU '{sku}' no existe en BODEGA."
        
        stock_actual, nombre = resultado
        if stock_actual < cantidad:
            return False, f"Stock insuficiente. Solo hay {stock_actual} unidades disponibles en BODEGA."
        
        exito, mensaje = registrar_movimiento_gui(sku, 'SALIDA', cantidad, None, fecha_evento, None, f"PRÉSTAMO SANTIAGO - {observaciones}" if observaciones else "PRÉSTAMO SANTIAGO")
        
        if exito:
            run_query(cursor, """
                INSERT INTO prestamos_activos (sku, nombre_producto, cantidad_prestada, fecha_prestamo, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, (sku, nombre, cantidad, fecha_evento, observaciones))
            
            conn.commit()
            return True, f"Préstamo registrado exitosamente: {cantidad} unidades de {nombre} a Santiago."
        else:
            return False, mensaje
            
    except Exception as e:
        return False, f"Error de base de datos: {e}"
    finally:
        if conn:
            conn.close()

def registrar_devolucion_santiago(sku, cantidad, fecha_devolucion, observaciones=None):
    """
    Registra una devolución desde Santiago a Bodega.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT id, cantidad_prestada, nombre_producto 
            FROM prestamos_activos 
            WHERE sku = ? AND estado = 'ACTIVO'
        """, (sku,))
        prestamos = cursor.fetchall()
        
        if not prestamos:
            return False, f"No hay préstamos activos para el SKU '{sku}'."
        
        total_prestado = sum(prestamo[1] for prestamo in prestamos)
        
        if cantidad > total_prestado:
            return False, f"Cantidad a devolver ({cantidad}) excede el total prestado activo ({total_prestado})."
        
        exito, mensaje = registrar_movimiento_gui(sku, 'ENTRADA', cantidad, None, fecha_devolucion, None, f"DEVOLUCIÓN SANTIAGO - {observaciones}" if observaciones else "DEVOLUCIÓN SANTIAGO")
        
        if exito:
            cantidad_restante = cantidad
            for prestamo in prestamos:
                if cantidad_restante <= 0:
                    break
                    
                id_prestamo, cantidad_prestada, nombre = prestamo
                
                if cantidad_restante >= cantidad_prestada:
                    run_query(cursor, "UPDATE prestamos_activos SET estado = 'DEVUELTO', fecha_devolucion = ? WHERE id = ?", 
                                 (fecha_devolucion, id_prestamo))
                    cantidad_restante -= cantidad_prestada
                else:
                    run_query(cursor, "UPDATE prestamos_activos SET cantidad_prestada = cantidad_prestada - ? WHERE id = ?", 
                                 (cantidad_restante, id_prestamo))
                    cantidad_restante = 0
            
            conn.commit()
            return True, f"Devolución registrada exitosamente: {cantidad} unidades de SKU {sku} desde Santiago."
        else:
            return False, mensaje
            
    except Exception as e:
        return False, f"Error de base de datos: {e}"
    finally:
        if conn:
            conn.close()

def obtener_prestamos_activos():
    """
    Obtiene todos los préstamos activos.
    """
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def obtener_historial_prestamos_completo():
    """
    Obtiene el historial completo de préstamos.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT sku, nombre_producto, cantidad_prestada, fecha_prestamo, 
                   fecha_devolucion, estado, observaciones
            FROM prestamos_activos 
            ORDER BY fecha_prestamo DESC, sku ASC
        """)
        return cursor.fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

# FUNCIONES PARA RECORDATORIOS - MEJORADAS
def crear_recordatorio(movil, paquete, tipo_recordatorio, fecha_recordatorio):
    """
    Crea un nuevo recordatorio.
    """
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error al crear recordatorio: {e}")
        return False
    finally:
        if conn:
            conn.close()

def obtener_recordatorios_pendientes(fecha=None):
    """
    Obtiene los recordatorios pendientes para una fecha específica o para hoy.
    """
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error al obtener recordatorios: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_recordatorios_todos(fecha=None):
    """
    Obtiene TODOS los recordatorios para una fecha específica, incluyendo completados.
    """
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error al obtener todos los recordatorios: {e}")
        return []
    finally:
        if conn:
            conn.close()

def marcar_recordatorio_completado(id_recordatorio):
    """
    Marca un recordatorio como completado.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        run_query(cursor, """
            UPDATE recordatorios_pendientes 
            SET completado = 1, fecha_completado = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (id_recordatorio,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al marcar recordatorio como completado: {e}")
        return False
    finally:
        if conn:
            conn.close()

def eliminar_recordatorios_completados():
    """
    Elimina los recordatorios que ya han sido completados.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        run_query(cursor, "DELETE FROM recordatorios_pendientes WHERE completado = 1")
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al eliminar recordatorios completados: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verificar_y_crear_recordatorios_salida(fecha_salida):
    """
    Verifica si hay salidas en una fecha y crea recordatorios automáticamente.
    """
    conn = None
    try:
        conn = get_db_connection()
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
        if conn:
            conn.close()

def obtener_inventario():
    """Obtiene todos los productos enriquecidos para la tabla principal."""
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()
            
def obtener_inventario_para_exportar():
    """Obtiene todos los campos del inventario, incluyendo secuencia_vista y fecha_creacion, para exportar."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql_query = """
        SELECT ubicacion, secuencia_vista, sku, nombre, cantidad, fecha_creacion
        FROM productos 
        ORDER BY ubicacion DESC, secuencia_vista ASC
        """
        run_query(cursor, sql_query) 
        return cursor.fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def obtener_todos_los_skus_para_movimiento():
    """
    Obtiene todos los SKUs y nombres únicos del inventario, y su cantidad en BODEGA (si existe), 
    ordenados por secuencia de vista - CORREGIDO: SIN DUPLICADOS.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_unique_skus = """
            SELECT DISTINCT p.nombre, p.sku, p.secuencia_vista
            FROM productos p
            WHERE p.ubicacion = 'BODEGA'
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_unique_skus)
        all_products_raw = cursor.fetchall()
        
        sql_bodega_stock = """
            SELECT sku, cantidad
            FROM productos
            WHERE ubicacion = 'BODEGA'
        """
        run_query(cursor, sql_bodega_stock)
        bodega_stock = {sku: cantidad for sku, cantidad in cursor.fetchall()}
        
        result = []
        skus_procesados = set()
        
        for nombre, sku, secuencia_vista in all_products_raw:
            if sku not in skus_procesados:  # CLAVE: Verificar que no sea duplicado
                cantidad = bodega_stock.get(sku, 0)
                result.append((nombre, sku, cantidad))
                skus_procesados.add(sku)
            
        return result
    except Exception as e:
        print(f"Error al obtener todos los SKUs para movimiento: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_ultima_salida_movil(movil):
    """Obtiene la última salida realizada a un móvil específico"""
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def obtener_asignacion_movil(movil):
    """Obtiene el inventario actual asignado a un móvil específico (usado en Consiliación)."""
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def obtener_asignacion_movil_con_paquetes(movil):
    """
    Obtiene el stock exacto por paquete (PAQUETE A, PAQUETE B, CARRO, SIN PAQUETE)
    sin aplicar compensaciones incorrectas.
    Basado 100% en movimientos reales - CORREGIDO: SIN DUPLICADOS.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Obtener productos asignados a ese móvil (AGREGADO: GROUP BY para evitar duplicados)
        sql_total = """
            SELECT p.nombre, a.sku_producto, SUM(a.cantidad) as total
            FROM asignacion_moviles a
            JOIN productos p ON a.sku_producto = p.sku
            WHERE a.movil = ? AND a.cantidad > 0
            GROUP BY a.sku_producto, p.nombre, p.secuencia_vista  -- CORREGIDO: Agrupar para evitar duplicados
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_total, (movil,))
        productos_asignados = cursor.fetchall()

        if not productos_asignados:
            return []

        resultado = []

        # 2. Para cada SKU reconstruimos el saldo REAL por paquete
        for nombre, sku, total_real in productos_asignados:

            # Inicializar los saldos exactos por paquete
            saldos = {
                "PAQUETE A": 0,
                "PAQUETE B": 0,
                "CARRO": 0,
                "SIN_PAQUETE": 0
            }

            # 3. Obtener TODOS los movimientos en orden real
            sql_mov = """
                SELECT tipo_movimiento, cantidad_afectada, paquete_asignado
                FROM movimientos 
                WHERE sku_producto = ? AND movil_afectado = ?
                AND tipo_movimiento IN ('SALIDA_MOVIL','RETORNO_MOVIL','CONSUMO_MOVIL')
                ORDER BY fecha_movimiento ASC, id ASC
            """
            run_query(cursor, sql_mov, (sku, movil))
            movimientos = cursor.fetchall()

            # 4. Reprocesar EXACTAMENTE según los movimientos
            for tipo, cantidad, paquete in movimientos:

                # Normalizar paquete
                if paquete is None or paquete == "NINGUNO":
                    paquete_key = "SIN_PAQUETE"
                else:
                    paquete_key = paquete

                # SALIDA suma material (entra al móvil)
                if tipo == "SALIDA_MOVIL":
                    saldos[paquete_key] += cantidad

                # RETORNO o CONSUMO restan material
                elif tipo in ("RETORNO_MOVIL", "CONSUMO_MOVIL"):
                    saldos[paquete_key] -= cantidad
                    if saldos[paquete_key] < 0:
                        saldos[paquete_key] = 0  # evitar negativos por errores del pasado

            # 5. Recalcular total real de paquetes
            total_por_paquetes = sum(saldos.values())

            # 6. Si no cuadra con asignacion_moviles, corregimos PERO SIN ALTERAR PAQUETES
            if total_por_paquetes != total_real:
                diferencia = total_real - total_por_paquetes
                # La diferencia se añade SIEMPRE a SIN_PAQUETE (no toca paquetes marcados)
                saldos["SIN_PAQUETE"] += diferencia
                if saldos["SIN_PAQUETE"] < 0:
                    saldos["SIN_PAQUETE"] = 0

            # Guardar resultado final para ese SKU
            resultado.append((
                nombre,
                sku,
                total_real,
                saldos["PAQUETE A"],
                saldos["PAQUETE B"],
                saldos["CARRO"]
            ))

        return resultado

    except Exception as e:
        print(f"Error en obtener_asignacion_movil_con_paquetes: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_reporte_asignacion_moviles(movil=None):
    """Obtiene el inventario asignado a TODOS los móviles, opcionalmente filtrado por un móvil específico."""
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def eliminar_producto(sku):
    """Elimina un producto y su historial de movimientos y asignación. Elimina todas las ubicaciones de ese SKU."""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn:
            conn.close()

def obtener_historial_producto(sku, fecha_inicio=None, fecha_fin=None):
    """Obtiene el historial de movimientos de un producto por SKU, con filtro de rango de fechas de evento, incluyendo el paquete asignado."""
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def obtener_abastos_resumen():
    """Obtiene un resumen de los abastos realizados, agrupados por fecha y referencia."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
            WHERE tipo_movimiento = 'ABASTO'
            GROUP BY fecha_evento, documento_referencia
            ORDER BY fecha_evento DESC, ultima_modificacion DESC
        """
        run_query(cursor, sql_query)
        return cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener resumen de abastos: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_detalle_abasto(fecha, referencia):
    """Obtiene los detalles de un abasto específico."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_query, (fecha, referencia))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener detalle de abasto: {e}")
        return []
    finally:
        if conn:
            conn.close()

def actualizar_movimiento_abasto(id_movimiento, nueva_cantidad, nueva_referencia):
    """Actualiza la cantidad y referencia de un movimiento de abasto, ajustando el stock."""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn:
            conn.close()

def obtener_historial_producto_para_exportar(sku, fecha_inicio=None, fecha_fin=None):
    """Obtiene el historial de movimientos de un producto por SKU con todos los campos relevantes para exportar, con filtro de fecha, incluyendo el paquete."""
    conn = None
    try:
        conn = get_db_connection()
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
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

def obtener_reporte_consumo(fecha_inicio, fecha_fin):
    """Obtiene el consumo total de material (SALIDA, CONSUMO_MOVIL, DESCARTE) entre dos fechas."""
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error al generar reporte de consumo: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_reporte_abasto(fecha_inicio, fecha_fin):
    """Obtiene el abasto/entrada total de material (ENTRADA, ABASTO) entre two fechas."""
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error al generar reporte de abasto: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_stock_actual_y_moviles():
    """Obtiene el stock actual en bodega y el total asignado a móviles por cada SKU."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_bodega = """
            SELECT sku, SUM(cantidad) as stock_bodega
            FROM productos 
            WHERE ubicacion = 'BODEGA'
            GROUP BY sku
        """
        run_query(cursor, sql_bodega)
        stock_bodega = {sku: cantidad for sku, cantidad in cursor.fetchall()}
        
        sql_moviles = """
            SELECT sku_producto, SUM(cantidad) as stock_moviles
            FROM asignacion_moviles 
            WHERE cantidad > 0
            GROUP BY sku_producto
        """
        run_query(cursor, sql_moviles)
        stock_moviles = {sku: cantidad for sku, cantidad in cursor.fetchall()}
        
        # NUEVO: Obtener consumo total por SKU
        sql_consumo = """
            SELECT sku_producto, SUM(cantidad_afectada) as consumo_total
            FROM movimientos 
            WHERE tipo_movimiento IN ({})
            GROUP BY sku_producto
        """.format(','.join(['?' for _ in TIPOS_CONSUMO]))
        
        run_query(cursor, sql_consumo, TIPOS_CONSUMO)
        consumo_total = {sku: cantidad for sku, cantidad in cursor.fetchall()}
        
        # NUEVO: Obtener abasto total por SKU
        sql_abasto = """
            SELECT sku_producto, SUM(cantidad_afectada) as abasto_total
            FROM movimientos 
            WHERE tipo_movimiento IN ({})
            GROUP BY sku_producto
        """.format(','.join(['?' for _ in TIPOS_ABASTO]))
        
        run_query(cursor, sql_abasto, TIPOS_ABASTO)
        abasto_total = {sku: cantidad for sku, cantidad in cursor.fetchall()}
        
        sql_productos = """
            SELECT DISTINCT p.sku, p.nombre, p.secuencia_vista
            FROM productos p
            WHERE p.ubicacion = 'BODEGA'
            ORDER BY p.secuencia_vista ASC
        """
        run_query(cursor, sql_productos)
        productos = cursor.fetchall()
        
        resultado = []
        for sku, nombre, secuencia in productos:
            bodega = stock_bodega.get(sku, 0)
            moviles = stock_moviles.get(sku, 0)
            total = bodega + moviles
            consumo = consumo_total.get(sku, 0)
            abasto = abasto_total.get(sku, 0)
            resultado.append((nombre, sku, bodega, moviles, total, consumo, abasto))
            
        return resultado
        
    except Exception as e:
        print(f"Error al obtener stock actual y móviles: {e}")
        return []
    finally:
        if conn:
            conn.close()

def obtener_estadisticas_reales():
    """Obtiene estadísticas reales para el dashboard"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Productos en Bodega (contar productos únicos en BODEGA)
        run_query(cursor, """
            SELECT COUNT(DISTINCT sku) 
            FROM productos 
            WHERE ubicacion = 'BODEGA' AND cantidad > 0
        """)
        productos_bodega = cursor.fetchone()[0]
        
        # 2. Móviles Activos (contar móviles con productos asignados)
        run_query(cursor, """
            SELECT COUNT(DISTINCT movil) 
            FROM asignacion_moviles 
            WHERE cantidad > 0
        """)
        moviles_activos = cursor.fetchone()[0]
        
        # 3. Stock Total (suma de todo el stock en BODEGA)
        run_query(cursor, """
            SELECT SUM(cantidad) 
            FROM productos 
            WHERE ubicacion = 'BODEGA'
        """)
        stock_total_result = cursor.fetchone()[0]
        stock_total = stock_total_result if stock_total_result else 0
        
        # 4. Préstamos Activos
        run_query(cursor, "SELECT COUNT(*) FROM prestamos_activos WHERE estado = 'ACTIVO'")
        prestamos_activos = cursor.fetchone()[0]
        
        # 5. Productos con Bajo Stock (Usando su propio minimo_stock - PUNTO 1)
        run_query(cursor, """
            SELECT COUNT(*) 
            FROM productos 
            WHERE ubicacion = 'BODEGA' AND cantidad < minimo_stock AND cantidad > 0
        """)
        bajo_stock = cursor.fetchone()[0]
        
        return {
            "productos_bodega": productos_bodega,
            "moviles_activos": moviles_activos,
            "stock_total": stock_total,
            "prestamos_activos": prestamos_activos,
            "bajo_stock": bajo_stock
        }
        
    except Exception as e:
        print(f"Error al obtener estadísticas reales: {e}")
        return {
            "productos_bodega": 0,
            "moviles_activos": 0,
            "stock_total": 0,
            "stock_total": 0,
            "prestamos_activos": 0,
            "bajo_stock": 0
        }
    finally:
        if conn:
            conn.close()

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

def obtener_movimientos_por_rango(fecha_inicio, fecha_fin):
    """
    Obtiene todos los movimientos en un rango de fechas.
    Retorna lista de tuplas con detalles del movimiento.
    """
    conn = None
    try:
        conn = get_db_connection()
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
        print(f"Error al obtener movimientos por rango: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- FUNCIONES PARA PORTAL MÓVIL (PUNTO 5) ---

def registrar_consumo_pendiente(movil, sku, cantidad, tecnico, ticket, fecha, colilla=None, contrato=None, ayudante=None):
    """Guarda un reporte proveniente del portal móvil (Punto 5)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        run_query(cursor, """
            INSERT INTO consumos_pendientes (movil, sku, cantidad, tecnico_nombre, ayudante_nombre, ticket, fecha, colilla, num_contrato)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (movil, sku, cantidad, tecnico, ayudante, ticket, fecha, colilla, contrato))
        conn.commit()
        return True, "Registro guardado"
    except Exception as e:
        return False, str(e)
    finally:
        if conn: conn.close()

def obtener_consumos_pendientes(estado='PENDIENTE'):
    """Obtiene consumos reportados por móviles incluyendo colilla y contrato."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        run_query(cursor, """
            SELECT c.id, c.movil, c.sku, p.nombre, c.cantidad, c.tecnico_nombre, c.ticket, c.fecha, c.colilla, c.num_contrato, c.ayudante_nombre
            FROM consumos_pendientes c
            LEFT JOIN productos p ON c.sku = p.sku AND p.ubicacion = 'BODEGA'
            WHERE c.estado = ?
            ORDER BY c.fecha_registro DESC
        """, (estado,))
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if conn: conn.close()

def obtener_detalles_moviles():
    """Retorna un diccionario {nombre_movil: {conductor, ayudante}}"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        run_query(cursor, "SELECT nombre, conductor, ayudante FROM moviles WHERE activo = 1")
        filas = cursor.fetchall()
        return {f[0]: {"conductor": f[1] or "", "ayudante": f[2] or ""} for f in filas}
    except Exception:
        return {}
    finally:
        if conn: conn.close()

def procesar_auditoria_consumo(id_consumo, sku, cantidad, movil, fecha, ticket, observaciones):
    """
    Confirma un consumo pendiente: lo marca como AUDITADO y realiza el movimiento real.
    """
    # 1. Realizar movimiento real
    exito, mensaje = registrar_movimiento_gui(
        sku, 'CONSUMO_MOVIL', cantidad, movil, fecha, None, observaciones
    )
    
    if exito:
        # 2. Marcar como auditado
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            run_query(cursor, "UPDATE consumos_pendientes SET estado = 'AUDITADO' WHERE id = ?", (id_consumo,))
            conn.commit()
        finally:
            if conn: conn.close()
            
    return exito, mensaje



def obtener_ultimos_movimientos(limite=15):
    """
    Obtiene los últimos movimientos registrados en el sistema.
    Retorna lista de tuplas: (id, fecha_evento, tipo, producto, cantidad, usuario/movil)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_query = """
            SELECT 
                m.id,
                m.fecha_evento,
                m.tipo_movimiento,
                COALESCE(p.nombre, 'Producto Eliminado (' || m.sku_producto || ')') as nombre_prod,
                m.cantidad_afectada,
                COALESCE(m.movil_afectado, 'Bodega') as destino
            FROM movimientos m
            LEFT JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            ORDER BY m.fecha_creacion DESC, m.id DESC
            LIMIT ?
        """
        # Note: fecha_creacion might not likely exist in legacy movements table, falling back to id which is autoincrement
        # However, let's check schema. In `inicializar_bd` we saw `fecha_movimiento DEFAULT CURRENT_TIMESTAMP`.
        # So we should use `fecha_movimiento` for "Last registered".
        
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
            ORDER BY m.fecha_movimiento DESC
            LIMIT ?
        """
        
        run_query(cursor, sql_query, (limite,))
        return cursor.fetchall()
        
    except Exception as e:
        print(f"Error al obtener últimos movimientos: {e}")
        return []
    finally:
        if conn:
            conn.close()

# =================================================================
# GESTIÓN DE MÓVILES (CRUD)
# =================================================================

def crear_movil(nombre, patente=None, conductor=None, ayudante=None):
    """Crea un nuevo móvil en la base de datos."""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn: conn.close()

def obtener_moviles(solo_activos=True):
    """Obtiene la lista de móviles. Retorna lista de tuplas (nombre, patente, conductor, ayudante, activo)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT nombre, patente, conductor, ayudante, activo FROM moviles"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY nombre ASC"
            
        run_query(cursor, query)
        return cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener móviles: {e}")
        return []
    finally:
        if conn: conn.close()

def obtener_nombres_moviles(solo_activos=True):
    """Retorna una LISTA de STRINGS con los nombres de los móviles (para compatibilidad con comboboxes)."""
    moviles = obtener_moviles(solo_activos)
    return [m[0] for m in moviles]

def editar_movil(nombre_actual, nuevo_nombre, nueva_patente, nuevo_conductor, nuevo_ayudante):
    """Edita los datos de un móvil."""
    conn = None
    try:
        conn = get_db_connection()
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
        if conn: conn.close()

def eliminar_movil(nombre):
    """
    Marca un móvil como inactivo (Soft Delete).
    """
    conn = None
    try:
        conn = get_db_connection()
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
        if conn: conn.close()

# =================================================================
# CONFIGURACIÓN DE EMPRESA
# =================================================================

def obtener_configuracion():
    """Obtiene los datos de configuración de la empresa."""
    conn = None
    try:
        conn = get_db_connection()
        # Usar Row para acceder por nombre de columna
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        run_query(cursor, "SELECT * FROM configuracion WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {}
    except sqlite3.Error:
        return {}
    finally:
        if conn: conn.close()

def guardar_configuracion(datos):
    """Guarda/Actualiza los datos de configuración."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            UPDATE configuracion SET 
            nombre_empresa = ?, rut = ?, direccion = ?, 
            telefono = ?, email = ?, logo_path = ?
            WHERE id = 1
        """
        params = (
            datos.get('nombre_empresa'), datos.get('rut'), 
            datos.get('direccion'), datos.get('telefono'), 
            datos.get('email'), datos.get('logo_path')
        )
        
        run_query(cursor, sql, params)
        conn.commit()
        return True, "Configuración guardada exitosamente."
    except sqlite3.Error as e:
        return False, f"Error al guardar: {e}"
    finally:
        if conn: conn.close()

# =================================================================
# GESTIÓN DE USUARIOS Y AUTENTICACIÓN
# =================================================================

def autenticar_usuario(username, password):
    """Verifica credenciales de usuario."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        run_query(cursor, """
            SELECT id, username, rol, nombre_completo 
            FROM usuarios 
            WHERE username = ? AND password = ? AND activo = 1
        """, (username, password))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        print(f"Error en autenticación: {e}")
        return None
    finally:
        if conn: conn.close()

def crear_usuario(username, password, rol, nombre):
    """Crea un nuevo usuario."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        run_query(cursor, """
            INSERT INTO usuarios (username, password, rol, nombre_completo) 
            VALUES (?, ?, ?, ?)
        """, (username, password, rol, nombre))
        conn.commit()
        return True, f"Usuario '{username}' creado."
    except sqlite3.IntegrityError:
        return False, f"El nombre de usuario '{username}' ya existe."
    except sqlite3.Error as e:
        return False, f"Error: {e}"
    finally:
        if conn: conn.close()

def obtener_usuarios():
    """Obtiene lista de usuarios activos."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        run_query(cursor, "SELECT id, username, rol, nombre_completo FROM usuarios WHERE activo = 1")
        return cursor.fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn: conn.close()

def eliminar_usuario(id_usuario):
    """Marca un usuario como inactivo."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        run_query(cursor, "UPDATE usuarios SET activo = 0 WHERE id = ?", (id_usuario,))
        conn.commit()
        return True, "Usuario desactivado."
    except sqlite3.Error as e:
        return False, f"Error: {e}"
    finally:
        if conn: conn.close()
