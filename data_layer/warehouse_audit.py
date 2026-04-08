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
    logger.info("Tablas de Auditoría de Bodega verificadas/readas correctamente.")

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
        # Obtener stock inicial y manual
        run_query(cursor, """
            SELECT i.sku, p.nombre, i.cantidad_inicio, i.cantidad_manual, i.id
            FROM auditoria_bodega_items i
            JOIN productos p ON i.sku = p.sku
            WHERE i.id_sesion = ? AND p.ubicacion = 'BODEGA'
        """, (id_sesion,))
        items = {r[0]: {'nombre': r[1], 'inicio': r[2], 'manual': r[3], 'id': r[4]} for r in cursor.fetchall()}
        
        # Sumar Abastos
        run_query(cursor, """
            SELECT sku, SUM(cantidad) FROM auditoria_bodega_abastos 
            WHERE id_sesion = ? GROUP BY sku
        """, (id_sesion,))
        for sku, total in cursor.fetchall():
            if sku in items:
                items[sku]['abastos'] = total
            else: # SKU que no estaba en items pero tiene abasto
                items[sku] = {'inicio': 0, 'manual': 0, 'abastos': total}
                
        # Sumar Billing
        run_query(cursor, """
            SELECT sku, SUM(cantidad) FROM auditoria_bodega_billing 
            WHERE id_sesion = ? GROUP BY sku
        """, (id_sesion,))
        for sku, total in cursor.fetchall():
            if sku in items:
                items[sku]['billing'] = total
            elif sku not in items:
                items[sku] = {'inicio': 0, 'manual': 0, 'abastos': 0, 'billing': total}

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

def registrar_abasto_ocr(id_sesion, sku, cantidad, img_path):
    """Registra un nuevo abasto detectado por OCR."""
    with db_session() as (conn, cursor):
        run_query(cursor, """
            INSERT INTO auditoria_bodega_abastos (id_sesion, sku, cantidad, imagen_path)
            VALUES (?, ?, ?, ?)
        """, (id_sesion, sku, cantidad, img_path))
    return True

def registrar_billing_excel(id_sesion, sku, cantidad, archivo):
    """Registra consumo de billing desde Excel."""
    with db_session() as (conn, cursor):
        run_query(cursor, """
            INSERT INTO auditoria_bodega_billing (id_sesion, sku, cantidad, fuente_archivo)
            VALUES (?, ?, ?, ?)
        """, (id_sesion, sku, cantidad, archivo))
    return True
