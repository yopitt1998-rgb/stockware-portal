import mysql.connector
import os
from datetime import datetime, date, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session

from data_layer.core import run_query, safe_messagebox
from data_layer.inventory import *

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

