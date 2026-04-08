import sqlite3
import mysql.connector
import os

from utils.logger import get_logger

logger = get_logger(__name__)
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session

from data_layer.core import run_query, safe_messagebox

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
            SELECT sku, ubicacion, 1 as priority, 1 as is_serial, paquete FROM series_registradas 
            WHERE UPPER(serial_number) = ? OR UPPER(mac_number) = ?
            UNION ALL
            SELECT sku, NULL as ubicacion, 2 as priority, 0 as is_serial, NULL as paquete FROM productos 
            WHERE codigo_barra = ? OR codigo_barra = ?
            UNION ALL
            SELECT sku, NULL as ubicacion, 3 as priority, 0 as is_serial, NULL as paquete FROM productos 
            WHERE codigo_barra_maestro IN (?, ?, ?)
            UNION ALL
            SELECT sku, NULL as ubicacion, 4 as priority, 0 as is_serial, NULL as paquete FROM productos 
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
            # Result: (sku, ubicacion, priority, is_serial, paquete)
            return result[0], bool(result[3]), result[1], result[4]
            
        return None, False, None, None
        
    except Exception as e:
        logger.error(f"Error en identificar_codigo_escaneado_gui: {e}")
        return None, False, None, None
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
        sql_seriales = "SELECT sku, serial_number, mac_number, ubicacion, paquete FROM series_registradas WHERE sucursal = ?"
        run_query(cursor, sql_seriales, (sucursal_target,))
        for sku, s_num, m_num, ubicacion, paquete in cursor.fetchall():
            if s_num and s_num.strip():
                serial_cache[s_num.strip().upper()] = (sku, ubicacion, paquete)
            if m_num and m_num.strip():
                serial_cache[m_num.strip().upper()] = (sku, ubicacion, paquete)

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

def buscar_producto_por_codigo_barra_maestro(codigo_barra, sucursal_context=None):
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
        
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

        # Buscar por código de barra (maestro o legacy) O por SKU (case-insensitive)
        run_query(cursor, """
            SELECT p.sku, p.nombre, p.cantidad as stock
            FROM productos p
            WHERE (UPPER(TRIM(p.codigo_barra_maestro)) IN (?, ?) 
               OR UPPER(TRIM(p.codigo_barra)) IN (?, ?)
               OR UPPER(TRIM(p.sku)) IN (?, ?))
               AND p.ubicacion = 'BODEGA'
               AND p.sucursal = ?
            LIMIT 1
        """, (codigo, raw_code, codigo, raw_code, codigo, raw_code, sucursal))
        
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

def buscar_producto_por_mac(mac_address, sucursal_context=None):
    """
    Busca un producto por su MAC/serial en la tabla series_registradas.
    
    Args:
        mac_address: MAC o serial del equipo
        
    Returns:
        dict con información del producto o None si no existe
    """
    conn = None
    try:
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

        # Normalizar MAC (uppercase y trim)
        mac = mac_address.strip().upper()
        
        # Buscar en tabla series_registradas
        # CLAVE: Unir con productos también filtrando por sucursal
        run_query(cursor, """
            SELECT s.sku, p.nombre, s.ubicacion, s.mac_number
            FROM series_registradas s
            JOIN productos p ON s.sku = p.sku AND s.sucursal = p.sucursal
            WHERE UPPER(TRIM(s.mac_number)) = ? AND s.estado = 'DISPONIBLE'
              AND s.sucursal = ? AND p.ubicacion = 'BODEGA'
            LIMIT 1
        """, (mac, sucursal))
        
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


def obtener_todos_los_seriales_sucursal(sucursal_context=None):
    """
    Obtiene un set de todos los seriales y mac_numbers existentes en la sucursal actual.
    Optimizado para validación rápida en memoria durante escaneos masivos (Abastos).
    """
    try:
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        
        with db_session() as (conn, cursor):
            # Obtener seriales y MACs
            sql = """
                SELECT serial_number, mac_number 
                FROM series_registradas 
                WHERE sucursal = ? OR (sucursal IS NULL AND ? = 'CHIRIQUI')
            """
            run_query(cursor, sql, (sucursal, sucursal))
            rows = cursor.fetchall()
            
            # Crear un set para búsqueda O(1)
            seriales = set()
            for s, m in rows:
                if s: seriales.add(s.strip().upper())
                if m: seriales.add(m.strip().upper())
            
            return seriales
    except Exception as e:
        logger.error(f"Error cargando caché de seriales: {e}")
        return set()
