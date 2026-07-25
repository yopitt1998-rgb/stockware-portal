import mysql.connector
import os
from datetime import datetime, date, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session

from data_layer.core import run_query, safe_messagebox

def crear_recordatorio(movil, paquete, tipo_recordatorio, fecha_recordatorio, cursor=None, sucursal=None):
    """
    Crea un nuevo recordatorio.
    FIX #36: Permite recibir un cursor para reusar conexión.
    FIX #25: Soporta parámetro sucursal.
    """
    if not sucursal:
        try:
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        except Exception:
            sucursal = 'CHIRIQUI'

    def _ejecutar(cur):
        # Verificar si ya existe un recordatorio no completado para esta combinación
        run_query(cur, """
            SELECT COUNT(*) FROM recordatorios_pendientes 
            WHERE movil = ? AND paquete = ? AND tipo_recordatorio = ? 
            AND fecha_recordatorio = ? AND completado = 0 AND sucursal = ?
        """, (movil, paquete, tipo_recordatorio, fecha_recordatorio, sucursal))
        
        if cur.fetchone()[0] == 0:
            run_query(cur, """
                INSERT INTO recordatorios_pendientes (movil, paquete, tipo_recordatorio, fecha_recordatorio, sucursal)
                VALUES (?, ?, ?, ?, ?)
            """, (movil, paquete, tipo_recordatorio, fecha_recordatorio, sucursal))
            return True
        return False

    try:
        if cursor:
            return _ejecutar(cursor)
        else:
            with db_session() as (conn, cur):
                return _ejecutar(cur)
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
            
        try:
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        except Exception:
            sucursal = 'CHIRIQUI'
        
        run_query(cursor, """
            SELECT id, movil, paquete, tipo_recordatorio, fecha_recordatorio
            FROM recordatorios_pendientes 
            WHERE fecha_recordatorio = ? AND completado = 0 AND sucursal = ?
            ORDER BY movil, tipo_recordatorio
        """, (fecha, sucursal))
        
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
            
            try:
                from config import CURRENT_CONTEXT
                sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
            except Exception:
                sucursal = 'CHIRIQUI'
            
            run_query(cursor, """
                SELECT id, movil, paquete, tipo_recordatorio, fecha_recordatorio, completado
                FROM recordatorios_pendientes 
                WHERE fecha_recordatorio = ? AND sucursal = ?
                ORDER BY movil, tipo_recordatorio
            """, (fecha, sucursal))
            
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
        try:
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        except Exception:
            sucursal = 'CHIRIQUI'
        
        run_query(cursor, "DELETE FROM recordatorios_pendientes WHERE completado = 1 AND sucursal = ?", (sucursal,))
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
        
        try:
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        except Exception:
            sucursal = 'CHIRIQUI'
        
        # Obtener todas las salidas del día para paquetes A y B
        run_query(cursor, """
            SELECT DISTINCT movil_afectado, paquete_asignado
            FROM movimientos 
            WHERE tipo_movimiento = 'SALIDA_MOVIL' 
            AND fecha_evento = ?
            AND paquete_asignado IN ('PAQUETE A', 'PAQUETE B', 'PAQUETE DOMINGO')
            AND movil_afectado IS NOT NULL
            AND sucursal = ?
        """, (fecha_salida, sucursal))
        
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
                # Crear recordatorio de retorno (reusando el cursor actual)
                if crear_recordatorio(movil, paquete, 'RETORNO', fecha_retorno.isoformat(), cursor=cursor, sucursal=sucursal):
                    recordatorios_creados += 1
                
                # Crear recordatorio de conciliación (reusando el cursor actual)
                if crear_recordatorio(movil, paquete, 'CONCILIACION', fecha_conciliacion.isoformat(), cursor=cursor, sucursal=sucursal):
                    recordatorios_creados += 1
        
        conn.commit()
        return True, f"Se crearon {recordatorios_creados} recordatorios automáticamente"
        
    except Exception as e:
        return False, f"Error al verificar y crear recordatorios: {e}"
    finally:
        if conn: close_connection(conn)

