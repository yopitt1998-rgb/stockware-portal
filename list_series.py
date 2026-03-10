
import os
import sys
import mysql.connector

# Agregar el directorio actual al path
sys.path.append(os.getcwd())

import config
from utils.db_connector import get_db_connection

def list_recent_series():
    print("--- Últimos 20 registros en series_registradas ---")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = "SELECT * FROM series_registradas ORDER BY id DESC LIMIT 20"
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        if not rows:
            print("No hay registros en series_registradas.")
            return

        print(f"{'ID':<6} | {'SKU':<12} | {'SERIAL':<25} | {'UBIC':<15} | {'ESTADO':<12} | {'SUC':<15}")
        print("-" * 100)
        for r in rows:
            print(f"{r['id']:<6} | {repr(r['sku']):<12} | {repr(r['serial_number']):<25} | {repr(r['ubicacion']):<15} | {repr(r['estado']):<12} | {repr(r['sucursal']):<15}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    list_recent_series()
