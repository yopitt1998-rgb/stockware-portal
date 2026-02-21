import sys
import os
# Add current dir to path to allow imports
sys.path.append(os.getcwd())

from utils.db_connector import get_db_connection, close_connection
from config import DB_TYPE

print(f"DB_TYPE: {DB_TYPE}")

conn = None
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("\n--- RECENT CONSUMOS PENDIENTES (Mobile 200 focus) ---")
    query = """
        SELECT id, movil, sku, fecha, estado, tecnico_nombre, fecha_registro 
        FROM consumos_pendientes 
        WHERE movil LIKE '%200%'
        ORDER BY fecha_registro DESC LIMIT 20
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    if not rows:
        print("No consumption records found for Mobile 200.")
    for row in rows:
        print(row)

    print("\n--- RECENT SERIES REGISTRADAS (Last 20) ---")
    query = """
        SELECT id, sku, serial_number, fecha_ingreso, estado 
        FROM series_registradas 
        ORDER BY id DESC LIMIT 20
    """
    cursor.execute(query)
    for row in cursor.fetchall():
        print(row)

except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        close_connection(conn)
