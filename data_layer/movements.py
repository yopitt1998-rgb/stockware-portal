import sqlite3
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
                elif tipo_movimiento in ('RETORNO_MOVIL', 'ENTRADA', 'ABASTO', 'ENTRADA_AJUSTE'):
                    for s in seriales:
                        # 1. ACTUALIZAR UBICACIÓN Y ESTADO
                        run_query(cursor, "UPDATE series_registradas SET ubicacion = 'BODEGA', paquete = 'NINGUNO', estado = 'DISPONIBLE' WHERE (serial_number = ? OR mac_number = ?) AND sucursal = ?", (s, s, sucursal))
                        
                        # 2. LIMPIEZA DE FALTANTES (NUEVO)
                        # Si el equipo estaba marcado como FALTANTE, debemos limpiar ese registro para que no aparezca en reportes
                        try:
                            # Buscar si existe en el detalle de seriales faltantes
                            run_query(cursor, "SELECT faltante_id FROM seriales_faltantes_detalle WHERE serial = ? OR serial = ?", (s, s))
                            f_row = cursor.fetchone()
                            if f_row:
                                id_f = f_row[0]
                                # Eliminar del detalle
                                run_query(cursor, "DELETE FROM seriales_faltantes_detalle WHERE serial = ? OR serial = ?", (s, s))
                                # Decrementar la cabecera
                                run_query(cursor, "UPDATE faltantes_registrados SET cantidad = cantidad - 1 WHERE id = ?", (id_f,))
                                # Eliminar cabecera si llegó a 0
                                run_query(cursor, "DELETE FROM faltantes_registrados WHERE id = ? AND cantidad <= 0", (id_f,))
                        except Exception as e_f:
                            logger.warning(f"Error limpiando faltante para serial {s}: {e_f}")

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
                 # MEJORA: Para Retorno y Consumo, siempre intentar drenar de CUALQUIER paquete disponible en el móvil
                 # para evitar que queden residuos teóricos en paquetes distintos al seleccionado en la UI.
                 if (tipo_movimiento in ('CONSUMO_MOVIL', 'RETORNO_MOVIL')) and cantidad_asignacion_cambio < 0:
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
                             run_query(cursor, "UPDATE asignacion_moviles SET cantidad = 0 WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (sku, movil_afectado, fila_pq, sucursal))
                 else:
                     pq_actual = paquete_para_stock if paquete_para_stock else 'NINGUNO'
                     sql_sel = "SELECT SUM(cantidad) FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?"
                     run_query(cursor, sql_sel, (sku, movil_afectado, pq_actual, sucursal))
                     resultado_asignacion = cursor.fetchone()
                     valor_actual = float(resultado_asignacion[0]) if resultado_asignacion and resultado_asignacion[0] is not None else 0.0
                     nueva_cantidad_asignacion = max(0, valor_actual + cantidad_asignacion_cambio)
                     
                     if DB_TYPE == 'MYSQL':
                         sql_upsert = "INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad, sucursal) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad)"
                         cursor.execute(sql_upsert, (sku, movil_afectado, pq_actual, nueva_cantidad_asignacion, sucursal))
                     else:
                         run_query(cursor, "UPDATE asignacion_moviles SET cantidad = 0 WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (sku, movil_afectado, pq_actual, sucursal))
                         if nueva_cantidad_asignacion > 0:
                             run_query(cursor, "UPDATE asignacion_moviles SET cantidad = ? WHERE sku_producto = ? AND movil = ? AND COALESCE(paquete, 'NINGUNO') = ? AND sucursal = ?", (nueva_cantidad_asignacion, sku, movil_afectado, pq_actual, sucursal))
                             # Note: For SQLite we try update first, but the logic above already implies record management.

            sql_mov = "INSERT INTO movimientos (sku_producto, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia, sucursal) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            run_query(cursor, sql_mov, (sku, tipo_movimiento, cantidad_afectada, movil_afectado, fecha_evento, paquete_asignado, observaciones, documento_referencia, sucursal))

            if tipo_movimiento in ['RETORNO_MOVIL', 'CONSUMO_MOVIL'] and movil_afectado and paquete_asignado in ['PAQUETE A', 'PAQUETE B']:
                tipo_recordatorio = 'RETORNO' if tipo_movimiento == 'RETORNO_MOVIL' else 'CONCILIACION'
                run_query(cursor, "UPDATE recordatorios_pendientes SET completado = 1, fecha_completado = CURRENT_TIMESTAMP WHERE movil = ? AND paquete = ? AND tipo_recordatorio = ? AND fecha_recordatorio = ? AND completado = 0", (movil_afectado, paquete_asignado, tipo_recordatorio, fecha_evento))
        
        movil_msg = f" a/desde el {movil_afectado}" if movil_afectado else ""
        paquete_msg = f" (Paq: {paquete_asignado})" if paquete_asignado else ""
        return True, f"Movimiento {tipo_movimiento} registrado para SKU {sku} ({cantidad_afectada} unidades){movil_msg}{paquete_msg}."

    except Exception as e:
        logger.error(f"Error en registrar_movimiento_gui para SKU {sku}: {e}")
        return False, f"Error en la base de datos: {str(e)}"

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

def actualizar_movimiento_abasto(id_movimiento, nueva_cantidad, nueva_referencia):
    """Actualiza la cantidad y referencia de un movimiento de abasto, ajustando el stock."""
    conn = None
    try:
        conn = get_db_connection()
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()
        
        # 1. Obtener datos actuales del movimiento (incluye sucursal)
        run_query(cursor, "SELECT sku_producto, cantidad_afectada, COALESCE(sucursal, 'CHIRIQUI') FROM movimientos WHERE id = ?", (id_movimiento,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, "Movimiento no encontrado."
            
        sku, cantidad_anterior, sucursal = resultado
        
        # 2. Calcular diferencia
        diferencia = nueva_cantidad - cantidad_anterior
        
        # 3. Actualizar stock en Bodega (FILTRADO POR SUCURSAL)
        if diferencia != 0:
            run_query(cursor, "UPDATE productos SET cantidad = cantidad + ? WHERE sku = ? AND ubicacion = 'BODEGA' AND sucursal = ?", (diferencia, sku, sucursal))
            
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

def registrar_abasto_batch(items_abasto, fecha_evento, numero_abasto=None, existing_conn=None, sucursal_context=None):
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
        
        # SUCURSAL CONTEXT — usar el contexto activo de la sesión, no variable de entorno
        from config import CURRENT_CONTEXT
        sucursal = sucursal_context or CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')

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
            # Import local para romper dependencia circular (inventory ↔ movements)
            from data_layer.inventory import registrar_series_bulk
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

