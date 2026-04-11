from datetime import datetime
from utils.db_connector import db_session, run_query
from utils.logger import get_logger

logger = get_logger(__name__)

def crear_tablas_auditoria():
    """Crea las tablas necesarias para el módulo de Auditoría de Bodega."""
    with db_session() as (conn, cursor):
        # 1. Sesiones de Auditoría
        run_query(cursor, """
            CREATE TABLE IF NOT EXISTS auditoria_bodega_sesiones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fecha DATE NOT NULL,
                sucursal VARCHAR(50) NOT NULL,
                responsable VARCHAR(255),
                completada TINYINT DEFAULT 0,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(fecha, sucursal)
            )
        """)
        
        # 2. Items de Auditoría (Resultados por SKU)
        run_query(cursor, """
            CREATE TABLE IF NOT EXISTS auditoria_bodega_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_sesion INT NOT NULL,
                sku VARCHAR(50) NOT NULL,
                cantidad_inicio INT DEFAULT 0,
                cantidad_manual INT DEFAULT 0,
                observaciones TEXT,
                FOREIGN KEY (id_sesion) REFERENCES auditoria_bodega_sesiones(id),
                UNIQUE(id_sesion, sku)
            )
        """)
        
        # 3. Registro de Abastos (Detalle de imágenes/OCR)
        run_query(cursor, """
            CREATE TABLE IF NOT EXISTS auditoria_bodega_abastos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_sesion INT NOT NULL,
                sku VARCHAR(50) NOT NULL,
                cantidad INT DEFAULT 0,
                imagen_path TEXT,
                numero_factura VARCHAR(255),
                fecha_documento DATE,
                documento_referencia VARCHAR(255),
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_sesion) REFERENCES auditoria_bodega_sesiones(id)
            )
        """)
        
        # 4. Registro de Billing (Detalle de Excel)
        run_query(cursor, """
            CREATE TABLE IF NOT EXISTS auditoria_bodega_billing (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_sesion INT NOT NULL,
                sku VARCHAR(50) NOT NULL,
                cantidad INT DEFAULT 0,
                fuente_archivo TEXT,
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_sesion) REFERENCES auditoria_bodega_sesiones(id)
            )
        """)
        
        # MIGRACIÓN: Asegurar que las columnas nuevas existan en auditoria_bodega_abastos
        # (Esto es necesario porque CREATE TABLE IF NOT EXISTS no añade columnas si la tabla ya existe)
        try:
            run_query(cursor, "ALTER TABLE auditoria_bodega_abastos ADD COLUMN numero_factura VARCHAR(255) AFTER imagen_path")
        except Exception:
            pass # Ya existe
            
        try:
            run_query(cursor, "ALTER TABLE auditoria_bodega_abastos ADD COLUMN fecha_documento DATE AFTER numero_factura")
        except Exception:
            pass # Ya existe

        try:
            run_query(cursor, "ALTER TABLE auditoria_bodega_abastos ADD COLUMN documento_referencia VARCHAR(255) AFTER fecha_documento")
        except Exception:
            pass # Ya existe
            
    logger.info("Tablas de Auditoría de Bodega verificadas y migradas correctamente.")

def obtener_o_crear_sesion_auditoria(sucursal, fecha=None):
    """Obtiene la sesión activa para hoy o crea una nueva."""
    if fecha is None:
        fecha = datetime.now().date()
    
    with db_session() as (conn, cursor):
        run_query(cursor, 
            "SELECT id FROM auditoria_bodega_sesiones WHERE sucursal = ? AND fecha = ?",
            (sucursal, fecha)
        )
        res = cursor.fetchone()
        if res:
            return res[0]
        
        # Si no existe, crearla
        run_query(cursor, 
            "INSERT INTO auditoria_bodega_sesiones (sucursal, fecha) VALUES (?, ?)",
            (sucursal, fecha)
        )
        return cursor.lastrowid

def obtener_items_auditoria(id_sesion):
    """Retorna todos los items y sus cálculos para una sesión."""
    with db_session() as (conn, cursor):
        # 1. Obtener stock inicial y manual (de los que ya tienen registro en items)
        run_query(cursor, """
            SELECT i.sku, p.nombre, i.cantidad_inicio, i.cantidad_manual, i.id
            FROM auditoria_bodega_items i
            JOIN productos p ON i.sku = p.sku
            WHERE i.id_sesion = ?
        """, (id_sesion,))
        items = {r[0]: {'nombre': r[1], 'inicio': r[2], 'manual': r[3], 'id': r[4]} for r in cursor.fetchall()}
        
        # 2. Sumar Abastos y asegurar que tengan nombre
        run_query(cursor, """
            SELECT a.sku, p.nombre, SUM(a.cantidad) 
            FROM auditoria_bodega_abastos a
            JOIN productos p ON a.sku = p.sku
            WHERE a.id_sesion = ? 
            GROUP BY a.sku, p.nombre
        """, (id_sesion,))
        for sku, nombre, total in cursor.fetchall():
            if sku in items:
                items[sku]['abastos'] = total
            else:
                items[sku] = {'nombre': nombre, 'inicio': 0, 'manual': 0, 'abastos': total}
                
        # 3. Sumar Billing y asegurar que tengan nombre
        run_query(cursor, """
            SELECT b.sku, p.nombre, SUM(b.cantidad) 
            FROM auditoria_bodega_billing b
            JOIN productos p ON b.sku = p.sku
            WHERE b.id_sesion = ? 
            GROUP BY b.sku, p.nombre
        """, (id_sesion,))
        for sku, nombre, total in cursor.fetchall():
            if sku in items:
                items[sku]['billing'] = total
            elif sku not in items:
                items[sku] = {'nombre': nombre, 'inicio': 0, 'manual': 0, 'abastos': 0, 'billing': total}

        # Asegurar que todas las claves existen
        for sku in items:
            items[sku].setdefault('inicio', 0)
            items[sku].setdefault('abastos', 0)
            items[sku].setdefault('billing', 0)
            items[sku].setdefault('manual', 0)
            
        return items

def guardar_cambio_item(id_sesion, sku, campo, valor):
    """Guarda cambios en cantidad_inicio o cantidad_manual."""
    valid_fields = {'cantidad_inicio', 'cantidad_manual'}
    if campo not in valid_fields:
        return False
    
    with db_session() as (conn, cursor):
        run_query(cursor, f"""
            INSERT INTO auditoria_bodega_items (id_sesion, sku, {campo})
            VALUES (?, ?, ?)
            ON DUPLICATE KEY UPDATE {campo} = VALUES({campo})
        """, (id_sesion, sku, valor))
    return True

def finalizar_sesion_auditoria(id_sesion):
    """Limpia todos los registros de una sesión de auditoría para permitir un reinicio."""
    with db_session() as (conn, cursor):
        # Eliminar items, abastos y billing asociados a la sesión
        run_query(cursor, "DELETE FROM auditoria_bodega_items WHERE id_sesion = ?", (id_sesion,))
        run_query(cursor, "DELETE FROM auditoria_bodega_abastos WHERE id_sesion = ?", (id_sesion,))
        run_query(cursor, "DELETE FROM auditoria_bodega_billing WHERE id_sesion = ?", (id_sesion,))
        run_query(cursor, "UPDATE auditoria_bodega_sesiones SET completada = 1 WHERE id = ?", (id_sesion,))
    return True

def registrar_abasto_ocr(id_sesion, sku, cantidad, img_path, factura="", fecha_doc=None, referencia=""):
    """Registra un nuevo abasto detectado por OCR, incluyendo número de factura y fecha."""
    with db_session() as (conn, cursor):
        run_query(cursor, """
            INSERT INTO auditoria_bodega_abastos (id_sesion, sku, cantidad, imagen_path, numero_factura, fecha_documento, documento_referencia)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_sesion, sku, cantidad, img_path, factura, fecha_doc, referencia))
    return True

def eliminar_abasto_registro(id_registro):
    """Elimina un registro específico de abasto por su ID."""
    with db_session() as (conn, cursor):
        run_query(cursor, "DELETE FROM auditoria_bodega_abastos WHERE id = ?", (id_registro,))
    return True

def eliminar_abastos_por_factura(id_sesion, factura):
    """Elimina todos los registros de abasto asociados a una factura en una sesión."""
    with db_session() as (conn, cursor):
        run_query(cursor, """
            DELETE FROM auditoria_bodega_abastos 
            WHERE id_sesion = ? AND numero_factura = ?
        """, (id_sesion, factura))
    return True

def actualizar_abasto_ocr(id_registro, nueva_cantidad, nueva_factura=None):
    """Actualiza la cantidad o factura de un registro de abasto."""
    with db_session() as (conn, cursor):
        if nueva_factura is not None:
            run_query(cursor, """
                UPDATE auditoria_bodega_abastos 
                SET cantidad = ?, numero_factura = ? 
                WHERE id = ?
            """, (nueva_cantidad, nueva_factura, id_registro))
        else:
            run_query(cursor, """
                UPDATE auditoria_bodega_abastos 
                SET cantidad = ? 
                WHERE id = ?
            """, (nueva_cantidad, id_registro))
    return True

def registrar_billing_excel(id_sesion, sku, cantidad, archivo):
    """Registra consumo de billing desde Excel."""
    with db_session() as (conn, cursor):
        run_query(cursor, """
            INSERT INTO auditoria_bodega_billing (id_sesion, sku, cantidad, fuente_archivo)
            VALUES (?, ?, ?, ?)
        """, (id_sesion, sku, cantidad, archivo))
    return True

def limpiar_billing_sesion(id_sesion):
    """Elimina todos los registros de billing cargados por Excel para esta sesión."""
    with db_session() as (conn, cursor):
        run_query(cursor, "DELETE FROM auditoria_bodega_billing WHERE id_sesion = ?", (id_sesion,))
    return True

def obtener_detalles_abastos(id_sesion):
    """Retorna el historial detallado de abastos para la sesión, incluyendo IDs para borrado."""
    with db_session() as (conn, cursor):
        run_query(cursor, """
            SELECT a.fecha_registro, a.sku, p.nombre, a.cantidad, a.imagen_path, a.numero_factura, a.fecha_documento, a.id
            FROM auditoria_bodega_abastos a
            JOIN productos p ON a.sku = p.sku
            WHERE a.id_sesion = ?
            ORDER BY a.fecha_registro DESC
        """, (id_sesion,))
        return cursor.fetchall()

def obtener_historial_completo_sesion(id_sesion):
    """Retorna un historial unificado de abastos y billing de la sesión con nombres de productos."""
    with db_session() as (conn, cursor):
        # Unir abastos y billing con una marca de tipo y nombre de producto
        run_query(cursor, """
            SELECT a.fecha_registro, a.sku, 'ABASTO' as tipo, a.cantidad, a.imagen_path as fuente, p.nombre
            FROM auditoria_bodega_abastos a
            JOIN productos p ON a.sku = p.sku
            WHERE a.id_sesion = ?
            UNION ALL
            SELECT b.fecha_registro, b.sku, 'BILLING' as tipo, b.cantidad, b.fuente_archivo as fuente, p.nombre
            FROM auditoria_bodega_billing b
            JOIN productos p ON b.sku = p.sku
            WHERE b.id_sesion = ?
            ORDER BY fecha_registro DESC
        """, (id_sesion, id_sesion))
        return cursor.fetchall()
